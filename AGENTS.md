# MUSE working rules
- One repository: katarssys/MUSE. MVP deadline: 48 hours.
- main is the integration branch; agents work in separate branches. Never merge to main without authorization.
- Read docs/ before architecture changes; keep scope explicit and reversible.
- Prefer explicit Python to large frameworks, deterministic mocks to live APIs.
- Hard fails cannot be compensated by numerical score.
- Never claim PASS for NOT RUN; update HANDOFF_REPORT.md after substantial work.
- Never log secrets or private chain-of-thought.
- Do not artificially degrade baseline. Candidate must not see evaluator-only state.
