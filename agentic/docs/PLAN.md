# Scope and acceptance plan

Phase 1: runnable Streamlit shell, dependency declaration, sample CSV, local secret template, Windows instructions and Git checkpoint.
Phase 2: CSV input and five distinct deterministic tools. Each tool validates columns and parameters and returns structured results. Test numerical results independently.
Phase 3: Gemini adapter and bounded tool-calling loop. Model selects operations; Python calculates. Never execute model-generated Python, SQL or shell commands. Tool results drive the final answer and visible evidence. Unknown or ambiguous fields require clarification.
Phase 4: evaluate at least three different dataset schemas, held-out questions, missing data, malformed files, date ambiguity, empty selections and misleading prompts. Record failures as well as successes.
Phase 5: SQLite memory for user-confirmed definitions, filters and preferences. Dataset-scoped definitions; inspect/edit/delete; resolve conflicts. Do not save all chats or datasets as memory.
Phase 6: reproducible setup, dependencies locked after clean installation, honest AI-assistance disclosure, demo and public repository.
Phase 7: user walkthrough and interview practice.

## Boundaries
Initial format: comma-separated UTF-8 CSV with a header. Proposed limits: 10 MiB and 100,000 rows; implement enforcement in Phase 2. No XLSX in the initial scope. No accounts, cloud sync or autonomous code execution. Dataset stays in the Python session; the future hosted model will receive explicitly documented schema and bounded tool results. Use synthetic or public data for demonstrations.

## Module plan (future files, not implemented)
app.py: UI only; dataset.py: parsing and validation; tools/: five analysis operations; agent.py: bounded orchestration; providers/gemini.py: API boundary; memory.py: SQLite; tests/: independent expected values and failures.

## Design decisions
Python 3.11 recommended for Windows. Streamlit for a small explainable UI, pandas for computation, SQLite standard library for later memory. Gemini selected as initial API provider. Account availability, quota, cost and exact model remain unverified; no free-tier guarantee. No provider SDK until Phase 3. No key required for Phase 1.

## Phase 2 checkpoint
CSV validation, all five tools, manual UI and structured JSON results are implemented. 26 tests pass in the build environment. Pending: Windows acceptance and Phase 3 actual model integration. Module layout deliberately kept to app.py and engine.py at this scale. Python 3.13 used by user; 3.12 in build environment.
