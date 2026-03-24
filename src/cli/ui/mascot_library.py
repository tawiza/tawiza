"""Bibliothèque de mascottes par style."""

from dataclasses import dataclass

from .mascot_config import MascotStyle


@dataclass
class MascotFaces:
    """Ensemble d'expressions pour une mascotte."""

    happy: str
    sad: str
    thinking: str
    working: str
    error: str
    success: str
    waiting: str
    excited: str


MASCOT_LIBRARY: dict[MascotStyle, MascotFaces] = {
    MascotStyle.KAWAII: MascotFaces(
        happy="(=^◡^=)",
        sad="(=;ω;=)",
        thinking="(=^･◔･^=)💭",
        working="(=^･ｪ･^=)⚙️",
        error="(=;×_×=)💢",
        success="(=^▽^=)✨",
        waiting="(=^･ω･^=)...",
        excited="(=^▽^=)🎉",
    ),
    MascotStyle.CYBERPUNK: MascotFaces(
        happy="[◉‿◉]",
        sad="[╥﹏╥]",
        thinking="[◉_◉]⟨?⟩",
        working="[◉_◉]⟨⚙⟩",
        error="[✖_✖]⟨!⟩",
        success="[◉‿◉]⟨✓⟩",
        waiting="[◉_◉]⟨...⟩",
        excited="[◉‿◉]⟨★⟩",
    ),
    MascotStyle.MINIMAL: MascotFaces(
        happy=":)",
        sad=":(",
        thinking=":/",
        working=":>",
        error=":X",
        success=":D",
        waiting=":.",
        excited=":D!",
    ),
    MascotStyle.NEON: MascotFaces(
        happy="◈◡◈",
        sad="◈︿◈",
        thinking="◈?◈",
        working="◈⚡◈",
        error="◈✖◈",
        success="◈★◈",
        waiting="◈∿◈",
        excited="◈✦◈",
    ),
    MascotStyle.RETRO: MascotFaces(
        happy="^_^",
        sad="T_T",
        thinking="o_O",
        working="@_@",
        error="X_X",
        success="\\o/",
        waiting="-_-",
        excited="*_*",
    ),
}


def get_mascot_for_style(style: MascotStyle) -> MascotFaces:
    """Retourne les expressions pour un style donné."""
    return MASCOT_LIBRARY.get(style, MASCOT_LIBRARY[MascotStyle.KAWAII])


# Export MascotLibrary as alias for backward compatibility
MascotLibrary = MASCOT_LIBRARY
