"""OpenManus - Intelligent web automation agent.

Provides web automation using Playwright and LLM guidance for:
- Intelligent web navigation
- AI-powered data extraction
- Form filling with validation
- Screenshot capture
- VM sandbox execution for isolation

Components:
- OpenManusAdapter: Main agent for web automation
- VMSandboxAdapter: Isolated VM-based execution
- VMMonitor: VM health and performance monitoring
- VMSandboxAPI: API for VM sandbox management
"""

from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter


# Lazy imports for optional components
def __getattr__(name: str):
    """Lazy import for optional components."""
    if name == "VMSandboxAdapter":
        from src.infrastructure.agents.openmanus.vm_sandbox_adapter import VMSandboxAdapter

        return VMSandboxAdapter
    elif name == "VMMonitor":
        from src.infrastructure.agents.openmanus.vm_monitor import VMMonitor

        return VMMonitor
    elif name == "VMSandboxAPI":
        from src.infrastructure.agents.openmanus.vm_sandbox_api import VMSandboxAPI

        return VMSandboxAPI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OpenManusAdapter",
    "VMSandboxAdapter",
    "VMMonitor",
    "VMSandboxAPI",
]
