"""Tawiza CLI v2 Mascot - Retro-futuristic helmet design."""

from dataclasses import dataclass

# Mascot ASCII art with mood variations
MASCOT_ART: dict[str, list[str]] = {
    "default": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._◉)\\  /(◉\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.==._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |_||_|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
    "working": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._●)\\  /(●\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.==._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |▓||▓|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
    "success": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._◈)\\  /(◈\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.==._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |█||█|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
    "thinking": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._◐)\\  /(◑\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.~~._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |░||░|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
    "error": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._⊗)\\  /(⊗\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.XX._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |!||!|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
    "loading": [
        "               _..-- `.`.   `.  `.  `.      --.._",
        "              /    ___________\\   \\   \\______    \\",
        "              |   |.-----------`.  `.  `.---.|   |",
        "              |`. |'  \\`.        \\   \\   \\  '|   |",
        "              |`. |'   \\ `-._     `.  `.  `.'|   |",
        "             /|   |'    `-._◔)\\  /(◔\\   \\   \\|   |\\",
        "           .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        "          /  .|   |'    `.  (_.==._)   \\   \\   \\ |.  \\",
        "        .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        "       /  /   |   |'    .'   |▁||▂|   `.  \\   \\   \\  \\  \\",
        "      / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        "     ( '      |`. |'.______________________.'\\      _.) ` )",
    ],
}

# Loading eye animation frames
LOADING_EYES = ["◌", "◔", "◑", "◕", "●", "◕", "◑", "◔"]


@dataclass
class Mascot:
    """Mascot manager with mood support."""

    current_mood: str = "default"

    def get_art(self, mood: str = None) -> list[str]:
        """Get mascot art for given mood."""
        mood = mood or self.current_mood
        return MASCOT_ART.get(mood, MASCOT_ART["default"]).copy()

    def set_mood(self, mood: str) -> None:
        """Set current mood."""
        if mood in MASCOT_ART:
            self.current_mood = mood

    def render(self, mood: str = None) -> str:
        """Render mascot as string."""
        return "\n".join(self.get_art(mood))


# Singleton instance
MASCOT = Mascot()


def mascot_welcome(version: str = "2.0") -> str:
    """Generate welcome screen with mascot."""
    lines = MASCOT.get_art("default")
    lines.append("")
    lines.append(f"                    ─── tawiza v{version} ───")
    lines.append("")
    lines.append("            Welcome! AI Multi-Agent Platform ready.")
    lines.append("")
    lines.append("                    Quick commands:")
    lines.append("                    ─────────────────")
    lines.append("                    chat     Chat with AI")
    lines.append("                    run      Run an agent")
    lines.append("                    status   System status")
    lines.append("                    pro      Advanced commands")

    return "\n".join(lines)


def mascot_message(message: str, mood: str = "default") -> str:
    """Generate mascot with message."""
    lines = MASCOT.get_art(mood)
    lines.append("")
    lines.append(f"                    {message}")
    return "\n".join(lines)
