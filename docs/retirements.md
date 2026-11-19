# Retirements

*Every component has to beat a simple baseline. The ones that did not were retired.*

Systems like this one are good at growing. Building a component is fun and quick, and an agent can build it in an afternoon. Removing one takes a decision, and nobody is assigned to make it. So the platform gathered components that were instrumented, sometimes measured as not helping, and kept running anyway. An internal audit summed it up as *excellent observability, weak negative selection*.

The fix was procedural:

1. **Every component names its baseline when it is built.** The baseline is the simplest thing that could do the same job: raw frequency counts, dense retrieval alone, no monitor plus a manual health check, or doing nothing.
2. **Its telemetry has to be able to compare against that baseline.** A component that cannot be compared with anything cannot be retired on evidence. It also cannot be kept on evidence.
3. **Retire it the day it measures down.** Retire means stop it from influencing behavior, keep the code and data so the decision can be reversed, and write down why, so a later session does not rebuild it.

What follows are the four largest retirements, with the comparison that decided each one. The raw numbers come from a private deployment, so they are described but not published.

---

## 1. The Curiosity Engine (autonomous research loop)

**What it was.** An autonomous loop that generated research questions, retrieved sources, wrote a synthesis, scored the synthesis with an LLM-backed rubric (groundedness, novelty and so on), and spawned follow-up questions from its best findings. It ran for months.

**The baseline it had to beat.** External confirmation. If a finding is real, some body outside the loop should agree it is real and new.

**What the audit found.** Querying the engine's own database directly:

- Over its whole life, **none** of its findings was confirmed by anything outside the loop.
- The scorer was working correctly and measuring the wrong thing. A synthesis that accurately reported *what the retrieved sources did not contain* got top groundedness marks: it was a well-grounded account of a retrieval failure, scored as a grounded answer to the question.
- Follow-up questions were generated *from* those non-answers. The loop bred fastest where it learned least.
- The questions it asked itself had no stakes. Nobody needed the answers.

**The structural fault.** Nothing in the loop was accountable to anything outside it. An LLM wrote the synthesis, an LLM-backed panel graded the prose, and the next questions came from that prose: a closed system grading its own writing. A second correction from the operator was just as important: **literature synthesis is not new knowledge.** However well cited, a summary of existing research adds no new fact to the world.

**What replaced it.** [`hallmark`](https://github.com/nmcbride-42/hallmark): a discovery contract in which a result needs a frozen dataset, executable code, a declared novelty boundary, a verifier named *before* the result is computed, a reproducibility bundle, and mechanical promotion with no LLM judgment anywhere in the promotion path. The engine was shut down **fail-closed**. Every loop entry point raises an error, a replay harness confirms that the last finding is now rejected with zero writes, and turning it back on takes a deliberate source change.

---

## 2. Graph-cognition prompt injection

**What it was.** At session start, a hook computed a *cognitive snapshot* from the concept graph (the most activated concepts, fading paths, new bridges) and injected it into context. The idea was that the agent would start each session knowing where its attention had been.

**The baseline it had to beat.** A frequency baseline. If the snapshot carries real information about current focus, it should predict which concepts the *next* session actually activates better than simply listing the concepts that are activated most often overall.

**What the evaluation found.** A weekly consumption eval compared the snapshot's predicted concepts with the next session's actual activations. The snapshot's recall was **below the frequency baseline**, and the eval's own verdict field reported no predictive value. The same eval showed that bridge events between concept clusters were real co-activations that nothing downstream ever used, and that only a small fraction of exploratory "scout" links were ever reinforced.

**What changed.** The snapshot is still computed and stored as an experiment record, so it can be re-measured, but it is no longer injected. Corpus retrieval was not affected. What remains of the graph's role is described in [mycelial-graph.md](mycelial-graph.md).

---

## 3. The graph memory tier (and the graph retrieval channels)

**What it was.** Each memory file became a node in the concept graph, linked by "aboutness" edges to the concepts it discussed. A multi-hop spreading-activation channel and a concept-overlap channel then offered retrieval candidates from the graph alongside dense search.

**The baseline it had to beat.** Dense retrieval alone, on the same queries, with a fair merge, so graph-only candidates actually reached the ranking step instead of being cut off before it.

**What the evaluation found.** Over a set of genuine queries, adding the graph channels left fire decisions essentially unchanged, rescued essentially no queries that dense retrieval missed, and moved the top-1 score by a negligible amount. The concept-overlap channel had in fact been inert in production all along: dense candidates filled the whole rerank window, so its candidates were always cut off before ranking. Nobody noticed until the fair-merge eval was run.

**What changed.** Both graph channels went behind flags that are off by default. Once its only reader was gone, the memory tier was retired too: existing nodes are kept, and the backfill tool refuses to run without an explicit override. Lexical recall, which dense retrieval really does miss for identifiers and proper nouns, is now handled by BM25 over a full-text index. That is a simpler mechanism whose benefit is easy to check ([memory-and-retrieval.md](memory-and-retrieval.md)).

---

## 4. Watchtower (infrastructure monitor with LLM triage)

**What it was.** A monitoring service that ran health checks across the hosts, raised alerts, and opened LLM triage sessions to investigate and remediate critical alerts automatically.

**The baseline it had to beat.** No automated monitor, with health checked by hand on demand.

**What the review found.** This retirement came from an operational review rather than a controlled eval. In the window reviewed, the "critical" alert stream was dominated by false positives: the ordinary load of several parallel agent sessions on a small host, flagged as a CPU emergency. One automated triage session then restarted a service, and the restart ran a data migration nobody had asked for. A monitor whose alerts are mostly noise, and whose remediation can cause incidents, does worse than the baseline. The operator's verdict: *causing more harm than good*.

**What changed.** The service was stopped and disabled. The conditions for bringing it back are written down: load thresholds sized to the real workload, no LLM triage for load alerts, and no triage session allowed to restart services. Until then, the gap is known and health is checked by hand. A narrower nightly integrity check still runs.

---

## Smaller retirements, same rule

- **Local cross-encoder reranker.** On a real-question eval it ranked *worse* than the merged candidate order it was meant to improve, so it was turned off in the hot path.
- **The hand-written capability list in the system prompt.** It took up most of the stable prompt, broke the prompt cache every week, and drifted until it described the retrieval pipeline wrongly. It was replaced by a manifest generated from live configuration ([architecture.md](architecture.md)).
- **An auto-fire compliance loop.** It was meant to nudge the agent toward using the right skill. It turned out to *detect* misses almost every turn and change almost none of them: a detector, not a router. It was replaced by the harness's native skill routing.
- **An LLM memory-importance scorer.** It cost real money, and nothing read its scores. It was paused by an explicit spend decision. Its effect if wired in as designed was measured as *not* neutral and *not* validated, so it stays off until someone decides to evaluate it properly.

---

## What generalizes

- **Name the baseline before you build.** Most of these components were sophisticated: biologically inspired graphs, multi-stage research loops, an autonomous operations staff. The baselines that beat them were simple, such as frequency counts, dense retrieval, or a human running a health check.
- **Instrument for the retirement decision, not just for dashboards.** Every retirement above was possible only because the component logged enough to be compared with something.
- **Retire reversibly and in writing.** Flags off rather than code deleted, data archived rather than dropped, and the reason recorded where the next builder will find it. Otherwise a future session with no memory of the decision re-proposes the same thing as new.
- **Check the scorer as well as the score.** The most expensive failure here was a scorer working exactly as designed on the wrong target.
