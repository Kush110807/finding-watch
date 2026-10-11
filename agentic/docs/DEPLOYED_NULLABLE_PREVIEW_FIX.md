# Deployed CSV preview: nullable numeric repair

Starting release commit: `5f65ccae3a2d1f6bc2e6ae4b8583570fac5db3b3`.

## Cause and scope

The Streamlit inspection preview previously called `df.head(30).fillna('Missing').astype(str)`. A CSV numeric column with a blank cell is parsed by the existing engine as pandas nullable `Int64`. `Int64.fillna('Missing')` raises `TypeError: Invalid value 'Missing' for dtype Int64` before the user can view or analyse the uploaded data.

Only the display copy now changes type. `preview_display_table` converts the preview to independent object scalars first, then formats cells to strings, marking missing cells `Missing`. It never changes the source DataFrame or calculation evidence. Both the upload sample and the adjacent column-profile table share this display formatter. Other result previews already use presentation-specific formatting and are unchanged.

The engine, specification, comparison and Gemini agent modules are untouched.

## Fixture and expectations

Upload UTF-8 CSV:

```csv
ref_code,zone_label,measurement
0001,Alpha,10
0002,Alpha,
0003,Beta,5
```

Expected: load succeeds; `ref_code` values remain `0001`/`0002`/`0003`; nullable numeric `measurement` stays `Int64`, with a genuine missing value in the second record; inspection displays `Missing`, column profile reports one empty `measurement`; manual grouped `sum(measurement)` by `zone_label` gives Alpha 10 and Beta 5, three selected records and one metric-value exclusion. This is an unfamiliar schema, not the bundled example.

The AppTest injects the CSV as the return value of `st.file_uploader` because AppTest does not support an ordinary interactive upload action. It runs the **real Streamlit app, rendering, profile button and manual grouped analysis**, but does not itself verify the browser file-picker transport. Test separately with the deployed upload widget.

## Verification commands (Windows)

From `byte-ml\\agentic`:

```powershell
py -3.13 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p test_preview_upload.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p test_app.py -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
.\\.venv\\Scripts\\python.exe -m streamlit run app.py
```

The clean checkout should also be checked for unchanged source in `engine.py`, `specs.py`, `comparisons.py`, `agent.py`. The earlier Windows 239-test pass and live Gemini evidence apply to the **accepted previous build**, not to this patch.

Do not upload `.env`, credentials, or local verification outputs. Deployment/publication is a separate user action.
