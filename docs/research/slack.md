# Slack: signatures, block_actions, posting and updating (ticket #7). Retrieved 2026-10-14

Sources:
- [SIG] https://docs.slack.dev/authentication/verifying-requests-from-slack
- [INT] https://docs.slack.dev/interactivity/handling-user-interaction
- [BA] https://docs.slack.dev/reference/interaction-payloads/block_actions-payload
- [PM] https://docs.slack.dev/reference/methods/chat.postMessage, [UPD] .../chat.update
- [BTN] https://docs.slack.dev/reference/block-kit/block-elements/button-element, [ACT] .../blocks/actions-block
- [SDK] slackapi/python-slack-sdk `slack_sdk/signature/__init__.py`, `slack_sdk/web/async_client.py` (latest v3.45.0, 2026-10-01)

## Verifying request signatures [SIG]
- Headers: `X-Slack-Signature` (`v0=<hex>`) and `X-Slack-Request-Timestamp` (unix seconds). Header names are case-insensitive.
- Base string: `f"v0:{timestamp}:{raw_body}"`. Compute HMAC-SHA256 with the signing secret as the key and take the hex digest. The signature is `"v0=" + hexdigest`.
- Use the **raw body bytes** from before any form parsing, so call `await request.body()` before reading the form.
- Reject the request if `|now - timestamp| > 5 minutes` (replay protection). Compare with `hmac.compare_digest`.

`slack_sdk.signature.SignatureVerifier` [SDK], verbatim behaviour:
```python
from slack_sdk.signature import SignatureVerifier, Clock
v = SignatureVerifier(signing_secret)            # ValueError if empty/blank secret
ok = v.is_valid_request(body: bytes|str, headers: Mapping[str,str])   # lowercases header keys itself
ok = v.is_valid(body, timestamp, signature)      # False if either missing; False if abs(now-ts) > 300
sig = v.generate_signature(timestamp=ts, body=body)   # "v0=<hex>", handy for building signed requests in tests/e2e
```
- `is_valid` calls `int(timestamp)`, so a non-numeric header raises **ValueError**. Wrap the call in try/except and return 401.
- For tests, inject the clock with a `Clock` subclass whose `now()` returns a fixed value: `SignatureVerifier(secret, clock=FixedClock())`.

FastAPI sketch:
```python
@router.post("/slack/actions")
async def slack_actions(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    try:
        if not verifier.is_valid_request(raw, dict(request.headers)):
            raise HTTPException(401)
    except ValueError:
        raise HTTPException(401)
    payload = json.loads(urllib.parse.parse_qs(raw.decode())["payload"][0])
    bg.add_task(service.apply_decision, ...)   # or do the fast DB update inline, then post the chat.update in the background
    return Response(status_code=200)           # empty 200 = ack
```

## Interactive payload delivery and ack [INT]
- Slack sends an HTTP POST with `Content-Type: application/x-www-form-urlencoded`. The body holds one `payload` field containing **JSON**.
- You must return **HTTP 200 within 3 seconds**, otherwise the user sees an error. An empty body is fine.
- The docs fetched do not describe retries for interactivity. The Events API retries with an `X-Slack-Retry-Num` header, but that is the Events API, not interactivity. Idempotency via the status guard covers both.
- Request URL: App settings → **Interactivity & Shortcuts** → On → `https://<host>/slack/actions`.

## `block_actions` payload: where things live [BA]
```json
{ "type":"block_actions",
  "user": {"id":"UA8RXUSPL","username":"jtorrance","name":"jtorrance","team_id":"T9TK3CUKW"},
  "team": {"id":"T9TK3CUKW","domain":"example"}, "api_app_id":"AABA1ABCD", "token":"<deprecated>",
  "container": {"type":"message","message_ts":"1548261231.000200","channel_id":"CBR2V3XEX","is_ephemeral":false},
  "channel": {"id":"CBR2V3XEX","name":"review-updates"},
  "message": {"ts":"1548261231.000200","text":"...","blocks":[...]},
  "response_url":"https://hooks.slack.com/actions/...", "trigger_id":"...",
  "actions":[{"type":"button","action_id":"intake_approve","block_id":"intake_actions","value":"<intake_id>",
              "text":{"type":"plain_text","text":"Approve"},"action_ts":"..."}] }
```

| Need | Path |
|---|---|
| user id / name | `user.id`, `user.username` (also `user.name` in some examples) |
| action | `actions[0].action_id`, `actions[0].value` |
| channel id | `channel.id` (or `container.channel_id`) |
| message ts | `message.ts` (or `container.message_ts`) |

- Tip: for the "Approved by @me" text, render `<@{user.id}>`. Slack displays it as the user's name, so no name lookup is needed.
- Store `approved_by` as `user.username` or `user.id`. Decide which in the contracts ticket.

## Message with two buttons: chat.postMessage [PM][BTN][ACT]
```python
from slack_sdk.web.async_client import AsyncWebClient   # requires `aiohttp` installed (async_base_client imports it)
from slack_sdk.errors import SlackApiError               # raised when ok=false; e.response["error"]
client = AsyncWebClient(token=bot_token)                 # optional: base_url=..., timeout=30, session=aiohttp.ClientSession
resp = await client.chat_postMessage(channel=channel_id, text="New intake: Mike's Roofing. 3 systems found, 1 issue flagged",
  blocks=[
    {"type":"section","text":{"type":"mrkdwn","text":"*New intake:* Mike's Roofing\n3 systems found, 1 issue flagged\n:warning: Injection flag"}},
    {"type":"actions","block_id":"intake_actions","elements":[
      {"type":"button","action_id":"intake_approve","style":"primary","value":str(intake_id),
       "text":{"type":"plain_text","text":"Approve"}},
      {"type":"button","action_id":"intake_request_changes","style":"danger","value":str(intake_id),
       "text":{"type":"plain_text","text":"Request changes"}}]}])
slack_ts, channel = resp["ts"], resp["channel"]     # response: {"ok":true,"channel":"C..","ts":"1503435956.000247","message":{...}}
```
- Scope: `chat:write`. The bot must be in the channel, otherwise you get `not_in_channel`. Other errors: `channel_not_found`, `invalid_auth`.
- Top-level `text` is "highly recommended" as the notification and screen-reader fallback.
- Limits:
  - Button `value` ≤ 2000 chars and `action_id` ≤ 255. Button text is plain_text, ≤ 75 chars.
  - `style` is `primary` or `danger`, and `primary` is used on at most one button.
  - An actions block holds ≤ 25 elements, and `block_id` ≤ 255.

## Editing after a decision: chat.update [UPD]
```python
await client.chat_update(channel=channel_id, ts=slack_ts,
    text=f"Approved by <@{user_id}>",
    blocks=[{"type":"section","text":{"type":"mrkdwn","text":f"*Mike's Roofing*: :white_check_mark: Approved by <@{user_id}>"}}])
```
- Required: `channel`, `ts`, and a `chat:write` token.
- To remove the buttons, pass a new `blocks` list without the actions block. `blocks=[]` removes all blocks, and passing `text` with no `blocks` also drops them.
- Only messages posted by the same bot can be updated (`cant_update_message`). Other errors: `message_not_found`, `channel_not_found`, `invalid_auth`.
- Alternative: POST `{"replace_original": true, "text": ..., "blocks": [...]}` to the payload's `response_url`, which needs no token. chat.update is what the spec uses.

## Spec mapping
- With no `SLACK_BOT_TOKEN`, skip posting and keep `slack_ts=None`.
- Callbacks:
  - Verify the signature first, then 401 on a bad or stale one.
  - Ack 200 immediately.
  - Apply the transition only from `awaiting_approval`. Repeats are no-ops that still return 200.
  - Run `chat_update` in a background task so the 3 s ack is never at risk.
- To test the edit without Slack, point `AsyncWebClient(base_url=...)` at a fake server, or inject the recording fake notifier through the Protocol.
