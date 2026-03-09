#!/usr/bin/env python3
"""Demo: Option B - Full mascot with status overlay."""

import sys
import time

# ANSI colors
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Full mascot with overlay zones marked
MASCOT_TEMPLATE = f"""
{CYAN}               _..-- `.`.   `.  `.  `.      --.._
              /    ___________\\   \\   \\______    \\
              |   |.-----------`.  `.  `.---.|   |
              |`. |'  \\`.        \\   \\   \\  '|   |
              |`. |'   \\ `-._     `.  `.  `.'|   |{RESET}
             {CYAN}/|   |'    `-._{YELLOW}{{eyes}}{CYAN})\\  /({YELLOW}{{eyes}}{CYAN}\\   \\   \\|   |\\{RESET}
           {CYAN}.' |   |'  `.     .'  '.  `.  `.  `.  | `.{RESET}
          {CYAN}/  .|   |'    `.  (_{{mouth}}_)   \\   \\   \\ |.  \\{RESET}
        {CYAN}.' .' |   |'      _.-======-._  `.  `.  `. `. `.{RESET}
       {CYAN}/  /   |   |'    .'   |{{bar1}}||{{bar2}}|   `.  \\   \\   \\  \\  \\{RESET}
      {CYAN}/ .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\{RESET}
     {CYAN}( '      |`. |'.______________________.'\\      _.) ` ){RESET}
"""

# Animation frames
EYES = ["◌", "◔", "◑", "◕", "●", "◕", "◑", "◔"]
BARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
MOUTHS = {
    "thinking": ".~~.",
    "working": ".==.",
    "success": ".^^.",
    "error": ".XX.",
}


def render_frame(step: int, status: str, mood: str = "working") -> str:
    """Render a single frame with current state."""
    eye_idx = step % len(EYES)
    bar_idx = step % len(BARS)

    mascot = MASCOT_TEMPLATE.format(
        eyes=EYES[eye_idx],
        mouth=MOUTHS.get(mood, ".==."),
        bar1=BARS[bar_idx],
        bar2=BARS[(bar_idx + 4) % len(BARS)],
    )

    # Status overlay - positioned to the right of mascot
    overlay = f"""
{BOLD}╭─────────────────────────────────────────────────────╮{RESET}
{BOLD}│{RESET} {MAGENTA}◆ Agent ReAct{RESET}                                       {BOLD}│{RESET}
{BOLD}├─────────────────────────────────────────────────────┤{RESET}
{BOLD}│{RESET} {YELLOW}▶ Status:{RESET} {status:<42} {BOLD}│{RESET}
{BOLD}│{RESET}                                                     {BOLD}│{RESET}
{BOLD}│{RESET} {DIM}Step 2/4 • Elapsed: 3.2s{RESET}                           {BOLD}│{RESET}
{BOLD}╰─────────────────────────────────────────────────────╯{RESET}
"""
    return mascot + overlay


def demo_sequence():
    """Run the demo animation sequence."""
    statuses = [
        ("thinking", "Analyzing the request..."),
        ("working", "Executing calculator tool..."),
        ("working", "Processing result: 42"),
        ("success", "Task completed successfully!"),
    ]

    print("\033[2J\033[H")  # Clear screen
    print(f"\n{BOLD}{CYAN}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}        OPTION B: Full Mascot with Overlay Demo{RESET}")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════{RESET}\n")

    for mood, status in statuses:
        for frame in range(8):  # 8 animation frames per status
            print("\033[7;0H")  # Move cursor to row 7
            print(render_frame(frame, status, mood))
            time.sleep(0.15)

    # Final result
    print(f"""
{GREEN}╭─────────────────────────────────────────────────────╮
│  ✓ Résultat Final                                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│    15 + 27 = {BOLD}42{RESET}{GREEN}                                     │
│                                                     │
│    {DIM}Durée: 14.2s • Étapes: 4 • Model: qwen3.5:27b{RESET}{GREEN}     │
╰─────────────────────────────────────────────────────╯{RESET}
""")


def static_preview():
    """Show static preview without animation."""
    print(f"\n{BOLD}{CYAN}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}        OPTION B: Full Mascot with Status Overlay{RESET}")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════════════════════════{RESET}\n")

    # Thinking state
    print(f"{DIM}─── État: THINKING ───{RESET}")
    print(MASCOT_TEMPLATE.format(eyes="◐", mouth=".~~.", bar1="░", bar2="░"))
    print(f"{BOLD}╭─────────────────────────────────────────────────────╮{RESET}")
    print(f"{BOLD}│{RESET} {MAGENTA}◆ Agent ReAct{RESET} {DIM}• qwen3.5:27b{RESET}                           {BOLD}│{RESET}")
    print(f"{BOLD}├─────────────────────────────────────────────────────┤{RESET}")
    print(f"{BOLD}│{RESET} {YELLOW}💭 Thinking:{RESET} Analyzing user request...              {BOLD}│{RESET}")
    print(f"{BOLD}│{RESET} {DIM}Step 1/? • Elapsed: 1.2s{RESET}                            {BOLD}│{RESET}")
    print(f"{BOLD}╰─────────────────────────────────────────────────────╯{RESET}")

    print(f"\n{DIM}─── État: WORKING ───{RESET}")
    print(MASCOT_TEMPLATE.format(eyes="●", mouth=".==.", bar1="▆", bar2="▂"))
    print(f"{BOLD}╭─────────────────────────────────────────────────────╮{RESET}")
    print(f"{BOLD}│{RESET} {MAGENTA}◆ Agent ReAct{RESET} {DIM}• qwen3.5:27b{RESET}                           {BOLD}│{RESET}")
    print(f"{BOLD}├─────────────────────────────────────────────────────┤{RESET}")
    print(f"{BOLD}│{RESET} {CYAN}⚡ Action:{RESET} calculator(15 + 27)                      {BOLD}│{RESET}")
    print(f"{BOLD}│{RESET} {GREEN}📥 Result:{RESET} 42                                       {BOLD}│{RESET}")
    print(f"{BOLD}│{RESET} {DIM}Step 2/3 • Elapsed: 8.4s{RESET}                            {BOLD}│{RESET}")
    print(f"{BOLD}╰─────────────────────────────────────────────────────╯{RESET}")

    print(f"\n{DIM}─── État: SUCCESS ───{RESET}")
    print(MASCOT_TEMPLATE.format(eyes="◈", mouth=".^^.", bar1="█", bar2="█"))
    print(f"{GREEN}{BOLD}╭─────────────────────────────────────────────────────╮{RESET}")
    print(f"{GREEN}{BOLD}│{RESET} {GREEN}✓ Completed!{RESET}                                        {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}├─────────────────────────────────────────────────────┤{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}                                                     {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}  La somme de 15 et 27 est {BOLD}42{RESET}.                      {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}                                                     {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}  {DIM}3 steps • 14.2s • qwen3.5:27b{RESET}                       {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}╰─────────────────────────────────────────────────────╯{RESET}")


if __name__ == "__main__":
    if "--animate" in sys.argv:
        demo_sequence()
    else:
        static_preview()
