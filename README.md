# BYTE Applied ML — Finding Watch M2 candidate

**Scope:** Five distinct Phase 3 analytical tools; accepted M1 composable evidence; M2 restricted, confirmation-gated Challenge a Finding. The user reports **M1 accepted** after independent and Windows checks, including live M0 smoke checks. **M2 is a candidate awaiting independent review**; the M2 Gemini comparison remains unverified. Revisit, SQLite memory and forecasting have not been implemented. This project addresses the Basic Agentic Task only.

## Local Windows setup

For the current M2 specification, fixtures, Windows checks and limitations, see **[`agentic/docs/M2_HANDOFF.md`](agentic/docs/M2_HANDOFF.md)**. Earlier repairs are documented in **[`agentic/docs/M1_REPAIR_HANDOFF.md`](agentic/docs/M1_REPAIR_HANDOFF.md)**. See **[`agentic/docs/M0_WINDOWS.md`](agentic/docs/M0_WINDOWS.md)** for exact install, real Gemini verification and Streamlit checks. `agentic/docs/M1_HANDOFF.md` documents the specification contract, evidence, limits and exclusions. `agentic/verify_live.py` uses an existing **private** local `.env`/environment variable and synthetic data only; it does not print keys. Do not commit or package secrets.

```powershell
cd agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_live.py --output live_verification_local.json
.\.venv\Scripts\python.exe verify_live_comparison.py --confirm --output live_comparison_confirmed_local.json
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Structure

- `engine.py`: guarded CSV load, five read-only deterministic tools, full-data filtered executor and evidence.
- `specs.py`: strict versioned `AnalysisSpec` validator (no model-generated code execution).
- `comparisons.py`: one-filter grouped comparison validator and full-data evidence; distinct from five analytical tools.
- `agent.py`: bounded Gemini adapter, with proposal-only confirmation-gated comparison tool; calculation evidence is separate from unverified narrative.
- `app.py`: retained Streamlit manual/AI workflows, plus small manual/AI M2 definition preview and confirmation controls.
- `tests/test_engine.py`: preserved Phase 3 deterministic engine tests.
- `tests/test_m1.py`: independently expected M1 numerical fixtures and boundary cases.
- `tests/test_m2.py`, `tests/test_m2_agent_adapter.py`: deterministic grouped Challenge checks and isolated offline SDK-shim tests.
- `tests/test_agent.py` & `tests/test_app.py`: pinned-SDK mocked agent and real Streamlit AppTest tests requiring full dependencies.
- `docs/`: requirements, contributions, M0/M1 verification and scope.

## Source history

The M2 distribution includes `phaseM2-history.bundle` with the original Phase 3 baseline, M1 and M2 commits. Restore with:

```powershell
git clone -b main .\phaseM2-history.bundle byte-ml-with-history
```

The original audited ZIP is left untouched. `.env`, `.venv`, caches, DBs, user uploads and local live-verification logs are not distributed.
