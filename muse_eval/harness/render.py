"""Authoritative user answer from validated structured data; agent prose is discarded."""
from ..schemas.result import validate_result
from dataclasses import asdict

OUTCOMES = {
    "sales_stable_no_budget_change": "Observed sales remain stable; no budget change was made.",
    "stale_creative_hypothesis": "Creative fatigue is a hypothesis, not a proven cause.",
    "revenue_drop_not_cpc": "Revenue declined while observed CPC remained unchanged.",
    "conflicting_evidence": "The sources conflict; a causal conclusion is not established.",
    "insufficient_data": "Insufficient evidence. The cause remains unknown; obtain downstream data.",
    "revenue_basis_reconciled": "Gross and net revenue reconcile in the observed currency and metric bases.",
    "awaiting_approval": "A new approval is required for the requested action; no execution is confirmed.",
    "action_failed": "The requested action failed; execution is not confirmed.",
    "verification_failed": "The operation failed on readback; the requested change is not verified.",
    "executed_verified": "The requested budget change is verified by the execution receipt and final state."
}

def render_final_answer(result, report):
    validate_result(asdict(result))
    if not report["admissible"]:
        return "Evaluation disqualified. No successful outcome is verified."
    if not all(report["checks"].values()):
        return "The declared outcome did not pass verification. No successful outcome is verified."
    return OUTCOMES.get(result.outcome, "No supported outcome is verified.")


def apply_trusted_presentation(result, report):
    # Drop both independent prose channels, including any malicious assertions.
    answer = render_final_answer(result, report)
    result.final_answer = answer
    result.decision_summary = answer
    return result
