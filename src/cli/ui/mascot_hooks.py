"""Mascot hooks - Display mascot at key moments in the CLI."""

import random
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console

from .mascot import (
    mascot_says,
    mini_mascot,
    print_mascot,
    print_welcome,
)

console = Console()

# Fichier pour tracker les affichages
MASCOT_STATE_FILE = Path.home() / ".tawiza" / ".mascot_state"

# Tips aléatoires
TIPS = [
    ("tawiza models list", "Voir tous les modèles Ollama disponibles"),
    ("tawiza system status", "Vérifier l'état du système"),
    ("tawiza chat", "Discuter avec l'assistant IA"),
    ("tawiza finetune list", "Voir les jobs de fine-tuning"),
    ("tawiza mascot --gallery", "Voir toutes les mascottes!"),
    ("tawiza completion install", "Activer l'autocomplétion"),
    ("tawiza live gpu-check", "Vérifier l'état du GPU"),
    ("tawiza debug status", "Voir le statut de débogage"),
    ("tawiza quickstart", "Démarrage rapide guidé"),
    ("tawiza wizard", "Assistant de configuration"),
]

WELCOME_MESSAGES = [
    "Prêt à coder!",
    "Comment puis-je t'aider?",
    "Let's build something awesome!",
    "GPU optimisé et prêt!",
    "Bienvenue chef!",
    "À ton service!",
    "Ready to rock! 🎸",
]

SUCCESS_MESSAGES = [
    "Mission accomplie!",
    "Parfait!",
    "Excellent travail!",
    "C'est fait!",
    "Nickel!",
    "✨ Succès!",
]

ERROR_HELP = [
    "Pas de panique, on va corriger ça!",
    "Hmm, laisse-moi t'aider...",
    "Essaie 'tawiza debug status' pour plus d'infos",
    "Une erreur? Voyons ça ensemble!",
]


def _load_state() -> dict:
    """Load mascot state from file."""
    try:
        if MASCOT_STATE_FILE.exists():
            import json
            return json.loads(MASCOT_STATE_FILE.read_text())
    except:
        pass
    return {"last_shown": None, "show_count": 0, "tips_shown": []}


def _save_state(state: dict):
    """Save mascot state to file."""
    try:
        MASCOT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json
        MASCOT_STATE_FILE.write_text(json.dumps(state))
    except:
        pass


def should_show_mascot(interval_minutes: int = 30) -> bool:
    """Check if we should show the mascot (rate limiting)."""
    state = _load_state()
    last_shown = state.get("last_shown")

    if last_shown is None:
        return True

    try:
        last_time = datetime.fromisoformat(last_shown)
        if datetime.now() - last_time > timedelta(minutes=interval_minutes):
            return True
    except:
        return True

    return False


def mark_mascot_shown():
    """Mark that mascot was shown."""
    state = _load_state()
    state["last_shown"] = datetime.now().isoformat()
    state["show_count"] = state.get("show_count", 0) + 1
    _save_state(state)


# ═══════════════════════════════════════════════════════════
# Hook Functions - Call these at key moments in your CLI
# ═══════════════════════════════════════════════════════════

def on_first_run():
    """Show welcome mascot on first run."""
    state = _load_state()
    if state.get("show_count", 0) == 0:
        print_welcome()
        mark_mascot_shown()
        return True
    return False


def on_startup(force: bool = False):
    """Maybe show mascot on startup (rate limited)."""
    if force or should_show_mascot(interval_minutes=60):
        message = random.choice(WELCOME_MESSAGES)
        mascot_says(message, "happy")
        mark_mascot_shown()
        return True
    return False


def on_success(task_name: str = None):
    """Show success mascot after completing a task."""
    message = random.choice(SUCCESS_MESSAGES)
    if task_name:
        message = f"{task_name}: {message}"
    mascot_says(message, "success")


def on_error(error_msg: str = None):
    """Show error mascot with helpful message."""
    help_msg = random.choice(ERROR_HELP)
    full_msg = f"{error_msg}\n{help_msg}" if error_msg else help_msg
    mascot_says(full_msg, "error")


def on_long_task_start(task_name: str = ""):
    """Show working mascot when starting a long task."""
    message = f"Je travaille sur: {task_name}..." if task_name else "Je travaille..."
    print_mascot("working", message)


def on_long_task_end(task_name: str = "", success: bool = True):
    """Show completion mascot after long task."""
    if success:
        on_success(task_name)
    else:
        on_error(f"Problème avec {task_name}" if task_name else None)


def show_random_tip():
    """Show a random tip with the mascot."""
    state = _load_state()
    tips_shown = state.get("tips_shown", [])

    # Get tips not shown yet
    available_tips = [(i, t) for i, t in enumerate(TIPS) if i not in tips_shown]

    if not available_tips:
        # Reset if all tips shown
        tips_shown = []
        available_tips = list(enumerate(TIPS))

    idx, (cmd, desc) = random.choice(available_tips)

    message = f"💡 Astuce: {cmd}\n   {desc}"
    mascot_says(message, "thinking")

    # Track shown tip
    tips_shown.append(idx)
    state["tips_shown"] = tips_shown
    _save_state(state)


def loading_mascot(message: str = "Chargement..."):
    """Show loading mascot (inline version)."""
    console.print(f"{mini_mascot('working')} {message}", style="yellow")


def inline_success(message: str = "OK"):
    """Inline success with mini mascot."""
    console.print(f"{mini_mascot('happy')} {message}", style="green")


def inline_error(message: str = "Erreur"):
    """Inline error with mini mascot."""
    console.print(f"{mini_mascot('sad')} {message}", style="red")


# ═══════════════════════════════════════════════════════════
# Context-aware mascot
# ═══════════════════════════════════════════════════════════

def contextual_mascot(context: str):
    """Show mascot based on context."""
    contexts = {
        "gpu": ("working", "GPU optimisé et prêt! 🎮"),
        "model": ("coding", "Modèles chargés!"),
        "error": ("error", random.choice(ERROR_HELP)),
        "success": ("success", random.choice(SUCCESS_MESSAGES)),
        "help": ("thinking", "Comment puis-je t'aider?"),
        "wait": ("working", "Patience, je travaille..."),
        "done": ("happy", "Terminé!"),
        "start": ("happy", random.choice(WELCOME_MESSAGES)),
    }

    mood, message = contexts.get(context, ("default", ""))
    if message:
        mascot_says(message, mood)
    else:
        print_mascot(mood)


# ═══════════════════════════════════════════════════════════
# Animated Mascot for Streaming / Live Feedback
# ═══════════════════════════════════════════════════════════

STREAMING_FRAMES = [
    "(=^･ω･^=)   ",
    "(=^･ω･^=) . ",
    "(=^･ω･^=) ..",
    "(=^･ω･^=)...",
    "(=^･ω･^=) ..",
    "(=^･ω･^=) . ",
]

THINKING_FRAMES = [
    "(=^･◔･^=) 💭",
    "(=^◔･^=)  💭",
    "(=^･◔^=)  💭",
    "(=^◔･^=)  💭",
]

WORKING_FRAMES = [
    "(=^･ｪ･^=)⚙️ ",
    "(=^･ｪ･^=) ⚙️",
    "(=^･ｪ･^=)  ⚙️",
    "(=^･ｪ･^=) ⚙️",
]

# Agent-specific mascots
AGENT_MASCOTS = {
    "browser": {
        "mood": "coding",
        "icon": "🌐",
        "mini": "(=^･ω･^=)🌐",
        "message": "Navigation en cours..."
    },
    "ml": {
        "mood": "thinking",
        "icon": "🧠",
        "mini": "(=^◔ω◔^=)🧠",
        "message": "Analyse ML..."
    },
    "code": {
        "mood": "coding",
        "icon": "💻",
        "mini": "(=^･ｪ･^=)💻",
        "message": "Génération de code..."
    },
    "data": {
        "mood": "working",
        "icon": "📊",
        "mini": "(=^･ω･^=)📊",
        "message": "Traitement des données..."
    },
    "optimizer": {
        "mood": "working",
        "icon": "⚡",
        "mini": "(=^▶◀^=)⚡",
        "message": "Optimisation GPU..."
    },
    "scraper": {
        "mood": "coding",
        "icon": "🕷️",
        "mini": "(=^･ω･^=)🕷️",
        "message": "Extraction web..."
    },
    "autonomous": {
        "mood": "thinking",
        "icon": "🤖",
        "mini": "(=^◔ω◔^=)🤖",
        "message": "Agent autonome en action..."
    },
    "planning": {
        "mood": "thinking",
        "icon": "📋",
        "mini": "(=^-*-^=)📋",
        "message": "Planification en cours..."
    },
    "executing": {
        "mood": "working",
        "icon": "▶️",
        "mini": "(=^･ω･^=)▶️",
        "message": "Exécution du plan..."
    },
    "default": {
        "mood": "default",
        "icon": "🤖",
        "mini": "(=^･ω･^=)🤖",
        "message": "Agent actif..."
    }
}


class AnimatedMascot:
    """Animated mascot for streaming and live feedback."""

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self.frame_index = 0

    def get_streaming_frame(self) -> str:
        """Get next streaming animation frame."""
        frame = STREAMING_FRAMES[self.frame_index % len(STREAMING_FRAMES)]
        self.frame_index += 1
        return frame

    def get_thinking_frame(self) -> str:
        """Get next thinking animation frame."""
        frame = THINKING_FRAMES[self.frame_index % len(THINKING_FRAMES)]
        self.frame_index += 1
        return frame

    def get_working_frame(self) -> str:
        """Get next working animation frame."""
        frame = WORKING_FRAMES[self.frame_index % len(WORKING_FRAMES)]
        self.frame_index += 1
        return frame

    def reset(self):
        """Reset animation frame counter."""
        self.frame_index = 0


def get_agent_mascot(agent_type: str) -> dict:
    """Get mascot configuration for specific agent type."""
    return AGENT_MASCOTS.get(agent_type.lower(), AGENT_MASCOTS["default"])


def agent_mascot_inline(agent_type: str, status: str = "working") -> str:
    """Get inline mascot for agent with status."""
    agent = get_agent_mascot(agent_type)

    status_indicators = {
        "working": "⚙️",
        "success": "✅",
        "error": "❌",
        "idle": "💤",
        "starting": "🚀",
    }

    indicator = status_indicators.get(status, "")
    return f"{agent['mini']} {indicator}"


def chat_welcome_mascot(console: Console = None):
    """Show welcome mascot for chat session."""
    if console is None:
        console = Console()

    mascot_says("Bienvenue! Je suis prêt à t'aider! 💬", "happy", console)


def chat_thinking_mascot(console: Console = None) -> str:
    """Get thinking mascot for chat (inline)."""
    return "(=^･◔･^=) 💭 Réflexion..."


def chat_response_mascot(response_type: str = "success", console: Console = None):
    """Show mascot reaction based on response type."""
    if console is None:
        console = Console()

    reactions = {
        "success": ("happy", "✨"),
        "error": ("error", "Oups! Laisse-moi réessayer..."),
        "long": ("working", "C'est une question complexe..."),
        "code": ("coding", "Voici le code!"),
        "help": ("thinking", "Voici quelques suggestions:"),
    }

    mood, msg = reactions.get(response_type, ("default", ""))
    if msg:
        console.print(f"{mini_mascot(mood if mood in ['happy', 'sad', 'working'] else 'default')} {msg}", style="cyan")


def live_mascot_status(action: str, console: Console = None) -> str:
    """Get mascot status for live mode actions."""
    actions = {
        "navigate": "(=^･ω･^=)🌐 Navigation...",
        "click": "(=^･ω･^=)👆 Clic!",
        "type": "(=^･ω･^=)⌨️  Saisie...",
        "extract": "(=^･ω･^=)📋 Extraction...",
        "screenshot": "(=^･ω･^=)📸 Capture!",
        "wait": "(=^-ω-^=)💤 Attente...",
        "success": "(=^◡^=)✅ Succès!",
        "error": "(=;ェ;=)❌ Erreur",
        "thinking": "(=^･◔･^=)💭 Analyse...",
    }
    return actions.get(action.lower(), f"(=^･ω･^=) {action}")


def show_agent_mascot(agent_type: str, message: str = None, console: Console = None):
    """Show full mascot for specific agent."""
    if console is None:
        console = Console()

    agent = get_agent_mascot(agent_type)
    msg = message or agent["message"]
    mascot_says(f"{agent['icon']} {msg}", agent["mood"], console)


# ═══════════════════════════════════════════════════════════
# Demo / Test
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    console.print("\n[bold magenta]═══ Mascot Hooks Demo ═══[/bold magenta]\n")

    console.print("[cyan]1. First run welcome:[/cyan]")
    on_first_run()

    console.print("\n[cyan]2. Success message:[/cyan]")
    on_success("Installation")

    console.print("\n[cyan]3. Error message:[/cyan]")
    on_error("Connection failed")

    console.print("\n[cyan]4. Random tip:[/cyan]")
    show_random_tip()

    console.print("\n[cyan]5. Inline messages:[/cyan]")
    loading_mascot("Chargement des modèles...")
    inline_success("Modèles chargés!")
    inline_error("Fichier non trouvé")

    console.print("\n[cyan]6. Contextual mascot:[/cyan]")
    contextual_mascot("gpu")
