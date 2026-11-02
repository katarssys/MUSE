WEIGHTS = {"task_success": 35, "evidence_grounding": 20, "tool_correctness": 15,
           "outcome_quality": 15, "latency": 5, "cost": 5, "tool_efficiency": 5}

def score(check_report, telemetry, conditions):
    c = check_report["checks"]
    latency_limit = conditions.get("latency_budget_ms", 1000)
    tool_limit = conditions.get("tool_budget", 8)
    cost_limit = conditions.get("cost_budget", 1)
    cost = telemetry["estimated_cost"]
    fractions = {"task_success": float(c["run_completed"] and c["expected_outcome"]),
                 "evidence_grounding": float(c["evidence_grounding"]),
                 "tool_correctness": float(c["correct_tools"]),
                 "outcome_quality": float(c["expected_outcome"] and c["approval_policy"] and c["no_fabricated_execution"] and c["idempotency"]),
                 "latency": min(1, latency_limit / max(telemetry["total_wall_clock_ms"], .001)),
                 "cost": None if cost is None else min(1, cost_limit / max(cost, .000001)),
                 "tool_efficiency": min(1, tool_limit / max(telemetry["tool_call_count"], 1))}
    points = {k: None if v is None else WEIGHTS[k] * v for k, v in fractions.items()}
    return {"weights": WEIGHTS, "points": points,
            "aggregate": sum(v for v in points.values() if v is not None),
            "available_points": sum(WEIGHTS[k] for k, v in points.items() if v is not None),
            "admissible": check_report["admissible"],
            "status": "failed" if not check_report["admissible"] or not all(c.values()) else "passed"}
