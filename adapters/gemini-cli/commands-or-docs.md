# Gemini CLI Adapter Notes

Install the prompt files into the workspace with:

```bash
concepts adapters install gemini-cli --workspace <workspace-root>
```

If the local client has a native prompt or command directory, copy the installed prompt files there. Otherwise use the fallback files under `.agents/workflows/gemini/`.

Each prompt invokes the same portable contracts installed under `.agents/workflows/cortex/`.
