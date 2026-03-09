"""Configuration GPU pour browser_use."""

# torch import déplacé dans les fonctions (lazy loading)
from typing import Any

GPU_CONFIG = {
    "gpu_enabled": True,
    "device": "cuda:0",
    "headless": True,
    "gpu_memory": 4096,
    "window_size": "1920x1080"
}

def get_gpu_config() -> dict[str, Any]:
    """Retourne la configuration GPU."""
    return GPU_CONFIG

def setup_gpu():
    """Configure le GPU pour browser_use."""
    import torch  # Lazy loading
    if GPU_CONFIG["gpu_enabled"] and torch.cuda.is_available():
        device = torch.device(GPU_CONFIG["device"])
        torch.cuda.set_device(device)

        # Configure memory
        if "memory_fraction" in GPU_CONFIG:
            torch.cuda.set_per_process_memory_fraction(GPU_CONFIG["memory_fraction"])

        print(f"🚀 GPU activé pour browser_use: {torch.cuda.get_device_name(device)}")
        print(f"📊 Mémoire GPU: {torch.cuda.get_device_properties(device).total_memory / 1024**3:.1f} GB")
        return device
    else:
        print("⚠️  GPU désactivé ou non disponible - utilisation CPU")
        return torch.device("cpu")

def get_gpu_info() -> dict[str, Any]:
    """Retourne les informations GPU."""
    import torch  # Lazy loading
    if torch.cuda.is_available():
        info = {
            "count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "devices": []
        }

        for i in range(torch.cuda.device_count()):
            info["devices"].append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "memory_total": torch.cuda.get_device_properties(i).total_memory,
                "memory_allocated": torch.cuda.memory_allocated(i),
                "memory_free": torch.cuda.get_device_properties(i).total_memory - torch.cuda.memory_allocated(i)
            })

        return info
    else:
        return {"count": 0, "devices": []}

# Fonctions spécifiques à browser_use
def browser_use_gpu_setup():
    """Configuration GPU spécifique à browser_use."""
    setup_gpu()
    # Configuration spécifique ici
