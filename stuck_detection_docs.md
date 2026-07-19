# Stuck Detection Mechanism Documentation

The Stuck Detection System (Phase 8) is a deterministic, background safety net designed to automatically identify when a learner is struggling and offer proactive assistance via Rocky.

Unlike the AI-driven "Live Tutor," which attempts to infer the learner's cognitive state using a language model when they pause typing, the Stuck Detection System is purely math-based. It evaluates a mathematical "stuck score" using concrete events from the learner's session.

## 1. When is the check triggered?

The stuck score is computed and checked in real-time immediately following two specific actions:

1. **After Code Execution:** Every time a learner clicks "Run Code" (`POST /execution/run`), the frontend fetches the updated stuck score.
2. **After Event Ingestion:** As a learner works, their editor events (typing pauses, file switches) are batched and sent to the backend. The backend triggers a background task (`check_stuck_score`) to silently evaluate the score after these batches are ingested.

> [!NOTE]
> The system is designed to be unobtrusive. It relies on the frontend explicitly polling the `GET /sessions/{id}/stuck-score` endpoint after executions to decide whether to drop down the stuck banner.

## 2. The Stuck Signals

The backend calculates the stuck score by averaging four distinct signals. Each signal produces a value between `0.0` and `1.0`.

### A. Consecutive Failures (`sig_failures`)
Tracks how many times the learner has run their code and received a non-zero exit code (a crash or syntax error) in a row.
* **Calculation:** `min(failed_streak / 3.0, 1.0)`
* **Maxes out:** After 3 consecutive failed runs (score = 1.0)

### B. Hint Rate (`sig_hints`)
Measures reliance on the progressive hint system relative to how often they run code.
* **Calculation:** `hint_rate = total_hints / max(total_runs, 1)`
* **Signal:** `min(hint_rate / 2.0, 1.0)`
* **Maxes out:** When a user averages 2 hints per execution run.

### C. Inactivity Gap (`sig_inactivity`)
Detects if a user has stopped typing for an extended period, often known as the "deer in headlights" pattern.
* **Calculation:** `min(last_pause_ms / 60_000.0, 1.0)`
* **Maxes out:** If the most recent editor event shows a typing pause of 60 seconds or more.

### D. Repeated Edits (`sig_edits`)
Identifies "spinning wheels" behavior where a learner makes many small edits to the exact same file and function without achieving a successful run.
* **Calculation:** `1.0` if the last 5 events were in the exact same function/file AND the current streak is failing. Otherwise `0.0`.
* **Maxes out:** Instantly triggers a 1.0 if the condition is met.

## 3. The Threshold

The final stuck score is the **unweighted average** of the four signals.
```python
score = (sig_failures + sig_hints + sig_inactivity + sig_edits) / 4
```

> [!IMPORTANT]
> The threshold for being considered "stuck" is **`0.25`**. 

This means a total combined signal sum of **1.0** is required to trigger the banner. 

**Common Trigger Scenarios:**
* **3 Consecutive Failures:** `1.0 (failures) / 4 = 0.25` (Instantly triggers)
* **2 Failures + 20s Pause:** `0.66 (failures) + 0.33 (inactivity) = 1.0 / 4 = 0.25` (Triggers)
* **1 Failure + 5 Repeated Edits:** `0.33 (failures) + 1.0 (edits) = 1.33 / 4 = 0.33` (Triggers)

## 4. Interaction with Dismissal Locks

If a user dismisses Rocky (either from a Live Nudge or the Stuck Banner), the system sets a **2-minute suppression lock** (`dismissed_until`) in Redis.

During this lock period, the `GET /stuck-score` endpoint will instantly return a score of `0.0` with `is_stuck = False`, regardless of how many times the code fails. This ensures Rocky does not nag the user repeatedly for the same stuck episode.
