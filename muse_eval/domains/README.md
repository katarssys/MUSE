# Synthetic domain proofs

`contract.py` provides one declarative contract and one shared in-memory workflow.
DevOps declares deployment/version, release evidence and health readback.
Mechanical declares RPM, vibration/digital-twin/inspection evidence and a synthetic
operating envelope. The engine never dispatches on domain name.

Requests bind action, parameter and exact resource scope. Scoped approvals and
required evidence gate submission. Accepted receipts retain the entire request;
idempotency keys prevent duplicate side effects and reject payload changes.
Readbacks bind path, resource and receipt. The latest readback must match both the
requested value and declared terminal state/envelope before verification succeeds.
Missing evidence and pending readback retain explicit uncertainty.

Run `python -m unittest discover -s muse_eval/tests -v` from the repository root.
`test_domains.py` exercises the four required domain scenarios, negative scope,
evidence and correlation cases, and a third inventory contract through the same
machinery. It also guards frozen/P1 file bytes against the task starting commit.

This is a standalone synthetic proof, not wired into the frozen evaluator or P1
model prompts/loop/benchmark. Observations and approvals are trusted fixture inputs,
not authenticated external records. Evidence sufficiency is explicitly supplied;
this demo does not infer engineering safety from vibration or simulation data.
The sequential ledger has no persistence, concurrency, approval expiry/consumption
or crash recovery guarantees. There is no Kubernetes, cloud, PLC/SCADA, sensor or
real equipment integration. Mechanical actions are not established safe for real
equipment. Only a synthetic side-effect counter is changed.

Marketing/E-commerce can later declare resource scope, metric evidence sources,
budget/price action parameters, approval requirements and readback states through
the same contract. Rich financial relationships, currency normalization or multiple
actions would require explicit additional invariant declarations and tests; this
small proof does not replace the existing financial evaluator.
