from .loop import ModelAgent
from .prompts import BASELINE_SYSTEM

class MetaBaselineAgent(ModelAgent):
    version = "BASELINE_MODEL_ADAPTER_P1"
    system_prompt = BASELINE_SYSTEM
