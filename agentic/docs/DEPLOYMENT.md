# Finding Watch — Streamlit Community Cloud deployment guide (prepared, not deployed)

This guide uses the **existing Streamlit app**. No hosting-oriented source changes are required for the documented root-level secrets method. The repository has not been pushed or deployed as part of release preparation.

## Current official documentation

- Deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Python dependencies: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- Hosting secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Root-level secrets as environment variables: https://docs.streamlit.io/develop/concepts/connections/secrets-management
- Sharing and private apps: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app

## Prerequisites and exact coordinates

1. Review the public repository contents/security checklist before making anything public.
2. Create/choose **your own GitHub repository**. The project source root is `byte-ml` (the folder containing `README.md` and `agentic/`). The Cloud **branch** should be `main` unless you deliberately choose another.
3. The Cloud **entrypoint path** is `agentic/app.py`, relative to that repository root. Its pinned requirements file is `agentic/requirements.txt`, beside the entrypoint, which Streamlit Community Cloud supports.
4. Create/sign in at https://share.streamlit.io/ and connect GitHub. You need admin permission to deploy from that repo. Choose **Create app → Existing app**; provide repo, branch, `agentic/app.py`.
5. In Advanced settings choose **Python 3.13** if available, matching the tested Windows configuration; otherwise confirm the pinned dependencies against a supported Python version before deploying. Community Cloud's default may differ. Do not assume builds are successful until deployment logs and browser behaviour are checked.
6. Check the deployed page using the bundled example *without any secrets*. The app should allow local suggested questions and all five advanced manual tools without Gemini. If build fails, inspect Cloud logs; never share full logs without checking for credentials/private data.

## Secret loading: why the existing loader works

`agentic/agent.py` reads `agentic/.env` via `dotenv_values`, then falls back to `os.getenv('GEMINI_API_KEY')` and `os.getenv('GEMINI_MODEL')`. Streamlit's **root-level** TOML secrets are documented as accessible as process **environment variables**. Therefore in the Cloud **Secrets** field, place the two keys at the top level, not in a nested `[gemini]` section:

```toml
GEMINI_API_KEY = "YOUR_PRIVATE_VALUE_SET_ONLY_IN_HOST_SETTINGS"
GEMINI_MODEL = "YOUR_VERIFIED_TOOL_CAPABLE_MODEL"
```

These strings are **placeholders**, never put the filled file into Git, a release ZIP, a screenshot, or a support chat. The deployed host injects root secrets into the process environment; no `st.secrets` refactor or protected-agent change is needed. The configuration loader's fallback can be checked in isolation without a live key, but actual Community Cloud startup must still be tested after deployment. The local `.env` has precedence if present; the public build deliberately must not contain it.

**No key is required for a public local-analysis demo.** If the host's Secrets field remains empty, suggested local questions and manual tools work; custom Gemini questions display the existing recovery path. Do not put an empty key placeholder into Secrets as an actual deployment configuration.

## Who pays for Gemini requests?

If you configure a Gemini key in a **public** deployed app, visitors who consent and ask custom questions can cause calls **charged against / rate-limited by the project associated with that key**, not their own accounts. The app has a bounded per-question tool loop but **does not have user authentication, per-visitor rate limiting or billing protection**. A privacy notice/consent is not an access control.

**Recommended release:** Public repository plus public Streamlit demo **without a Gemini key**, showing fully working local analysis and manual Challenge. Provide a separate short **recorded live-Gemini video** made from your private Windows configuration, including real tool calls and clarification. This avoids spending your quota on public visitors.

If evaluators need interactive Gemini access, temporarily use a **private Streamlit app with specifically invited evaluators** (Cloud Sharing supports private viewer access) or a separate restricted API project/key with monitored usage. Check current AI Studio quota and billing/spend caps before enabling, revoke or remove the deployment secret after the evaluation, and never assume a spend cap gives instant zero-overage protection. Make clear to evaluators if the public demo is local-analysis-only.

## Final launch checklist (once authorised to deploy)

- [ ] Check current build/requirements/Python compatibility in Community Cloud logs.
- [ ] With no key: example + manual tools + Challenge work; user understands Gemini is optional/unavailable.
- [ ] If a key is configured: model is actually accessible, function calling works, consent is still required, errors do not expose details.
- [ ] Dataset uploads and application session data are not presented as long-term stored; do not upload private or sensitive data to a public app.
- [ ] At desktop and ~390 px widths, inspect answer, clarification, confirmed comparison, evidence download and stale-state flow.
- [ ] Confirm any deployed URL actually opens before putting it into the submission form. Do not fabricate the URL.
- [ ] Only then add the real repository/demo link to README or submission portal if desired.
