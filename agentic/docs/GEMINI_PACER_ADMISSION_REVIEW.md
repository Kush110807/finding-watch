# Gemini pacing admission — focused repair handoff

## Scope and starting point

- Baseline: `a066384c1665e53088dae5e1c7dcf3dbb9b27dac` (`repair/gemini-reliability`).
- Repair branch: `repair/gemini-pacer-admission`.
- Only the process-local `RequestPacer` admission logic, its fake-clock tests, and relevant documentation changed.
- No merges, pushes, deployments, live Gemini calls or API credentials.

## Verified defect

The previous algorithm atomically **reserved future timestamps before sleeping**. A late sleeper could return after its reserved slot expired without revisiting the interval constraint. With `interval=13` and fake sleep overshooting every requested delay by 13 seconds, three sequential requests were admitted at `[0, 26, 26]` — zero spacing between requests 2 and 3.

## Repair

`RequestPacer.acquire` maintains the timestamp of the **last actual admission**, initially unset. Every caller:

1. Acquires the lock, reads monotonic time and rejects an elapsed deadline.
2. Checks whether at least `interval` seconds have elapsed since the last actual admission.
3. If eligible, records the actual admission time while holding the lock.
4. Otherwise, if the next admissible time is not before the deadline, returns `False`.
5. Releases the lock, optionally emits a waiting status, sleeps, and **repeats** the check under the lock.

No future admission is reserved, and the lock is never held during sleep. This prevents late concurrent wakeups from consuming stale reservations simultaneously. The invariant concerns admissions to the process-local scheduler, not other processes or Google's project-wide quota. All retry policy, bounds, diagnostics, safeguards and completed analytical tool handling are unchanged.

## Regression cases

- Overdue sequential wake: expected actual admissions `[0, 26, 52]` rather than `[0, 26, 26]`.
- Two concurrent waiters released late at the same time: one must rewait and the third sleep occurs; shared interval is respected.
- Deadline expiration after late sleep: returns `False` without reserving or consuming a slot; later fresh caller may proceed.
- Existing tests still cover concurrent arrivals, ordinary spacing, retry-after, 429/503/504, exhausted daily quota, non-retryable failures, and request/analysis budgets.

## Verification boundaries

Run from `agentic`:

```powershell
py -3.13 -m unittest discover -s tests -p test_provider_reliability.py -v
py -3.13 -m unittest discover -s tests -v
```

Do **not** treat offline fake-clock and SDK-shim tests as real pinned-SDK or Streamlit verification. Continue using the one previously agreed combined Windows/browser/live-provider checklist; no new live quota-consuming calls are requested for this narrow repair.

## Actual checks on this candidate (offline environment)

- Original baseline independently reproduced `[0, 26, 26]` using fake-clock oversleep.
- Focused reliability suite: **19 tests passed** (16 inherited plus 3 new).
- Focused reliability suite repeated 15 times without a failure.
- Full discovery: **195 entries, 193 passed and 2 import errors**, for missing `google.genai` and `streamlit`.
- Python source/test compilation: passed.
- Real pinned Gemini SDK mocks, Streamlit AppTests, deployed browser and live calls: **not executed**; unavailable dependencies. Previous Windows/live results are not evidence for this new commit.
