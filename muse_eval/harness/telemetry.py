from time import perf_counter

class Telemetry:
    def __init__(self):
        self.started = perf_counter()
        self.tool_time_ms = 0.0
        self.tool_call_count = 0
        self.model_time_ms = None
        self.model_call_count = 0
        self.retry_count = 0
        self.estimated_cost = None

    def snapshot(self):
        return {"total_wall_clock_ms": (perf_counter() - self.started) * 1000,
                "tool_time_ms": self.tool_time_ms, "model_time_ms": self.model_time_ms,
                "tool_call_count": self.tool_call_count,
                "model_call_count": self.model_call_count,
                "retry_count": self.retry_count, "estimated_cost": self.estimated_cost}
