# Real Work IQ — Microsoft 365 Calendar via Microsoft Graph

How to move the **Work IQ** layer from synthetic signals to **real Microsoft 365 work
context**, step by step. This is the practical, provable path; the code seam is already in
the repo.

## Why Graph (and not the Work IQ service)

The Microsoft **Work IQ** service (`workiq.svc.cloud.microsoft`) is the "official" layer, but:

- it requires an **M365 Copilot add-on license** (~$30/user/mo) — standard M365 doesn't qualify,
- it's in **limited preview** (TAP / Developer License needed),
- it's **delegated-only** and returns **natural language**, not structured signals.

**Microsoft Graph `Calendars.Read`** delivers the *same* `WorkIQSignals` fields (meeting
load, focus time, busy periods) from the real calendar, on **any M365 license**. The agents
never change — only the *source* of the signals does. Frame it honestly to judges:
*"Work context grounded in Microsoft 365 calendar via Microsoft Graph."*

## What's already wired in the repo

| Piece | File | Role |
|---|---|---|
| Settings | `config/settings.py` | `WORK_IQ_SOURCE`, `GRAPH_*` vars |
| Adapter | `backend/iq/work_iq_graph.py` | `GraphWorkIQClient` — calendarView → `WorkIQSignals` → `WorkContext` |
| Selector | `backend/iq/work_iq.py` | `get_work_iq()` returns Graph client (synthetic fallback) when `WORK_IQ_SOURCE=graph` |
| Login | `scripts/graph_device_login.py` | one-time device-code token |

The adapter preserves the exact `WorkContext` shape, so the Engagement Agent, Manager
Insights, what-if simulator, and readiness logic are untouched. If a token/mailbox is
missing or Graph errors, each call **degrades to synthetic** — demos never break.

## Step 1 — Register an Entra app

```bash
az ad app create --display-name "EnterpriseCertIQ-WorkIQ" \
  --sign-in-audience AzureADMyOrg \
  --is-fallback-public-client true            # public client → device-code flow
# note the appId (client id) and your tenant id
```

In the portal (Entra ID → App registrations → your app):
1. **Authentication** → Advanced settings → **Allow public client flows = Yes**.
2. **API permissions** → Add → Microsoft Graph → **Delegated** → `Calendars.Read`
   (add `Calendars.Read.Shared` if reading teammates' calendars). Grant admin consent if required.

## Step 2 — Acquire a token (one time)

```bash
source .venv/bin/activate
pip install -r requirements.azure.txt        # provides azure-identity

export GRAPH_TENANT_ID=<tenant-guid>          # or "common"
export GRAPH_CLIENT_ID=<app-client-id>
python scripts/graph_device_login.py
# → open the URL, enter the code, sign in. Token printed; cache persisted.
```

## Step 3 — Point the backend at Graph

In `.env.local` (or `.env.azure`):

```dotenv
WORK_IQ_SOURCE=graph
GRAPH_TENANT_ID=<tenant-guid>
GRAPH_CLIENT_ID=<app-client-id>

# Quickest: paste the token from step 2 (refresh via the script when it expires)
GRAPH_ACCESS_TOKEN=<token>
# …or omit the token and the backend reuses the persisted device-code cache.

# Map synthetic learner ids → real test mailboxes (UPNs). Without this, the
# default mailbox below is used for everyone.
GRAPH_LEARNER_UPN_MAP={"L-1004":"alex@contoso.com","L-1005":"sam@contoso.com"}
GRAPH_DEFAULT_UPN=me
```

> No real tenant? Leave `WORK_IQ_SOURCE=synthetic` (default). Or use a Microsoft 365
> Developer Program tenant with seeded calendars — same code path, synthetic mailboxes.

## Step 4 — Verify it's really Graph

```bash
./start.sh --no-setup --skip-model
# Engagement/Manager now read live calendar; the disclosure string changes:
curl -s localhost:8000/api/manager/TEAM-A/insights | python3 -m json.tool | grep -i "ai_disclosure"
#   → "...from Microsoft 365 calendar via Microsoft Graph"
```

Add a meeting to the test mailbox's next 7 days → re-run a workflow → the learner's
`meeting_hours_pw` rises, `capacity_risk` shifts, and recommended study slots adapt.

## How the mapping works (adapter internals)

`GraphWorkIQClient.get_work_context(learner)`:

1. resolve mailbox: `GRAPH_LEARNER_UPN_MAP[learner_id]` → else `GRAPH_DEFAULT_UPN`.
2. token: `GRAPH_ACCESS_TOKEN` → else `DeviceCodeCredential` (cached).
3. `GET /users/{upn}/calendarView` for the next 7 days (`$select=subject,start,end,showAs`).
4. sum hours where `showAs ∈ {busy, oof, workingElsewhere, tentative}` → `meeting_hours_per_week`.
5. `focus_hours = 40 − meeting_hours` (floored); `available_study_hours = conservative slice`.
6. build `WorkIQSignals` → `WorkContext` via the **same** helpers the synthetic client uses.

So the only thing that changed between synthetic and real Work IQ is **where steps 3–4 get
their numbers** — every downstream agent is identical.

## Production hardening (beyond the hackathon)

- **App-only is not supported** for Work IQ; for unattended Graph calendar reads use
  `Calendars.Read` *application* permission + client-credentials (admin-consented) and read
  specific mailboxes — swap `_get_token()` for `ClientSecretCredential`/managed identity.
- Cache calendar reads per user (the LLM cache doesn't cover Graph) to respect rate limits.
- Store tokens in Key Vault, not env, in cloud deployments.
- For the true Work IQ A2A service later: keep this same `WorkContext` contract and add a
  `WorkIQServiceClient` behind the selector — agents still won't change.
```
