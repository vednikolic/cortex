# Examples and Scenarios

Used by `/save` Step 4 (pattern and signal detection) and Step 9 (rule promotions). Read when you need concrete anchor examples for cross-project signal types or promotion escalation shapes.

## Signal scenarios

### Scenario 1: Opportunity connection

You built a retry-with-backoff wrapper in project-A this session. MEMORY.md has a mental model entry: "treat transient failures with exponential backoff." Project-B's AGENTS.md lists "flaky API calls" in its Friction Log.

Signal entry:
```
Opportunities: project-A retry wrapper maps directly to project-B flaky API friction -- reusable module candidate
```

### Scenario 2: Risk signal

You chose SQLite for local storage in project-A this session. Project-B's Decision Register says "[tentative] Use Postgres for all persistence." These assumptions conflict silently.

Signal entry:
```
Risks: project-A chose SQLite for local storage; project-B assumes Postgres for all persistence -- conflicting data layer assumptions
```

### Scenario 3: Convergence

This session you added event logging to project-A. Last week's daily notes show you added telemetry to project-B and cost tracking to project-C. All three need a lightweight event bus.

Signal entry:
```
Convergence: project-A event logging + project-B telemetry + project-C cost tracking all need a shared event bus abstraction
```

## Rule promotion shapes (Step 9)

### Normal promotion (seen 2+ times)

```
Potential root rule (AGENTS.md for universal, CLAUDE.md for Claude-specific):
  "[pattern]" -- seen N times, could be a standing rule
```

### Violated preference escalation

Step 4 flagged a `[VIOLATED]` entry -- user corrected behavior that was already documented in learnings.md or MEMORY.md. This skips the 2+ occurrence requirement. A documented preference that was not applied is already past the threshold. Surface prominently, not buried under patterns.

```
VIOLATED PREFERENCE -- immediate Rule candidate:
  "[preference text from learnings.md]" -- documented but not applied this session
  Proposed rule: [draft the rule text for root AGENTS.md if universal, CLAUDE.md if Claude-specific]
```

## What NOT to save

- **Temporary session state.** Bad: `- Currently debugging a failing test in my-app/tests/test_classify.py`. If the bug reveals a pattern, save the pattern, not the debugging step
- **File contents or code snippets.** Bad: `- Added retry logic: \`for i in range(3): try: ... except: sleep(2**i)\``. Save the file path and the decision rationale: `- Added retry with exponential backoff to API client (my-app/src/client.py)`
- **Meta-conversation.** Bad: `- User asked me to refactor the auth module and I suggested using middleware`. The refactoring outcome matters, not the conversation about it
- **Anything already captured in the target file.** If MEMORY.md already says `Use per-project venvs with Python 3.12`, do not add it again. Consolidate or update the existing entry
- **Sensitive data.** Never save credentials, tokens, secrets, or PII. Reference the secret manager or env var name instead
