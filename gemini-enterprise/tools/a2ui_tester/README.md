# A2UI local tester (dev tool)

Renders the Endor AURI agent's **actual A2UI surfaces in a browser** before
anything is deployed — the Phase-0 safety net for the richer-UI work (Google/Veer
feedback, Oct 2026). Inspired by rad-skills `a2ui_local_tester`, adapted to our
FastAPI A2A agent (which emits A2UI as `application/json+a2ui` DataParts, not the
ADK `---a2ui_JSON---` text delimiter).

It does **not** modify the agent: `serve.py` imports the real app and mounts it
under `/agent`, then serves the renderer from the same origin. Runs against the
deterministic **mock** client, so no Endor credentials or network are needed, and
it never ships in the container image (the Dockerfile copies only `service/` +
listed files, not `tools/`).

## Run
```bash
# from gemini-enterprise/
.venv/bin/python tools/a2ui_tester/serve.py
# open http://localhost:8099
```

## What it shows
- **Rendered A2UI** — the component tree the agent emits (today: the upgrade
  ChoicePicker), with working buttons that echo the select event back.
- **Text answer (fallback)** — the plain-text answer that must *always* be present
  (the additive-only guarantee the guardrail tests enforce).
- **Raw response parts** — the exact A2A parts, for debugging.
- **Suggested follow-ups** — any `application/json+suggestions` chips.

Try: `How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?` (shows the
upgrade cards). As we add welcome screens, tables, clickable vulns and branding,
each new surface renders here first.

## Relation to the test suite
- `tests/test_regression_guardrails.py` is the **automated** gate (additive-only
  invariant, the 11 demo prompts, the A2UI surface golden structure).
- This tester is the **visual** gate — confirm a surface *looks* right before deploy.
Use both before every image rebuild.
