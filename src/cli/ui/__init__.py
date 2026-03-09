"""
CLI UI Components - Beautiful terminal interface

This module provides elegant, themed UI components for the CLI:
- Themes (cyberpunk, minimal, ocean, sunset, matrix, dracula, nord, solarized)
- Formatters (tables, trees, charts, diff, json)
- Interactive components (prompts, menus, progress)
- Animations and visual effects
- Algorithmic art (fractals, procedural patterns)
- Professional animations (spinners, transitions, effects)
- Contextual icons (command-specific, status indicators)
- Visual effects (gradients, glow, neon)
"""

# Core components
# Animations
from .animations import (
    # New breathing mascot animations
    BreathingMascot,
    CustomSpinners,
    MascotProgressBar,
    MascotSpinner,
    MatrixProgressBar,
    NeonProgressBar,
    ParticleEffects,
    ProgressAnimations,
    TextAnimations,
)

# Algorithmic art
from .ascii_art import (
    BannerArt,
    FractalArt,
    MatrixRain,
    ProceduralPatterns,
    show_julia_set,
    show_mandelbrot,
    show_matrix_rain,
    show_spiral,
    show_wave_pattern,
)
from .components import Panel, Progress, Spinner

# Visual effects
from .effects import (
    AnimatedEffects,
    BoxDecorations,
    ColorGradient,
    GlowEffect,
    TextStyling,
)
from .formatters import (
    ChartFormatter,
    JsonFormatter,
    PanelFormatter,
    TableFormatter,
    TreeFormatter,
    create_stars,
    format_number,
)
from .gpu_monitor import GPULocation, GPUMonitor, GPUStatus, get_gpu_status

# Icons
from .icons import (
    CommandIcons,
    IconManager,
    Icons,
    IconSet,
    command_icon,
    get_icon_manager,
    icon,
    status_icon,
)
from .interactive import FilePicker, InteractiveForm, InteractiveMenu, InteractivePrompt

# Mascot
from .mascot import (
    get_detailed_mascot,
    get_mascot,
    mascot_says,
    mini_mascot,
    print_banner,
    print_mascot,
    print_welcome,
)

# Mascot system components
from .mascot_config import MascotConfig, MascotStyle
from .mascot_gpu_widget import MascotGPUWidget
from .mascot_hooks import (
    contextual_mascot,
    inline_error,
    inline_success,
    loading_mascot,
    on_error,
    on_first_run,
    on_long_task_end,
    on_long_task_start,
    on_startup,
    on_success,
    show_random_tip,
)
from .mascot_library import MascotFaces, get_mascot_for_style
from .theme import Theme, get_theme, list_themes

__all__ = [
    # Core
    "Theme",
    "get_theme",
    "list_themes",
    "TableFormatter",
    "TreeFormatter",
    "ChartFormatter",
    "JsonFormatter",
    "PanelFormatter",
    "create_stars",
    "format_number",
    "Panel",
    "Progress",
    "Spinner",
    "InteractivePrompt",
    "InteractiveMenu",
    "FilePicker",
    "InteractiveForm",

    # Art
    "FractalArt",
    "ProceduralPatterns",
    "MatrixRain",
    "BannerArt",
    "show_mandelbrot",
    "show_julia_set",
    "show_matrix_rain",
    "show_wave_pattern",
    "show_spiral",

    # Animations
    "CustomSpinners",
    "TextAnimations",
    "ProgressAnimations",
    "NeonProgressBar",
    "MatrixProgressBar",
    "ParticleEffects",
    "BreathingMascot",
    "MascotSpinner",
    "MascotProgressBar",

    # Icons
    "Icons",
    "IconManager",
    "IconSet",
    "CommandIcons",
    "icon",
    "command_icon",
    "status_icon",
    "get_icon_manager",

    # Effects
    "ColorGradient",
    "GlowEffect",
    "BoxDecorations",
    "TextStyling",
    "AnimatedEffects",

    # Mascot
    "print_mascot",
    "print_welcome",
    "print_banner",
    "mascot_says",
    "get_mascot",
    "get_detailed_mascot",
    "mini_mascot",
    "on_first_run",
    "on_startup",
    "on_success",
    "on_error",
    "on_long_task_start",
    "on_long_task_end",
    "show_random_tip",
    "loading_mascot",
    "inline_success",
    "inline_error",
    "contextual_mascot",

    # Mascot system
    "MascotConfig",
    "MascotStyle",
    "get_mascot_for_style",
    "MascotFaces",
    "GPUMonitor",
    "GPUStatus",
    "GPULocation",
    "get_gpu_status",
    "MascotGPUWidget",
]
