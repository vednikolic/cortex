# Routing Reference

Route by scope, not by where the conversation happened.

- Concrete work completed today or next actions: daily note.
- Project-specific decision, current status, deployment state, friction log entry, or continuity rule: project context.
- Project-specific reusable execution pattern with proof: project playbook.
- User trait, durable communication preference, or personal operating pattern: personal learnings.
- Cross-project pattern, tool behavior, or workspace-wide rule candidate: workspace memory.
- Canonical-source, prompt hierarchy, or agent contract change: relevant agent instruction file.

Strict test for personal learnings: if the entry names a project, file, command flag, commit, regex, tool bug, phase or task identifier, dated implementation proof, weighed options list, `Rule:` clause, or skill update candidate, route it to project context, project playbook, or workspace memory instead.

If the entry belongs in a project playbook that does not exist yet, create the playbook with a table of contents and a first section. Do not park the entry in personal learnings with a TODO.

Reframed workflow patterns: when an entry describes a workflow pattern such as plan chunking, phase gates, or audit prompts but is framed as "user prefers X", strip the framing and route it to the project playbook or a skill update candidate.

Active project status belongs in project context or a generated brief, not in workspace memory.
