# Hermes Intake

Turns a new client's first-call transcript into setup documents that a person approves before anything is acted on.

## Language

**Client**:
A home-improvement company (e.g. Mike's Roofing) onboarding with the agency.
_Avoid_: Customer, account, lead

**Transcript**:
The text of a Client's first call, as submitted.
_Avoid_: Call, recording

**Redacted Transcript**:
A Transcript with emails, phone numbers and street addresses replaced by numbered placeholders such as `[EMAIL_1]`. The only form of a Transcript the agent, the database and the logs ever see.

**Intake**:
One Transcript processed once into an Intake Output, together with its status and cost. Request changes does not re-run it.
_Avoid_: Run, job, request

**Intake Output**:
What an Intake produces: the Client's Current Systems, an Architecture Doc, an Access Checklist and a list of Feasibility Verdicts.
_Avoid_: Result, report

**Current System**:
A piece of software or service the Client already uses (e.g. WordPress, Google Ads, Jobber). A personal phone is not a system.
_Avoid_: Existing tool, stack

**Architecture Doc**:
The proposed systems to set up for the Client (e.g. landing page, CRM, missed-call text-back).

**Access Checklist**:
The logins, keys and permissions the agency must obtain from the Client.

**Feasibility Verdict**:
A judgement on one integration between two systems: yes, partial or no, with a reason.

**Issue**:
A Feasibility Verdict of "no". A "partial" verdict is not an Issue.
_Avoid_: Problem, blocker, risk

**Approval**:
A person's Approve or Request changes decision on an Intake, made in Slack. Request changes carries a Change Reason.

**Change Reason**:
What the reviewer says should change, typed in Slack when they click Request changes. It is recorded on the Intake; it does not re-run it.

**Injection Flag**:
A marker on an Intake whose Transcript contained phrases that try to instruct the agent.
_Avoid_: Block, rejection

**Fallback**:
Completing an Intake with the secondary model after the primary model failed, timed out or returned an invalid Intake Output.
_Avoid_: Backup agent, retry

**Estimated Cost**:
What an Intake would have cost at the model providers' published paid prices. Shown next to the actual cost, which is zero on free tiers.
