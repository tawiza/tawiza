#!/usr/bin/env python3
"""
Composants Interactifs pour CLI Tawiza-V2
Menus, prompts, formulaires et sélecteurs avancés
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import questionary
from questionary import Style

# ===== STYLES PERSONNALISÉS =====

CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:#FF6B35 bold"),  # Question mark
        ("question", "bold"),  # Question text
        ("answer", "fg:#FFD93D bold"),  # Selected answer
        ("pointer", "fg:#FF6B35 bold"),  # Pointer
        ("highlighted", "fg:#FF6B35 bold"),  # Highlighted choice
        ("selected", "fg:#FFD93D"),  # Selected item
        ("separator", "fg:#6C6C6C"),  # Separator
        ("instruction", "fg:#858585"),  # Instructions
        ("text", ""),  # Plain text
        ("disabled", "fg:#858585 italic"),  # Disabled choices
    ]
)


# ===== MENUS INTERACTIFS =====


class InteractiveMenu:
    """Menu de sélection interactif avec recherche"""

    @staticmethod
    def select(
        question: str,
        choices: list[str],
        default: str | None = None,
        instruction: str = "(Use arrow keys)",
        style: Style | None = None,
    ) -> str:
        """Menu de sélection simple"""
        return questionary.select(
            question,
            choices=choices,
            default=default,
            instruction=instruction,
            style=style or CUSTOM_STYLE,
            use_shortcuts=True,
            use_arrow_keys=True,
        ).ask()

    @staticmethod
    def multi_select(
        question: str,
        choices: list[str],
        default: list[str] | None = None,
        instruction: str = "(Space to select, Enter to confirm)",
    ) -> list[str]:
        """Menu de sélection multiple"""
        return questionary.checkbox(
            question, choices=choices, default=default, instruction=instruction, style=CUSTOM_STYLE
        ).ask()

    @staticmethod
    def autocomplete(
        question: str,
        choices: list[str],
        default: str = "",
        meta_information: dict[str, str] | None = None,
    ) -> str:
        """Menu avec auto-complétion"""
        return questionary.autocomplete(
            question,
            choices=choices,
            default=default,
            meta_information=meta_information,
            style=CUSTOM_STYLE,
        ).ask()


# ===== PROMPTS ET VALIDATION =====


class ValidationError(Exception):
    """Erreur de validation"""

    pass


@dataclass
class ValidationRule:
    """Règle de validation"""

    validator: Callable[[str], bool]
    error_message: str


class InteractivePrompt:
    """Prompts avec validation"""

    @staticmethod
    def text(
        question: str,
        default: str = "",
        validate: ValidationRule | None = None,
        multiline: bool = False,
    ) -> str:
        """Prompt texte avec validation"""

        def validation_func(text):
            if validate and not validate.validator(text):
                return validate.error_message
            return True

        return questionary.text(
            question,
            default=default,
            validate=validation_func if validate else None,
            multiline=multiline,
            style=CUSTOM_STYLE,
        ).ask()

    @staticmethod
    def password(question: str, validate: ValidationRule | None = None) -> str:
        """Prompt password masqué"""

        def validation_func(pwd):
            if validate and not validate.validator(pwd):
                return validate.error_message
            return True

        return questionary.password(
            question, validate=validation_func if validate else None, style=CUSTOM_STYLE
        ).ask()

    @staticmethod
    def number(
        question: str,
        default: float | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> float:
        """Prompt nombre avec validation de range"""

        def validate_number(text):
            try:
                value = float(text)
                if min_value is not None and value < min_value:
                    return f"Value must be >= {min_value}"
                if max_value is not None and value > max_value:
                    return f"Value must be <= {max_value}"
                return True
            except ValueError:
                return "Please enter a valid number"

        result = questionary.text(
            question,
            default=str(default) if default is not None else "",
            validate=validate_number,
            style=CUSTOM_STYLE,
        ).ask()

        return float(result)

    @staticmethod
    def integer(
        question: str,
        default: int | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        """Prompt entier avec validation"""

        def validate_int(text):
            try:
                value = int(text)
                if min_value is not None and value < min_value:
                    return f"Value must be >= {min_value}"
                if max_value is not None and value > max_value:
                    return f"Value must be <= {max_value}"
                return True
            except ValueError:
                return "Please enter a valid integer"

        result = questionary.text(
            question,
            default=str(default) if default is not None else "",
            validate=validate_int,
            style=CUSTOM_STYLE,
        ).ask()

        return int(result)

    @staticmethod
    def confirm(question: str, default: bool = False, auto_enter: bool = True) -> bool:
        """Prompt confirmation (yes/no)"""
        return questionary.confirm(
            question, default=default, auto_enter=auto_enter, style=CUSTOM_STYLE
        ).ask()


# ===== FILE/DIRECTORY PICKER =====


class FilePicker:
    """Sélecteur de fichiers et répertoires"""

    @staticmethod
    def select_file(
        question: str = "Select a file:", directory: Path | None = None, pattern: str = "*"
    ) -> Path | None:
        """Sélectionner un fichier"""
        search_dir = directory or Path.cwd()

        if not search_dir.exists():
            print(f"Directory {search_dir} does not exist")
            return None

        # List files matching pattern
        files = sorted([f for f in search_dir.glob(pattern) if f.is_file()])

        if not files:
            print(f"No files matching '{pattern}' found in {search_dir}")
            return None

        # Create choices with relative paths
        choices = [str(f.relative_to(search_dir)) for f in files]
        choices.append("❌ Cancel")

        selected = InteractiveMenu.select(
            question, choices=choices, instruction="(Use arrow keys to navigate)"
        )

        if selected == "❌ Cancel":
            return None

        return search_dir / selected

    @staticmethod
    def select_directory(
        question: str = "Select a directory:", start_dir: Path | None = None
    ) -> Path | None:
        """Sélectionner un répertoire"""
        current_dir = start_dir or Path.cwd()

        while True:
            # List directories
            dirs = sorted(
                [d for d in current_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            )

            choices = ["📁 <Current Directory>"]
            if current_dir.parent != current_dir:
                choices.append("📁 ..")
            choices.extend([f"📁 {d.name}" for d in dirs])
            choices.append("❌ Cancel")

            selected = InteractiveMenu.select(f"{question}\n[{current_dir}]", choices=choices)

            if selected == "❌ Cancel":
                return None
            elif selected == "📁 <Current Directory>":
                return current_dir
            elif selected == "📁 ..":
                current_dir = current_dir.parent
            else:
                dir_name = selected.replace("📁 ", "")
                current_dir = current_dir / dir_name


# ===== FORMULAIRES MULTI-CHAMPS =====


@dataclass
class FormField:
    """Champ de formulaire"""

    name: str
    question: str
    field_type: str  # "text", "number", "password", "select", "confirm"
    default: Any = None
    choices: list[str] | None = None
    validate: ValidationRule | None = None
    min_value: float | None = None
    max_value: float | None = None


class InteractiveForm:
    """Formulaire interactif multi-champs"""

    @staticmethod
    def create(title: str, fields: list[FormField], confirm_submit: bool = True) -> dict[str, Any]:
        """Créer et afficher un formulaire"""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        console.print(Panel(f"[bold cyan]{title}[/]", border_style="cyan"))
        console.print()

        results = {}

        for field in fields:
            if field.field_type == "text":
                results[field.name] = InteractivePrompt.text(
                    field.question, default=str(field.default or ""), validate=field.validate
                )

            elif field.field_type == "password":
                results[field.name] = InteractivePrompt.password(
                    field.question, validate=field.validate
                )

            elif field.field_type == "number":
                results[field.name] = InteractivePrompt.number(
                    field.question,
                    default=field.default,
                    min_value=field.min_value,
                    max_value=field.max_value,
                )

            elif field.field_type == "integer":
                results[field.name] = InteractivePrompt.integer(
                    field.question,
                    default=field.default,
                    min_value=field.min_value,
                    max_value=field.max_value,
                )

            elif field.field_type == "select":
                results[field.name] = InteractiveMenu.select(
                    field.question, choices=field.choices or [], default=field.default
                )

            elif field.field_type == "multi_select":
                results[field.name] = InteractiveMenu.multi_select(
                    field.question, choices=field.choices or [], default=field.default
                )

            elif field.field_type == "confirm":
                results[field.name] = InteractivePrompt.confirm(
                    field.question, default=field.default or False
                )

        # Confirm submission
        if confirm_submit:
            console.print()
            console.print("[bold cyan]Form Summary:[/]")
            for key, value in results.items():
                console.print(f"  [cyan]{key}:[/] {value}")
            console.print()

            if not InteractivePrompt.confirm("Submit form?", default=True):
                return {}

        return results


# ===== DEMO =====

if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.clear()

    console.print(Panel("[bold cyan]Interactive Components Demo[/]", border_style="cyan"))
    console.print()

    # 1. Simple select
    console.print("[bold]1. Simple Select Menu:[/]")
    theme = InteractiveMenu.select(
        "Choose a theme:",
        choices=["🌅 Sunset", "🌊 Ocean", "🌲 Forest", "⚡ Neon"],
        instruction="Use arrow keys",
    )
    console.print(f"[green]✓ Selected: {theme}[/]\n")

    # 2. Multi-select
    console.print("[bold]2. Multi-Select Menu:[/]")
    features = InteractiveMenu.multi_select(
        "Select features to enable:",
        choices=["GPU Optimization", "Smart Cache", "Auto-retry", "Logging"],
        instruction="Space to select, Enter to confirm",
    )
    console.print(f"[green]✓ Selected: {', '.join(features)}[/]\n")

    # 3. Text prompt with validation
    console.print("[bold]3. Text Prompt with Validation:[/]")
    name = InteractivePrompt.text(
        "Enter your name:",
        validate=ValidationRule(
            validator=lambda x: len(x) >= 3, error_message="Name must be at least 3 characters"
        ),
    )
    console.print(f"[green]✓ Name: {name}[/]\n")

    # 4. Number prompt
    console.print("[bold]4. Number Prompt:[/]")
    workers = InteractivePrompt.integer("Number of workers:", default=4, min_value=1, max_value=16)
    console.print(f"[green]✓ Workers: {workers}[/]\n")

    # 5. Confirmation
    console.print("[bold]5. Confirmation:[/]")
    if InteractivePrompt.confirm("Apply configuration?", default=True):
        console.print("[green]✓ Configuration applied![/]")
    else:
        console.print("[yellow]✗ Cancelled[/]")

    console.print()
    console.print(Panel("[bold green]Demo Complete![/]", border_style="green"))
