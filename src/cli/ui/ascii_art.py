"""
ASCII Art Generator - Algorithmic art for terminal

Provides multiple algorithmic art generators:
- Fractals (Mandelbrot, Julia sets)
- Cellular automata (Conway's Game of Life)
- Procedural patterns (noise, waves)
- Dynamic banners
- Matrix rain effect
"""

import math
import random
import time
from dataclasses import dataclass


@dataclass
class Point:
    """2D point"""
    x: float
    y: float


class FractalArt:
    """
    Fractal art generator for terminal

    Generates beautiful mathematical fractals using ASCII characters
    """

    def __init__(self, width: int = 80, height: int = 40):
        self.width = width
        self.height = height

    def mandelbrot(
        self,
        *,
        max_iter: int = 50,
        chars: str = " ·:░▒▓█",
        center_x: float = -0.5,
        center_y: float = 0.0,
        zoom: float = 1.5,
    ) -> str:
        """
        Generate Mandelbrot set visualization

        Args:
            max_iter: Maximum iterations for convergence
            chars: Characters for different iteration depths
            center_x: X coordinate of center
            center_y: Y coordinate of center
            zoom: Zoom level

        Returns:
            ASCII art string
        """
        lines = []

        for y in range(self.height):
            line = []
            for x in range(self.width):
                # Map pixel to complex plane
                c_real = center_x + (x - self.width / 2) / (self.width / 4) / zoom
                c_imag = center_y + (y - self.height / 2) / (self.height / 4) / zoom

                # Calculate iterations
                z_real, z_imag = 0.0, 0.0
                iterations = 0

                while iterations < max_iter and z_real**2 + z_imag**2 < 4:
                    z_real_new = z_real**2 - z_imag**2 + c_real
                    z_imag = 2 * z_real * z_imag + c_imag
                    z_real = z_real_new
                    iterations += 1

                # Map iterations to character
                char_index = int((iterations / max_iter) * (len(chars) - 1))
                line.append(chars[char_index])

            lines.append("".join(line))

        return "\n".join(lines)

    def julia_set(
        self,
        *,
        c_real: float = -0.7,
        c_imag: float = 0.27015,
        max_iter: int = 50,
        chars: str = " ·:░▒▓█",
        zoom: float = 1.0,
    ) -> str:
        """
        Generate Julia set visualization

        Args:
            c_real: Real part of complex constant
            c_imag: Imaginary part of complex constant
            max_iter: Maximum iterations
            chars: Characters for different depths
            zoom: Zoom level

        Returns:
            ASCII art string
        """
        lines = []

        for y in range(self.height):
            line = []
            for x in range(self.width):
                # Map pixel to complex plane
                z_real = (x - self.width / 2) / (self.width / 4) / zoom
                z_imag = (y - self.height / 2) / (self.height / 4) / zoom

                # Calculate iterations
                iterations = 0

                while iterations < max_iter and z_real**2 + z_imag**2 < 4:
                    z_real_new = z_real**2 - z_imag**2 + c_real
                    z_imag = 2 * z_real * z_imag + c_imag
                    z_real = z_real_new
                    iterations += 1

                # Map iterations to character
                char_index = int((iterations / max_iter) * (len(chars) - 1))
                line.append(chars[char_index])

            lines.append("".join(line))

        return "\n".join(lines)


class ProceduralPatterns:
    """
    Procedural pattern generator

    Creates beautiful patterns using mathematical functions
    """

    def __init__(self, width: int = 80, height: int = 40):
        self.width = width
        self.height = height

    def wave_pattern(
        self,
        *,
        frequency: float = 0.1,
        amplitude: float = 10.0,
        phase: float = 0.0,
        chars: str = " ·:░▒▓█",
    ) -> str:
        """
        Generate wave pattern

        Args:
            frequency: Wave frequency
            amplitude: Wave amplitude
            phase: Phase shift
            chars: Characters for different intensities

        Returns:
            ASCII art string
        """
        lines = []

        for y in range(self.height):
            line = []
            for x in range(self.width):
                # Calculate wave value
                value = math.sin((x * frequency) + phase) * amplitude
                value += math.cos((y * frequency * 0.5) + phase) * amplitude

                # Normalize to 0-1
                normalized = (value + 2 * amplitude) / (4 * amplitude)

                # Map to character
                char_index = int(normalized * (len(chars) - 1))
                char_index = max(0, min(len(chars) - 1, char_index))
                line.append(chars[char_index])

            lines.append("".join(line))

        return "\n".join(lines)

    def perlin_noise_pattern(
        self,
        *,
        scale: float = 0.1,
        octaves: int = 4,
        chars: str = " ·:░▒▓█",
        seed: int | None = None,
    ) -> str:
        """
        Generate Perlin-like noise pattern

        Args:
            scale: Noise scale
            octaves: Number of octaves for detail
            chars: Characters for different intensities
            seed: Random seed

        Returns:
            ASCII art string
        """
        if seed is not None:
            random.seed(seed)

        lines = []

        for y in range(self.height):
            line = []
            for x in range(self.width):
                # Simple noise approximation
                value = 0.0
                amplitude = 1.0
                frequency = scale

                for _ in range(octaves):
                    # Use sine for smooth noise approximation
                    noise_x = math.sin(x * frequency + random.random() * 0.1) * amplitude
                    noise_y = math.cos(y * frequency + random.random() * 0.1) * amplitude
                    value += (noise_x + noise_y) / 2

                    amplitude *= 0.5
                    frequency *= 2

                # Normalize to 0-1
                normalized = (value + octaves) / (2 * octaves)

                # Map to character
                char_index = int(normalized * (len(chars) - 1))
                char_index = max(0, min(len(chars) - 1, char_index))
                line.append(chars[char_index])

            lines.append("".join(line))

        return "\n".join(lines)

    def spiral_pattern(
        self,
        *,
        rotations: float = 3.0,
        thickness: float = 2.0,
        chars: str = " ·:░▒▓█",
    ) -> str:
        """
        Generate spiral pattern

        Args:
            rotations: Number of spiral rotations
            thickness: Spiral thickness
            chars: Characters for different intensities

        Returns:
            ASCII art string
        """
        lines = []
        center_x = self.width / 2
        center_y = self.height / 2
        max_radius = min(center_x, center_y)

        for y in range(self.height):
            line = []
            for x in range(self.width):
                # Calculate distance and angle from center
                dx = x - center_x
                dy = (y - center_y) * 2  # Aspect ratio correction

                distance = math.sqrt(dx**2 + dy**2)
                angle = math.atan2(dy, dx)

                # Calculate spiral value
                spiral_angle = (distance / max_radius) * rotations * 2 * math.pi
                spiral_value = math.sin(spiral_angle - angle) * thickness

                # Normalize based on distance
                if distance < max_radius:
                    value = (spiral_value + thickness) / (2 * thickness)
                    char_index = int(value * (len(chars) - 1))
                    char_index = max(0, min(len(chars) - 1, char_index))
                    line.append(chars[char_index])
                else:
                    line.append(chars[0])

            lines.append("".join(line))

        return "\n".join(lines)


class MatrixRain:
    """
    Matrix rain effect generator

    Creates the iconic Matrix digital rain animation
    """

    def __init__(self, width: int = 80, height: int = 40):
        self.width = width
        self.height = height
        self.columns: list[int] = [random.randint(0, height) for _ in range(width)]
        self.chars = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜｦﾝ0123456789"

    def generate_frame(self) -> str:
        """
        Generate a single frame of matrix rain

        Returns:
            ASCII art string
        """
        # Create empty grid
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]

        # Update columns
        for x in range(self.width):
            # Draw trail
            y = self.columns[x]

            if y < self.height:
                # Bright head
                grid[y][x] = random.choice(self.chars)

                # Fading trail
                for trail_y in range(max(0, y - 10), y):
                    if trail_y >= 0:
                        grid[trail_y][x] = random.choice(self.chars)

            # Move column down
            self.columns[x] += 1

            # Reset column if it's gone off screen
            if self.columns[x] > self.height + 10:
                self.columns[x] = random.randint(-10, 0)

        # Convert grid to string
        lines = ["".join(row) for row in grid]
        return "\n".join(lines)

    def animate(self, duration: float = 5.0, fps: int = 10) -> None:
        """
        Animate matrix rain for a duration

        Args:
            duration: Animation duration in seconds
            fps: Frames per second
        """
        import os

        frame_delay = 1.0 / fps
        start_time = time.time()

        while time.time() - start_time < duration:
            # Clear screen
            os.system('clear' if os.name != 'nt' else 'cls')

            # Generate and print frame
            frame = self.generate_frame()
            print(frame)

            # Wait for next frame
            time.sleep(frame_delay)


class BannerArt:
    """
    Dynamic banner generator

    Creates impressive banners for CLI headers
    """

    TAWIZA_BANNER = r"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║    ███╗   ███╗██████╗ ████████╗ ██████╗  ██████╗       ██╗   ██╗██████╗   ║
║    ████╗ ████║██╔══██╗╚══██╔══╝██╔═══██╗██╔═══██╗      ██║   ██║╚════██╗  ║
║    ██╔████╔██║██████╔╝   ██║   ██║   ██║██║   ██║█████╗██║   ██║ █████╔╝  ║
║    ██║╚██╔╝██║██╔═══╝    ██║   ██║   ██║██║   ██║╚════╝╚██╗ ██╔╝██╔═══╝   ║
║    ██║ ╚═╝ ██║██║        ██║   ╚██████╔╝╚██████╔╝       ╚████╔╝ ███████╗  ║
║    ╚═╝     ╚═╝╚═╝        ╚═╝    ╚═════╝  ╚═════╝         ╚═══╝  ╚══════╝  ║
║                                                                           ║
║              Machine Learning Platform - Terminal Operations              ║
║                           Powered by Tajine Production                    ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""

    CYBERPUNK_BANNER = r"""
    ▄▄▄▄███▄▄▄▄   ███▄▄▄▄       ███      ▄██████▄   ▄██████▄           ▄█    █▄  ████████▄
  ▄██▀▀▀███▀▀▀██▄ ███▀▀▀██▄ ▀█████████▄ ███    ███ ███    ███         ███    ███ ███   ▀███
  ███   ███   ███ ███   ███    ▀███▀▀██ ███    ███ ███    ███         ███    ███ ███    ███
  ███   ███   ███ ███   ███     ███   ▀ ███    ███ ███    ███        ▄███▄▄▄▄███▄███    ███
  ███   ███   ███ ███   ███     ███     ███    ███ ███    ███       ▀▀███▀▀▀▀███▀███    ███
  ███   ███   ███ ███   ███     ███     ███    ███ ███    ███         ███    ███ ███    ███
  ███   ███   ███ ███   ███     ███     ███    ███ ███    ███         ███    ███ ███   ▄███
   ▀█   ███   █▀   ▀█   █▀     ▄████▀    ▀██████▀   ▀██████▀          ███    █▀  ████████▀
"""

    MINIMAL_BANNER = """
┌──────────────────────────────────────────────────────────────┐
│                        Tawiza v2.0                            │
│              Machine Learning Platform CLI                   │
└──────────────────────────────────────────────────────────────┘
"""

    @classmethod
    def get_banner(cls, style: str = "tawiza") -> str:
        """
        Get banner by style

        Args:
            style: Banner style (tawiza, cyberpunk, minimal)

        Returns:
            Banner ASCII art
        """
        banners = {
            "tawiza": cls.TAWIZA_BANNER,
            "cyberpunk": cls.CYBERPUNK_BANNER,
            "minimal": cls.MINIMAL_BANNER,
        }

        return banners.get(style.lower(), cls.TAWIZA_BANNER)

    @staticmethod
    def create_border_box(
        text: str,
        *,
        width: int | None = None,
        padding: int = 2,
        border_chars: str = "═║╔╗╚╝",
    ) -> str:
        """
        Create a bordered box around text

        Args:
            text: Text to box
            width: Box width (auto if None)
            padding: Internal padding
            border_chars: Characters for borders (horizontal, vertical, TL, TR, BL, BR)

        Returns:
            Bordered text
        """
        lines = text.split("\n")
        max_len = max(len(line) for line in lines) if lines else 0
        box_width = width or (max_len + 2 * padding)

        h_char, v_char, tl, tr, bl, br = border_chars

        # Top border
        result = [f"{tl}{h_char * box_width}{tr}"]

        # Content lines
        for line in lines:
            padded_line = line.ljust(max_len)
            padding_str = " " * padding
            result.append(f"{v_char}{padding_str}{padded_line}{padding_str}{v_char}")

        # Bottom border
        result.append(f"{bl}{h_char * box_width}{br}")

        return "\n".join(result)


# Convenience functions
def show_mandelbrot(width: int = 80, height: int = 40) -> None:
    """Display Mandelbrot set"""
    fractal = FractalArt(width, height)
    print(fractal.mandelbrot())


def show_julia_set(width: int = 80, height: int = 40) -> None:
    """Display Julia set"""
    fractal = FractalArt(width, height)
    print(fractal.julia_set())


def show_matrix_rain(duration: float = 5.0) -> None:
    """Display Matrix rain animation"""
    matrix = MatrixRain()
    matrix.animate(duration=duration)


def show_wave_pattern(width: int = 80, height: int = 40) -> None:
    """Display wave pattern"""
    patterns = ProceduralPatterns(width, height)
    print(patterns.wave_pattern())


def show_spiral(width: int = 80, height: int = 40) -> None:
    """Display spiral pattern"""
    patterns = ProceduralPatterns(width, height)
    print(patterns.spiral_pattern())
