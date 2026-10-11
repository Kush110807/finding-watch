# Gemini reliability repair — review candidate

## What is established vs unknown

- Existing `agent.client_for` used a **30,000 ms HTTP timeout**, and `HttpRetryOptions(attempts=1)` already disabled automatic SDK retry multiplication. The agent loop previously had no process-wide request pacing or application backoff. Each `generate_content` round (including follow-ups after tool responses) is a separate Google request; a single user question can consume several.
- Reported **429, 503, 504 and 400 are separate HTTP outcomes**, not evidence of one underlying defect. `429` can reflect RPM, token or daily/project quota; account screenshots of historical usage do not establish current headroom. `503` is temporary service unavailability, `504` a gateway timeout, and `400` a rejected request/model/tool schema (non-retryable unchanged). An HTTP/transport timeout also has its own classification.
- The source and supplied history do not contain server-side Google traces proving why specific requests failed, the applicable project quota, or whether another process or service consumed capacity. This repair does not claim to establish those root causes.

## Policy

The new `provider_reliability.py` maintains a **single thread-safe process-local start-time scheduler** using a lock and monotonic clock. Request admissions are spaced using the time of the last actual admission; delayed or concurrent sleepers recheck the deadline and spacing under the lock when they wake. No lock is held while sleeping, and no waiting caller reserves a future slot. All `ask`/`execute` provider requests and application-level retries use it. The model-listing route also passes through the scheduler (SDK pagination, if invoked, is not individually rate-limited). Default spacing is **13 seconds**, conservative against a user-reported **5 requests/minute** limit. This does not measure input TPM or RPD and cannot coordinate other applications, deployment workers/processes, restarts, or an entire Google project. A public deployment using the same Google project will still share its true quota.

Per `generate_content` request: SDK automatic attempts remain **1**; application policy allows **3 attempts total** (but **at most 2 for an ambiguous HTTP 429**), 30-second SDK HTTP timeout, capped exponential delay with jitter, max 30-second backoff, a 95-second request budget and a 180-second overall `ask` budget, and at most **6 actual provider attempts across all rounds in one question** (including retries). Configurable bounds are validated with safe defaults via `.env.example`. If Retry-After or `google.rpc.RetryInfo` requires waiting beyond allowed budget/cap, the app stops instead of retrying too early; it never assumes a reset time. Structured `QuotaFailure` violations explicitly identifying a per-day limit stop immediately. **400, 401, 403, 404 and unrelated/unclassified failures do not retry.** 408, 429 (qualified), 500, 502, 503, 504 and known transport timeouts/network errors may be retried within those limits.

The retry callback repeats the **same failed SDK provider request** and the same accumulated agent `contents`. Deterministic tools that already ran are **not rerun**. If later provider contact fails, its output is `status=error`, `calculation_verified=False`, with partial tool trace retained only as supporting audit information, not as a completed answer. No other request or user result is promoted to answer status. The UI protects the submitted question, keeps local analysis working, shows concise wait/retry progress, and presents safe diagnostic metadata inside the technical disclosure.

**Redaction:** Diagnostics expose only category, HTTP status (if present), attempt count, elapsed seconds and partial-tools boolean. Never save exception strings, raw API response bodies, prompts, CSV contents or credentials in public diagnostic output. Provider SDK exceptions may themselves contain sensitive details, so Python tracebacks from user-provided secrets should not be published.

## Verification, without Google quota

```powershell
cd byte-ml\agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_provider_reliability.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_agent.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### One combined final browser / live check

1. Start app, load bundled example and confirm local analysis works **without** Gemini; consent is opt-in.
2. Enable consent using **your existing private configuration**. Ask one custom supported question requesting a real tool, such as “What is the monthly total revenue? The date column is date in YYYY-MM-DD format.” Confirm an actual `time_trend` call and evidence, not a model listing or a suggested local computation. If it fails, report the category/status/attempt count, not the raw exception.
3. Ask once: **“Predict the exact total fee for October 2026 and prove that more hours cause higher fees.”** Expected: no fabricated exact future total or causal proof. It should explain the unsupported forecast/causal request and invite a supported descriptive question. A provider error is **not a passing result**. Do not repeatedly retry this against limited quota.
4. On a desktop and ~390px browser, verify retry/wait messages when they occur, the original question remains editable after failure, no earlier answer appears as the new answer, local manual tools and Challenge confirmation still work.
5. Share only redacted diagnostic summaries and screen evidence without local API keys or sensitive CSV data. Do not share `.env` or the raw provider request.

No live provider call was made by this repair process. Earlier user-verified monthly/clarification results belong to an earlier commit.
