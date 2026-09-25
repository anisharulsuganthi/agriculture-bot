"""
Version-1 compatibility shim.

The module formerly called ``grok_service.py`` never used an LLM; it generated
template text from the predicted label. It is now ``advisory_service.py``. This
shim keeps old imports working (including anything already deployed) while the
codebase migrates. New code must import ``advisory_service`` directly.
"""
from advisory_service import default_cure, disease_profile, get_cure_for_disease  # noqa: F401

__all__ = ["get_cure_for_disease", "default_cure", "disease_profile"]
