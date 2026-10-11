# Finding Watch — BYTE release and acceptance checklist

Reviewed against https://bytesoc.dev/tasks/applied-ml/ on **11 October 2026**. The BYTE task portal itself may require interactive account-specific fields; none are fabricated here. Portal: https://submissions.bytesoc.dev/. **Deadline: 13 October 2026, 11:59 PM IST.**

| Official Basic Agentic Task requirement | Implemented evidence | Status / caveat |
|---|---|---|
| Tabular dataset + natural-language questions | `agentic/app.py`, `engine.load_csv`, Gemini `agent.ask` | CSV only; custom AI path requires consent and a supported model |
| Five genuinely distinct tools | `inspect_dataset`, `filter_rows`, `grouped_summary`, `time_trend`, `correlation` | Five deterministic tools, not five wrappers; Challenge and clarification do not count |
| Agent actually uses tools to answer | SDK function declarations, bounded tool loop and executed evidence trace | Prior user reports of live grouped/monthly/clarification; no new live run for release docs |
| Works on suitable unfamiliar data | Column-driven UI and spec validation; test fixtures with alternate schemas | Not every dataset/ambiguity is supported; conservative types and explicit dates |
| Disclose stack and contribution | Root README, pinned requirements, `CONTRIBUTIONS.md` | AI-assisted code/docs transparently acknowledged; user must personally review wording |
| Public GitHub repository | Complete source prepared in Git bundle | **Not published**; public repository URL still needed |
| README with setup/tools | Root README and deployment docs | Prepared; candidate should review and own it |
| Video or hosted demo preferred | `DEMO_SCRIPT.md`, `DEPLOYMENT.md` | Not recorded/deployed here; actual working URL required if claimed |
| Optional persistent memory | Not implemented | Do not count it as a sixth tool or claim the optional mission |

## Release checks

- [x] Starting accepted commit verified: `754ec1cda8f917fbe62f242d503c654dca4138d6`; 22 commits preserved before release documentation.
- [x] Release changes limited to documentation / release preparation; engine, specs, comparisons and agent unchanged.
- [x] `requirements.txt` pinned; `agentic/app.py` and requirements colocated for Streamlit Community Cloud.
- [x] Confirmed via Streamlit docs: root-level Cloud secrets become environment variables; `agent.configuration()` has `os.getenv` fallback. No secret file is tracked.
- [x] Tracked HEAD and previous history inspected for common high-confidence credential patterns and sensitive file names. **0 hits in 164 historical blobs** before this documentation commit. This is a best-effort automated check, not a mathematical guarantee; user should additionally inspect GitHub's secret scanning alerts.
- [x] No `.env`, `secrets.toml`, virtual environment, personal dataset, or local `live_verification*.json` included in the release files.
- [ ] New release's full Windows suite / running browser checks: **not re-run** for documentation changes; last user-reported frozen Stage 3 build: **239 passed**.
- [ ] Fresh model call after release: **not run**; prior user-reported real grouped, monthly and clarification calls are historical evidence only.
- [ ] Publish GitHub repository with correct `main` branch and readable README; check it is public and files are safe.
- [ ] If chosen, record short demo and/or deploy Streamlit app, then verify real link and resource/secret settings.
- [ ] Submit the repository plus requested portal fields **before 13 October 2026, 11:59 PM IST**; the second task, if required, is separate.

## Scope limitations worth disclosing during review

Only explicit validated descriptive calculations; one filter change on a grouped finding; no data accuracy guarantee, causal interpretation, forecasting, joins, arbitrary generated Python, cross-session memory or Revisit. A host-wide Gemini key shared through a public deployment can consume its owner's quota. App reports a safe error and allows local analysis when the provider is unavailable.
