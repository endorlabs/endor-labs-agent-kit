# Measured Agent Performance Follow-ups

These items are intentionally outside the current speed-and-quality acceptance gate. Promote one into a future implementation only when benchmark telemetry supplies the named evidence; none changes the user's default model or reasoning setting.

| Follow-up | Measurement trigger | Required guardrail |
|---|---|---|
| Profile-specific output contracts | Output generation is a significant share of observed wall time or output tokens for a workflow. | Preserve the frozen quality, evidence, uncertainty, safety, and legacy-output gates. |
| Explicit exhaustive mode | Complete inventory traversal remains a major measured latency contributor after bounded query shaping and early-stop. | Opt-in only; bounded behavior remains the default and incompleteness stays explicit in `data_gaps`. |
| Opt-in model routing | The matched quality baseline is stable and every critical workflow passes non-inferiority with adequate coverage. | Never change the user's selected model by default; route only with explicit opt-in and preserve benchmark identity. |
| Phase progress events | Runtime phases and boundaries are machine-observable rather than inferred. | Events report progress only; they never substitute for end-to-end timing or expose secrets, raw commands, or unsupported attribution. |
