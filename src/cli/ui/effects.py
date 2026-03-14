"""
Visual Effects - Advanced visual effects for CLI

Provides professional visual effects:
- Color gradients
- Glow effects
- Box decorations
- Text styling
- Rainbow effects
"""

from rich.console import Console
from rich.style import Style
from rich.text import Text


class ColorGradient:
    """
    Color gradient generator

    Creates smooth color transitions using RGB interpolation
    """

    @staticmethod
    def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """Convert RGB to hex color"""
        return f"#{r:02x}{g:02x}{b:02x}"

    @classmethod
    def interpolate_color(
        cls,
        color1: str,
        color2: str,
        factor: float,
    ) -> str:
        """
        Interpolate between two colors

        Args:
            color1: Start color (hex)
            color2: End color (hex)
            factor: Interpolation factor (0-1)

        Returns:
            Interpolated color (hex)
        """
        r1, g1, b1 = cls.hex_to_rgb(color1)
        r2, g2, b2 = cls.hex_to_rgb(color2)

        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        return cls.rgb_to_hex(r, g, b)

    @classmethod
    def create_gradient(
        cls,
        text: str,
        start_color: str,
        end_color: str,
    ) -> Text:
        """
        Apply gradient to text

        Args:
            text: Text to apply gradient to
            start_color: Starting color (hex)
            end_color: Ending color (hex)

        Returns:
            Rich Text with gradient applied
        """
        result = Text()
        text_length = len(text)

        for i, char in enumerate(text):
            factor = i / max(1, text_length - 1)
            color = cls.interpolate_color(start_color, end_color, factor)
            result.append(char, style=Style(color=color))

        return result

    @classmethod
    def rainbow_gradient(cls, text: str) -> Text:
        """
        Apply rainbow gradient to text

        Args:
            text: Text to colorize

        Returns:
            Rich Text with rainbow gradient
        """
        # Rainbow colors
        colors = [
            "#FF0000",  # Red
            "#FF7F00",  # Orange
            "#FFFF00",  # Yellow
            "#00FF00",  # Green
            "#0000FF",  # Blue
            "#4B0082",  # Indigo
            "#9400D3",  # Violet
        ]

        result = Text()
        text_length = len(text)

        for i, char in enumerate(text):
            # Calculate position in rainbow (0-1)
            position = (i / max(1, text_length - 1)) * (len(colors) - 1)

            # Get surrounding colors
            color_index = int(position)
            next_index = min(color_index + 1, len(colors) - 1)

            # Interpolate between colors
            local_factor = position - color_index
            color = cls.interpolate_color(
                colors[color_index],
                colors[next_index],
                local_factor,
            )

            result.append(char, style=Style(color=color))

        return result


class GlowEffect:
    """
    Glow effect generator

    Creates neon-like glow effects using color intensity
    """

    @staticmethod
    def create_glow(
        text: str,
        base_color: str = "#00FFFF",
        intensity: int = 3,
    ) -> Text:
        """
        Create glowing text effect

        Args:
            text: Text to glow
            base_color: Base glow color (hex)
            intensity: Glow intensity (layers)

        Returns:
            Rich Text with glow effect
        """
        # Create layers of text with decreasing intensity
        result = Text()

        # Outer glow layers
        for i in range(intensity):
            alpha = 0.3 - (i * 0.1)
            if alpha > 0:
                result.append(" " * i)

        # Core bright text
        result.append(text, style=f"bold {base_color}")

        return result

    @staticmethod
    def neon_text(text: str, color: str = "cyan") -> Text:
        """
        Create neon sign effect

        Args:
            text: Text to neon-ify
            color: Neon color

        Returns:
            Rich Text with neon effect
        """
        return Text(text, style=f"bold {color} on black")


class BoxDecorations:
    """
    Box decoration generator

    Creates various box and border styles
    """

    # Box drawing characters
    SINGLE = "─│┌┐└┘"
    DOUBLE = "═║╔╗╚╝"
    ROUNDED = "─│╭╮╰╯"
    THICK = "━┃┏┓┗┛"
    DASHED = "╌╎┌┐└┘"

    @classmethod
    def create_box(
        cls,
        text: str,
        *,
        style: str = "single",
        padding: int = 1,
        title: str | None = None,
    ) -> str:
        """
        Create decorative box around text

        Args:
            text: Text to box
            style: Box style (single, double, rounded, thick, dashed)
            padding: Internal padding
            title: Optional title

        Returns:
            Boxed text
        """
        # Select box chars
        box_chars = {
            "single": cls.SINGLE,
            "double": cls.DOUBLE,
            "rounded": cls.ROUNDED,
            "thick": cls.THICK,
            "dashed": cls.DASHED,
        }

        chars = box_chars.get(style, cls.SINGLE)
        h, v, tl, tr, bl, br = chars

        # Process text lines
        lines = text.split("\n")
        max_width = max(len(line) for line in lines) if lines else 0
        inner_width = max_width + (2 * padding)

        # Create box
        result = []

        # Top border
        if title:
            title_padded = f" {title} "
            title_len = len(title_padded)
            left_border = h * ((inner_width - title_len) // 2)
            right_border = h * (inner_width - title_len - len(left_border))
            result.append(f"{tl}{left_border}{title_padded}{right_border}{tr}")
        else:
            result.append(f"{tl}{h * inner_width}{tr}")

        # Content
        pad_str = " " * padding
        for line in lines:
            padded_line = line.ljust(max_width)
            result.append(f"{v}{pad_str}{padded_line}{pad_str}{v}")

        # Bottom border
        result.append(f"{bl}{h * inner_width}{br}")

        return "\n".join(result)

    @staticmethod
    def create_separator(
        width: int = 80,
        char: str = "─",
        title: str | None = None,
    ) -> str:
        """
        Create decorative separator line

        Args:
            width: Separator width
            char: Character to use
            title: Optional centered title

        Returns:
            Separator line
        """
        if title:
            title_padded = f" {title} "
            title_len = len(title_padded)
            left_len = (width - title_len) // 2
            right_len = width - title_len - left_len
            return f"{char * left_len}{title_padded}{char * right_len}"
        return char * width


class TextStyling:
    """
    Advanced text styling utilities
    """

    @staticmethod
    def create_header(
        text: str,
        *,
        level: int = 1,
        style: str = "cyberpunk",
    ) -> Text:
        """
        Create styled header

        Args:
            text: Header text
            level: Header level (1-3)
            style: Style theme

        Returns:
            Styled header
        """
        styles_map = {
            "cyberpunk": {
                1: "bold magenta",
                2: "bold cyan",
                3: "bold yellow",
            },
            "minimal": {
                1: "bold black",
                2: "bold grey",
                3: "grey",
            },
            "matrix": {
                1: "bold green",
                2: "green",
                3: "dim green",
            },
        }

        theme_styles = styles_map.get(style, styles_map["cyberpunk"])
        text_style = theme_styles.get(level, "bold white")

        # Add decorative prefix based on level
        prefixes = {
            1: "▓▓▓ ",
            2: "▒▒ ",
            3: "░ ",
        }

        prefix = prefixes.get(level, "")
        return Text(f"{prefix}{text}", style=text_style)

    @staticmethod
    def create_badge(
        text: str,
        *,
        color: str = "green",
        symbol: str = "●",
    ) -> Text:
        """
        Create status badge

        Args:
            text: Badge text
            color: Badge color
            symbol: Badge symbol

        Returns:
            Styled badge
        """
        return Text(f"{symbol} {text}", style=f"bold {color}")

    @staticmethod
    def create_tag(
        text: str,
        *,
        bg_color: str = "blue",
        fg_color: str = "white",
    ) -> Text:
        """
        Create tag/label

        Args:
            text: Tag text
            bg_color: Background color
            fg_color: Foreground color

        Returns:
            Styled tag
        """
        return Text(f" {text} ", style=f"bold {fg_color} on {bg_color}")


class AnimatedEffects:
    """
    Simple animated text effects
    """

    @staticmethod
    def pulse_text(text: str, console: Console | None = None) -> None:
        """
        Pulsing text animation (single iteration)

        Args:
            text: Text to pulse
            console: Console instance
        """
        if console is None:
            console = Console()

        # Pulse sequence
        styles = [
            "dim white",
            "white",
            "bold white",
            "white",
            "dim white",
        ]

        for style in styles:
            console.clear()
            console.print(text, style=style)
            import time

            time.sleep(0.1)


def demo_effects():
    """Demonstration of visual effects"""
    console = Console()

    console.print("\n╔═══════════════════════════════════════╗")
    console.print("║   VISUAL EFFECTS SHOWCASE             ║")
    console.print("╚═══════════════════════════════════════╝\n")

    # Gradient
    console.print("[bold yellow]1. Color Gradients:[/bold yellow]")
    gradient_text = ColorGradient.create_gradient(
        "Machine Learning Platform",
        "#FF00FF",
        "#00FFFF",
    )
    console.print(gradient_text)

    # Rainbow
    console.print("\n[bold yellow]2. Rainbow Gradient:[/bold yellow]")
    rainbow = ColorGradient.rainbow_gradient("Tawiza v2.0 - AI Powered CLI")
    console.print(rainbow)

    # Neon glow
    console.print("\n[bold yellow]3. Neon Effect:[/bold yellow]")
    neon = GlowEffect.neon_text(">>> SYSTEM ONLINE <<<", "cyan")
    console.print(neon)

    # Boxes
    console.print("\n[bold yellow]4. Decorative Boxes:[/bold yellow]")
    box_text = BoxDecorations.create_box(
        "Status: All systems operational\nUptime: 99.99%",
        style="double",
        title="System Status",
    )
    console.print(box_text)

    # Separator
    console.print("\n[bold yellow]5. Separators:[/bold yellow]")
    separator = BoxDecorations.create_separator(60, "═", "Tawiza CLI")
    console.print(separator, style="cyan")

    # Headers
    console.print("\n[bold yellow]6. Styled Headers:[/bold yellow]")
    header1 = TextStyling.create_header("Main Title", level=1, style="cyberpunk")
    header2 = TextStyling.create_header("Subtitle", level=2, style="cyberpunk")
    header3 = TextStyling.create_header("Section", level=3, style="cyberpunk")
    console.print(header1)
    console.print(header2)
    console.print(header3)

    # Badges
    console.print("\n[bold yellow]7. Status Badges:[/bold yellow]")
    badge_success = TextStyling.create_badge("Running", color="green", symbol="✓")
    badge_warning = TextStyling.create_badge("Degraded", color="yellow", symbol="⚠")
    badge_error = TextStyling.create_badge("Failed", color="red", symbol="✗")
    console.print(badge_success, " ", badge_warning, " ", badge_error)

    # Tags
    console.print("\n[bold yellow]8. Tags:[/bold yellow]")
    tag1 = TextStyling.create_tag("ML", bg_color="blue")
    tag2 = TextStyling.create_tag("AI", bg_color="magenta")
    tag3 = TextStyling.create_tag("AUTO", bg_color="green")
    console.print(tag1, " ", tag2, " ", tag3)

    console.print("\n" + "═" * 60 + "\n")


if __name__ == "__main__":
    demo_effects()
