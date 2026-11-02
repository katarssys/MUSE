from .loop import ModelAgent
from .prompts import MUSE_SYSTEM

class MuseModelAgent(ModelAgent):
    version = "MUSE_MODEL_ADAPTER_P1"
    system_prompt = MUSE_SYSTEM
