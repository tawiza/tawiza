"""Configuration système pour la mascotte Tawiza."""

from enum import Enum, StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel


class MascotStyle(StrEnum):
    KAWAII = "kawaii"
    CYBERPUNK = "cyberpunk"
    MINIMAL = "minimal"
    NEON = "neon"
    RETRO = "retro"


class MascotConfig(BaseModel):
    """Configuration de la mascotte."""

    style: MascotStyle = MascotStyle.KAWAII
    name: str = "Neko"
    color: str = "magenta"
    animations: bool = True
    sound_effects: bool = False
    expressions_enabled: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "MascotConfig":
        """Charge la configuration depuis un fichier YAML."""
        if path is None:
            path = Path("configs/mascot.yaml")
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Sauvegarde la configuration."""
        if path is None:
            path = Path("configs/mascot.yaml")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Convert enum to string for YAML serialization
        data = self.model_dump()
        data["style"] = self.style.value
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
