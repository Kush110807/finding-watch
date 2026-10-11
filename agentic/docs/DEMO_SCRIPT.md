# Finding Watch — short BYTE demo script (approximately 2–3 minutes)

**Preparation:** Use the bundled synthetic `demo_sales.csv` and a private local Gemini configuration with a model that has already demonstrated working function calls. Confirm recording software hides the `.env` file, model-list raw output, IDE environment variables and any real user data. Capture the running app, not mocks. If Gemini is unavailable, label recorded AI sections as previously captured, or omit them; do not fake tool calls.

**0:00–0:20 — The problem and start.** “Finding Watch lets me ask descriptive questions about a CSV, see the exact calculation, and test how a finding changes under one condition.” Click **Try an example**; show the dataset name, four records and five columns. Mention it also accepts a suitable unfamiliar CSV.

**0:20–0:55 — Custom Gemini tool selection.** Open **Gemini connection and consent** and explain what is sent. With consent on, type a *custom*, supported question not populated by local suggestions: “Compare total revenue by category in this dataset. Use the revenue column and a total, not order counts.” Click **Analyse**. Show the real tool trace in the collapsed evidence only briefly: `grouped_summary` selected and Python returns Coffee 3,000; Snacks 1,400. If the model chooses other tools, show the actual trace accurately; do not claim it chose `grouped_summary` if it did not.

**0:55–1:20 — Clarification.** Ask “Which category performed best?” Gemini should request a meaning; show that the original question remains and grouping/measure choices are not silently selected. Explicitly choose category and total revenue (or give a contextual answer if appropriate); submit. The calculated result should still come from Python evidence. Explain that record counts and units could answer different questions.

**1:20–2:15 — Challenge.** Under the submitted grouped result, click **Test another condition**. Explain: “This doesn't edit the original answer. It asks what happens when only North records are included.” Explicitly choose **Add condition → region → is → North**. Click **Review comparison**; show original versus alternative before computation. Click **Confirm and compare**. From the bundled example expect: all records Coffee 3,000 and Snacks 1,400; North Coffee 1,200 and Snacks 800; Coffee remains leader. Note that the row counts change from four to two.

**2:15–2:40 — Reproducibility.** Expand **How this was calculated / How this was compared**: point out dataset identity, executed specification, counts, missing-value rules and JSON download. Collapse it again. Explain that the exact integer evidence belongs to the deterministic engine, while Gemini's wording is model commentary.

**Closing (10 seconds).** “Five different tools handle schema inspection, record filtering, grouped summaries, time trends and correlation. No arbitrary generated code executes. This is one BYTE Basic Agentic Task. Persistent memory and Revisit are future ideas, not features I'm claiming to have built.”

## Alternate shorter local-only demo

If live Gemini is rate-limited at demonstration time, still show **Try an example → suggested category revenue → Analyse → Test another condition → review → confirm → evidence download**. State explicitly that the custom Gemini inference could not be verified *in that particular recording*; include a separately labelled previously recorded real Gemini run if available. A model list or mock is never a substitute for live tool calls.
