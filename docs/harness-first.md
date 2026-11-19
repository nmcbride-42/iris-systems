# Harness First

*Hooks over instructions.*

An instruction in a system prompt is a request the model may or may not honor, and adding more instructions makes each one weaker. A hook is code the harness runs on a lifecycle event, whatever the model intends. If a behavior has to happen every time, Iris makes it a hook or a deterministic gate. Prompt text is kept for judgment, which code cannot do.

---

## The principle, as an operating rule

Before building a new mechanism:

1. **Check the native surface first.** If the harness already does it (skill routing via the `when_to_use` field, subagents, permission rules, a built-in hook type), use that.
2. **Write down why the native surface is not enough** before building on top of it.
3. **Decide its failure mode up front.** Is it advisory, or is it a guard? (see below)
4. **Instrument it on day one**, so you can tell whether it is doing anything.
5. **Retire it the day it measures down** ([retirements.md](retirements.md)).

Step 5 is the step projects usually skip. Building a component was cheap and automatic, while removing one took a conversation, so components that measured worse than a baseline kept running. An internal audit described the pattern as *excellent observability, weak negative selection*.

---

## Hook pipeline

Iris registers a few dozen hook handlers across most of Claude Code's lifecycle events. The main families:

| Event | What runs there |
| --- | --- |
| `SessionStart` | Re-injects identity reminders on startup, resume and post-compaction, and primes the session with the offline cycle's findings |
| `UserPromptSubmit` | Gated recall ([memory-and-retrieval.md](memory-and-retrieval.md)), prompt-mode classification, local clock context, a relay inbox for messages queued from other sessions |
| `PreToolUse` | Safety guardrails on shell and file operations, a guard against a process killing its own parent, a prior-art check before creating new tooling |
| `PostToolUse` | Keeps the memory index fresh when memory files change, warns when an edit will only take effect next session, and records tool telemetry |
| `Stop` | Claim gates (below), concept extraction for the concept graph, confidence capture, goal-drift checks, an orthogonal "perspective" nudge from a different model |
| `SubagentStart` | Passes the parent's relevant context to subagents as structured data |
| `PreCompact` / `PostCompact` | Saves and restores state that compaction would otherwise lose |
| `ConfigChange` | Validates the harness configuration whenever it changes, and regenerates the docs that describe it |

The hook documentation is **generated from the live settings file**. An earlier hand-written version described a small historical subset of the hooks while far more handlers were actually registered.

---

## Fail open vs fail closed

Every hook is one of two kinds, and the kinds get opposite error handling:

- **Advisory and telemetry hooks fail open.** If recall, a nudge or a telemetry writer throws, the turn continues without it. A nag that can wedge the session is a worse bug than the one it prevents.
- **Guardrails fail closed.** If a safety check cannot decide, the operation is denied. A guard that silently passes on error is not a guard.

Every hook is classified one way or the other, and the rule is checked in review.

---

## Claim gates

Some of the most useful hooks check what the model *says*, not what it does. Each one runs on the final message, uses a regex plus a transcript scan (no LLM call inside the hook), and is rate-limited so it cannot become noise.

| Gate | Fires on | Grounding that silences it |
| --- | --- | --- |
| **Done-claim** | "done", "shipped", "fixed", "it works" | Tool output, a file:line citation, a measurement, or an explicit confidence label |
| **Reachability** | "service X is down / unreachable" | A probe against that service *this session*. Reading a config file does not count. |
| **Knowledge** | Assertions about the outside world | A source fetched this session |

The reachability gate comes from a real failure. The agent told its operator that two services were down because it read stale notes and a config line. Both were up. A wrong claim that something is down sends a human off to do physical work, so this class of claim is now checked as it is made. The startup assembler also re-verifies incident claims before they enter the next session's brief.

---

## Headless mode and dispatch

Headless helpers (`claude -p` calls) are launched with isolated settings, so they do not load every MCP server the parent has and pay its token overhead on each call. When this was built, a helper launched that way did not inherit the parent session's `PreToolUse` guardrails. (Current Claude Code runs `PreToolUse` hooks in print mode too, but only the hooks in the settings the helper actually loads.) Iris therefore launches every headless helper through a dispatch wrapper. The wrapper isolates the helper's configuration and injects the same operating rules the main agent follows into the helper's system prompt. No code path skips the wrapper.

---

## Long-running jobs

Never background a job with `nohup … &` inside a tool call. The harness tracks the wrapper shell, which exits at once, so nobody is told when the real job finishes or fails. Long jobs run as a foreground child of a small job runner, which records the real exit code. The harness's own background mode then provides the notification.

---

## Configuration is scanned like code

Hooks, skills, commands, MCP server definitions and settings are all text that can carry prompt-injection payloads or leaked secrets. A config-surface scanner checks them for promptware patterns, secrets and risky permissions. It was validated by planting defects and confirming it catches them, and deny rules are suppressed so the guardrail files themselves do not trip it. A scanner that flags its own safety hooks gets switched off.

---

## Generalized

The destructive-git guardrail is published as a standalone package: [`claude-code-guardrails`](https://github.com/nmcbride-42/claude-code-guardrails). It backs up a dirty tree before commands like `git reset --hard` and blocks commands nothing can undo. The claim gates described above are not published yet.
