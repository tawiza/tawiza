#!/usr/bin/env python3
"""
Commandes CLI pour Tawiza-V2 (Consolide)
"""

from . import (
    agents,
    annotate,
    browser,
    captcha,
    chat,
    completion_cmd,
    credentials,
    data,
    debug,
    ecocartographe,
    finetune,
    live,
    models,
    prompts,
    system,
    training,
    vm_sandbox_commands,
)

__all__ = [
    "agents",
    "debug",
    "system",
    "models",
    "captcha",
    "chat",
    "completion_cmd",
    "live",
    "annotate",
    "finetune",
    "prompts",
    "credentials",
    "vm_sandbox_commands",
    "browser",
    "data",
    "training",
    "ecocartographe"
]
