"""Redaction and the Injection Flag on submission, through the HTTP seam."""

import httpx

from app.agents.fake import FakeAgent
from tests.api.test_intakes import TRANSCRIPTS, submit

RAW_PII = (
    "dana.whitfield@clearflowplumbing.com",
    "(512) 555-0187",
    "555-0142",
    "4821 Riverside Drive",
    "78741",
)


async def test_pii_transcript_is_stored_and_returned_redacted(
    api_client: httpx.AsyncClient, fake_agent: FakeAgent
) -> None:
    raw = (TRANSCRIPTS / "pii_example.txt").read_text()

    created = await submit(api_client, "Clearflow Plumbing", raw)
    fetched = await api_client.get(f"/intakes/{created.json()['id']}")

    for body in (created.json(), fetched.json()):
        for value in RAW_PII:
            assert value not in body["transcript_redacted"]
        assert "[EMAIL_1]" in body["transcript_redacted"]
        assert "[PHONE_1]" in body["transcript_redacted"]
        assert "[ADDRESS_1]" in body["transcript_redacted"]
    assert body["injection_flagged"] is False
    assert all(value not in call for call in fake_agent.calls for value in RAW_PII)


async def test_injection_transcript_is_flagged_but_still_processed(
    api_client: httpx.AsyncClient,
) -> None:
    raw = (TRANSCRIPTS / "injection_example.txt").read_text()

    created = await submit(api_client, "Raj HVAC", raw)
    fetched = (await api_client.get(f"/intakes/{created.json()['id']}")).json()

    assert created.json()["injection_flagged"] is True
    assert fetched["injection_flagged"] is True
    assert fetched["status"] == "awaiting_approval"


async def test_mikes_roofing_is_not_flagged(api_client: httpx.AsyncClient) -> None:
    created = await submit(api_client)

    assert created.json()["injection_flagged"] is False
