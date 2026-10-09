# BYTE Applied ML — Finding Watch M1 implementation candidate

**Scope:** Phase 3's five distinct analytical tools + narrowly validated composable filters and calculation evidence. **M0 live agent test pending**, and **M1 is not accepted**. This project is only the Basic Agentic Task. Challenge, Revisit and memory have not been implemented.

## Local Windows setup

For the independent-review repairs, see **[`agentic/docs/M1_REPAIR_HANDOFF.md`](agentic/docs/M1_REPAIR_HANDOFF.md)**. See **[`agentic/docs/M0_WINDOWS.md`](agentic/docs/M0_WINDOWS.md)** for exact install, real Gemini verification and Streamlit checks. `agentic/docs/M1_HANDOFF.md` documents the specification contract, evidence, limits and exclusions. `agentic/verify_live.py` uses an existing **private** local `.env`/environment variable and synthetic data only; it does not print keys. Do not commit or package secrets.

```powershell
cd agentic
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_live.py --output live_verification_local.json
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Structure

- `engine.py`: guarded CSV load, five read-only deterministic tools, full-data filtered executor and evidence.
- `specs.py`: strict versioned `AnalysisSpec` validator (no model-generated code execution).
- `agent.py`: bounded Gemini function-calling adapter; calculation evidence is separate from unverified narrative.
- `app.py`: existing Streamlit manual and AI workflows, plus optional analysis filters and submitted-result binding.
- `tests/test_engine.py`: preserved Phase 3 deterministic engine tests.
- `tests/test_m1.py`: independently expected M1 numerical fixtures and boundary cases.
- `tests/test_agent.py` & `tests/test_app.py`: mocked agent/Streamlit tests requiring full requirements.
- `docs/`: requirements, contributions, M0/M1 verification and scope.

## Source history

The repaired distribution includes `phaseM1-repair-history.bundle` with the original Phase 3 baseline and M1 commit. Restore with:

```powershell
git clone -b main .\phaseM1-repair-history.bundle byte-ml-with-history
```

The original audited ZIP is left untouched. `.env`, `.venv`, caches, DBs, user uploads and local live-verification logs are not distributed.
