# UI runtime repair — duplicate evidence widgets

## Source baseline

Start from `de1160b5e82883aef26b0ede77033218161fb0b1`.

## Changes

- `download_keys.py` declares stable per-rendering-location widget identities. A key is **never** an evidence hash: equal output objects can appear in the manual calculation, the clarified answer, and multiple places in an AI trace. Trace occurrence numbers start at 1.
- `ui_components.py` requires the render location to be supplied by the caller and passes the derived key explicitly to `st.download_button`. It does not edit downloaded JSON content.
- `app.py` identifies manual/clarified result surfaces and AI trace positions independently. Its confirmed manual/clarified Challenge immediately calls `st.rerun()` to replace pending headings and notices with the confirmed state. Existing gates and stale-result checks are unchanged.
- `tests/test_download_keys.py` checks stable, unique keys offline. `tests/test_app.py` includes the three reported Streamlit collision cases, the unchanged-JSON widget call, and post-confirmation heading assertions.

`engine.py`, `specs.py`, and `comparisons.py` have **no changes**.

## Independent verification on Windows

From `byte-ml/agentic`, after installing `requirements.txt` in a virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest tests.test_app -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The test suite mocks `agent.ask` in AppTest. No key or live Gemini request is required for collision regressions.

### Real browser checks

1. With the example dataset, run **Summarise groups** then ask Gemini a question, obtaining a grouped result; ensure both the manual and AI evidence-download buttons render without errors. If unavailable, the AppTest uses a synthetic mocked response without an API key.
2. Inspect a real tool trace containing two identical tool calls; both result cards and both downloads must display.
3. Inspect a trace containing `inspect_dataset` then `grouped_summary`; both downloads must display.
4. Confirm a manual Challenge and a clarified Challenge. On the immediate rerender, **Challenge · confirmed** must replace **Challenge · pending** and the confirmation evidence download must be present. Edit one condition; the previous completed comparison should be hidden until reconfirmed.
5. Download JSON and verify exact integer values and `null` remain unchanged.

Record the command output and actual browser screenshots, including any provider error messages (redacted) before accepting the repair. Screenshots of design mockups do **not** qualify.

## Verification boundaries

`unittest` offline tests are independent of the Streamlit runtime. Streamlit AppTest and real browser screenshots must be recorded separately; no offline key test alone proves the browser collision has been eliminated. Live Gemini is not necessary to test widget identity, and this repair does not assert a fresh live-provider result.
