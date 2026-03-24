#!/usr/bin/env python3
"""Final Design: Centered mascot + progress bar + scrolling thoughts."""

import shutil
import sys
import time

# ANSI
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[K"

# Get terminal width for centering
TERM_WIDTH = shutil.get_terminal_size().columns

# Eye animation frames
EYES = ["◌", "◔", "◑", "◕", "●", "◕", "◑", "◔"]
BARS = "▁▂▃▄▅▆▇█"


def center(text: str) -> str:
    """Center text in terminal."""
    # Strip ANSI codes for length calculation
    import re

    clean = re.sub(r"\033\[[0-9;]*m", "", text)
    padding = max(0, (TERM_WIDTH - len(clean)) // 2)
    return " " * padding + text


def get_mascot(eyes: str, mouth: str, bar1: str, bar2: str) -> list[str]:
    """Generate mascot with current state."""
    return [
        f"{CYAN}           _..-- `.`.   `.  `.  `.      --.._",
        "          /    ___________\\   \\   \\______    \\",
        "          |   |.-----------`.  `.  `.---.|   |",
        "          |`. |'  \\`.        \\   \\   \\  '|   |",
        "          |`. |'   \\ `-._     `.  `.  `.'|   |",
        f"         /|   |'    `-._{YELLOW}{eyes}{CYAN})\\  /({YELLOW}{eyes}{CYAN}\\   \\   \\|   |\\",
        "       .' |   |'  `.     .'  '.  `.  `.  `.  | `.",
        f"      /  .|   |'    `.  (_{mouth}_)   \\   \\   \\ |.  \\",
        "    .' .' |   |'      _.-======-._  `.  `.  `. `. `.",
        f"   /  /   |   |'    .'   |{bar1}||{bar2}|   `.  \\   \\   \\  \\  \\",
        "  / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\",
        f" ( '      |`. |'.______________________.'\\      _.) ` ){RESET}",
    ]


def progress_bar(progress: float, width: int = 40) -> str:
    """Create a horizontal progress bar."""
    filled = int(width * progress)
    empty = width - filled
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * empty}{RESET}"
    percent = f"{int(progress * 100)}%"
    return f"[{bar}] {percent}"


def render_frame(
    step: int,
    mood: str,
    thought: str,
    action: str | None,
    progress: float,
    elapsed: float,
):
    """Render complete frame."""
    # Mood settings
    moods = {
        "thinking": ("◐", ".~~."),
        "working": ("●", ".==."),
        "success": ("◈", ".^^."),
        "error": ("⊗", ".XX."),
    }
    eyes_base, mouth = moods.get(mood, ("◉", ".==."))

    # Animate eyes during thinking/working
    eyes = EYES[step % len(EYES)] if mood in ("thinking", "working") else eyes_base

    # Animate bars
    bar1 = BARS[step % len(BARS)]
    bar2 = BARS[(step + 4) % len(BARS)]

    # Build frame
    lines = []

    # Header
    lines.append("")
    lines.append(center(f"{BOLD}{MAGENTA}◆ Tawiza Agent{RESET}"))
    lines.append("")

    # Mascot (centered)
    for line in get_mascot(eyes, mouth, bar1, bar2):
        lines.append(center(line))

    lines.append("")

    # Thought (scrolling style - truncate if too long)
    max_thought = TERM_WIDTH - 20
    if len(thought) > max_thought:
        # Scroll effect
        offset = (step * 2) % (len(thought) - max_thought + 20)
        display_thought = (
            thought[offset : offset + max_thought]
            if offset < len(thought)
            else thought[:max_thought]
        )
    else:
        display_thought = thought

    thought_color = YELLOW if mood == "thinking" else CYAN if mood == "working" else GREEN
    lines.append(center(f"{DIM}💭{RESET} {thought_color}{display_thought}{RESET}"))
    lines.append("")

    # Action (if any)
    if action:
        lines.append(center(f"{CYAN}⚡ {action}{RESET}"))
        lines.append("")

    # Progress bar (centered)
    lines.append(center(progress_bar(progress)))
    lines.append("")

    # Footer
    lines.append(
        center(f"{DIM}Step {int(progress * 4) + 1}/4 • {elapsed:.1f}s • qwen3.5:27b{RESET}")
    )

    return "\n".join(lines)


def demo_sequence():
    """Run the demo animation."""
    print("\033[2J\033[H")  # Clear screen

    steps = [
        (
            "thinking",
            "Analyzing the request... understanding what calculation is needed",
            None,
            0.0,
        ),
        (
            "thinking",
            "The user wants to add 15 and 27 together, I should use the calculator tool",
            None,
            0.15,
        ),
        (
            "working",
            "Executing calculator tool with expression: 15 + 27",
            "calculator(15 + 27)",
            0.35,
        ),
        ("working", "Tool returned result: 42. Now formulating the response", None, 0.65),
        ("working", "Preparing final answer with the calculated sum", None, 0.85),
        ("success", "Task completed! The sum of 15 and 27 is 42", None, 1.0),
    ]

    elapsed = 0.0
    for i, (mood, thought, action, progress) in enumerate(steps):
        for frame in range(12 if i < len(steps) - 1 else 20):
            print("\033[H")  # Move to top
            print(render_frame(frame, mood, thought, action, progress, elapsed))
            time.sleep(0.1)
            elapsed += 0.1

    # Final result
    print("\n")
    print(center(f"{GREEN}{BOLD}╭──────────────────────────────────────────╮{RESET}"))
    print(
        center(
            f"{GREEN}{BOLD}│{RESET}  {GREEN}✓ Résultat{RESET}                              {GREEN}{BOLD}│{RESET}"
        )
    )
    print(center(f"{GREEN}{BOLD}├──────────────────────────────────────────┤{RESET}"))
    print(
        center(
            f"{GREEN}{BOLD}│{RESET}                                          {GREEN}{BOLD}│{RESET}"
        )
    )
    print(
        center(
            f"{GREEN}{BOLD}│{RESET}      15 + 27 = {BOLD}42{RESET}                       {GREEN}{BOLD}│{RESET}"
        )
    )
    print(
        center(
            f"{GREEN}{BOLD}│{RESET}                                          {GREEN}{BOLD}│{RESET}"
        )
    )
    print(center(f"{GREEN}{BOLD}╰──────────────────────────────────────────╯{RESET}"))
    print("")


def static_preview():
    """Show static preview of final design."""
    print("\033[2J\033[H")
    print(center(f"{BOLD}{CYAN}═══════════════════════════════════════════════════{RESET}"))
    print(center(f"{BOLD}{CYAN}      FINAL DESIGN: Centered + Progress Bar{RESET}"))
    print(center(f"{BOLD}{CYAN}═══════════════════════════════════════════════════{RESET}"))
    print("")

    # State 1: Thinking
    print(center(f"{DIM}─── THINKING ───{RESET}"))
    print(render_frame(0, "thinking", "Analyzing the request...", None, 0.1, 1.2))
    print("\n")

    # State 2: Working
    print(center(f"{DIM}─── WORKING ───{RESET}"))
    print(render_frame(4, "working", "Executing tool...", "calculator(15 + 27)", 0.5, 5.4))
    print("\n")

    # State 3: Success
    print(center(f"{DIM}─── SUCCESS ───{RESET}"))
    print(render_frame(0, "success", "Task completed! Result: 42", None, 1.0, 12.3))


if __name__ == "__main__":
    if "--animate" in sys.argv:
        demo_sequence()
    else:
        static_preview()
