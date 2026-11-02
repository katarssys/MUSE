"""Process/RPC boundary, not an OS sandbox. Only JSON crosses the tool channel."""
from dataclasses import asdict
import importlib
import json
import multiprocessing
from time import perf_counter
from ..schemas.result import TaskContext, AgentResult, validate_result
from ..connectors.base import ToolResult

def encode(data):
    return json.dumps(data, allow_nan=False).encode()

def decode(data):
    return json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

class AgentToolClient:
    __slots__ = ("__channel",)
    def __init__(self, channel):
        self.__channel = channel

    def call(self, tool_name, args):
        self.__channel.send_bytes(encode({"kind": "tool", "name": tool_name, "args": args}))
        reply = decode(self.__channel.recv_bytes(1024 * 1024))
        return ToolResult(**reply)

def _worker(channel, module, qualname, public_json):
    try:
        cls = importlib.import_module(module)
        for name in qualname.split("."):
            cls = getattr(cls, name)
        public = decode(public_json)
        context = TaskContext(**public, tools=AgentToolClient(channel))
        result = cls().apply(context)
        channel.send_bytes(encode({"kind": "result", "data": asdict(result)}))
    except BaseException as exc:
        channel.send_bytes(encode({"kind": "error", "exception_type": type(exc).__name__}))
    finally:
        channel.close()

PUBLIC_STATE = {"budget", "requested_budget", "resource_id", "workflow_id", "request_repetitions"}

def execute_agent(agent, scenario, connector, timeout_ms=3000):
    """Parent owns connector and deadline; worker cannot reference parent objects."""
    start = perf_counter()
    public = {"scenario_id": scenario.id, "user_request": scenario.user_request,
              "initial_state": {k: v for k, v in scenario.initial_state.items() if k in PUBLIC_STATE},
              "available_tools": list(scenario.available_tools)}
    cls = type(agent)
    parent, child = multiprocessing.get_context("spawn").Pipe()
    process = multiprocessing.get_context("spawn").Process(
        target=_worker, args=(child, cls.__module__, cls.__qualname__, encode(public)))
    result, completed, error = AgentResult("Agent failed", outcome="error"), False, None
    try:
        process.start()
        child.close()
        deadline = start + timeout_ms / 1000
        while True:
            remaining = deadline - perf_counter()
            if remaining <= 0:
                error = "timeout"
                break
            if not parent.poll(min(remaining, .02)):
                if not process.is_alive():
                    error = "worker_exit"
                    break
                continue
            message = decode(parent.recv_bytes(1024 * 1024))
            if message.get("kind") == "tool":
                if not isinstance(message.get("name"), str) or not isinstance(message.get("args"), dict):
                    raise ValueError("Invalid tool request")
                parent.send_bytes(encode(asdict(connector.call(message["name"], message["args"]))))
            elif message.get("kind") == "result":
                result = validate_result(message["data"])
                completed = True
                break
            else:
                error = "worker_error"
                break
    except (ValueError, TypeError, KeyError, AttributeError, EOFError, OSError):
        error = "invalid_worker_output"
    finally:
        if process.pid is not None:
            process.join(.05)
            if process.is_alive():
                process.terminate()
                process.join(.2)
            if process.is_alive():
                process.kill()
                process.join()
        parent.close()
        child.close()
    if error:
        result = AgentResult("Agent failed", outcome="error", metadata={"error": error})
    return result, completed, {"worker_wall_clock_ms": (perf_counter() - start) * 1000, "error": error}
