#!/usr/bin/env python3
"""
UX Helpers pour Tawiza-V2 CLI

Module centralisé pour les améliorations UX:
- Fuzzy finding
- Progress bars animées
- Notifications desktop
- Clipboard
- Terminal bell
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger
from rich.console import Console

console = Console()

T = TypeVar("T")

# ==============================================================================
# FEATURE FLAGS - Check disponibilité des bibliothèques
# ==============================================================================

HAS_ITERFZF = False
HAS_INQUIRERPY = False
HAS_ALIVE_PROGRESS = False
HAS_PYPERCLIP = False
HAS_PLYER = False
HAS_THEFUZZ = False

try:
    from iterfzf import iterfzf

    HAS_ITERFZF = True
except ImportError:
    pass

try:
    from InquirerPy import inquirer
    from InquirerPy.validator import PathValidator as InquirerPathValidator

    HAS_INQUIRERPY = True
except ImportError:
    pass

try:
    from alive_progress import alive_bar, alive_it

    HAS_ALIVE_PROGRESS = True
except ImportError:
    pass

try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    pass

try:
    from plyer import notification

    HAS_PLYER = True
except ImportError:
    pass

try:
    from thefuzz import fuzz, process

    HAS_THEFUZZ = True
except ImportError:
    pass


# ==============================================================================
# FUZZY FINDING
# ==============================================================================


def fuzzy_select(
    choices: list[str], prompt: str = "Select: ", default: str | None = None, multi: bool = False
) -> str | list[str] | None:
    """
    Sélection avec fuzzy finding.

    Args:
        choices: Liste de choix
        prompt: Message de prompt
        default: Valeur par défaut
        multi: Permettre sélection multiple

    Returns:
        Choix sélectionné(s) ou None
    """
    if not choices:
        return default

    # Méthode 1: iterfzf (meilleur UX)
    if HAS_ITERFZF and not multi:
        try:
            selected = iterfzf(
                choices,
                prompt=prompt,
                multi=multi,
            )
            return selected if selected else default
        except Exception as e:
            logger.debug(f"iterfzf failed: {e}")

    # Méthode 2: InquirerPy fuzzy
    if HAS_INQUIRERPY:
        try:
            if multi:
                result = inquirer.checkbox(
                    message=prompt.rstrip(": "),
                    choices=choices,
                ).execute()
            else:
                result = inquirer.fuzzy(
                    message=prompt.rstrip(": "),
                    choices=choices,
                    default=default,
                ).execute()
            return result
        except Exception as e:
            logger.debug(f"InquirerPy failed: {e}")

    # Fallback: questionary (déjà intégré)
    try:
        import questionary

        if multi:
            return questionary.checkbox(prompt, choices=choices).ask()
        return questionary.select(prompt, choices=choices, default=default).ask()
    except Exception as e:
        logger.debug(f"questionary failed: {e}")

    # Fallback final: input simple
    console.print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        console.print(f"  {i}. {choice}")
    try:
        idx = int(input("Enter number: ")) - 1
        return choices[idx] if 0 <= idx < len(choices) else default
    except (ValueError, IndexError):
        return default


def fuzzy_match(
    query: str, choices: list[str], limit: int = 5, score_cutoff: int = 60
) -> list[tuple[str, int]]:
    """
    Recherche fuzzy dans une liste.

    Args:
        query: Terme de recherche
        choices: Liste de choix
        limit: Nombre max de résultats
        score_cutoff: Score minimum (0-100)

    Returns:
        Liste de tuples (choix, score)
    """
    if HAS_THEFUZZ:
        results = process.extract(query, choices, limit=limit, scorer=fuzz.WRatio)
        return [(r[0], r[1]) for r in results if r[1] >= score_cutoff]

    # Fallback: recherche simple
    query_lower = query.lower()
    matches = []
    for choice in choices:
        if query_lower in choice.lower():
            # Score basé sur position et longueur
            pos = choice.lower().find(query_lower)
            score = 100 - (pos * 2) - (len(choice) - len(query))
            matches.append((choice, max(0, min(100, score))))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:limit]


# ==============================================================================
# PROGRESS BARS
# ==============================================================================


@contextmanager
def animated_progress(
    total: int | None = None, title: str = "Processing", spinner: str = "dots"
) -> Iterator[Callable[[], None]]:
    """
    Progress bar animée avec alive-progress.

    Args:
        total: Nombre total d'items (None = indéterminé)
        title: Titre de la barre
        spinner: Type de spinner

    Yields:
        Fonction pour avancer la barre
    """
    if HAS_ALIVE_PROGRESS:
        try:
            with alive_bar(total, title=title, spinner=spinner) as bar:
                yield bar
            return
        except Exception as e:
            logger.debug(f"alive_progress failed: {e}")

    # Fallback: Rich progress
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn() if total else TextColumn(""),
    ) as progress:
        task = progress.add_task(title, total=total or 100)

        def advance():
            progress.advance(task)

        yield advance


def iterate_with_progress[T](iterable: list[T], title: str = "Processing") -> Iterator[T]:
    """
    Itérer avec progress bar animée.

    Args:
        iterable: Liste à itérer
        title: Titre de la barre

    Yields:
        Items de l'itérable
    """
    if HAS_ALIVE_PROGRESS:
        try:
            yield from alive_it(iterable, title=title)
            return
        except Exception as e:
            logger.debug(f"alive_it failed: {e}")

    # Fallback: Rich
    from rich.progress import track

    yield from track(iterable, description=title)


# ==============================================================================
# NOTIFICATIONS
# ==============================================================================


def notify_desktop(
    title: str, message: str, timeout: int = 10, app_name: str = "Tawiza-V2"
) -> bool:
    """
    Envoyer une notification desktop.

    Args:
        title: Titre de la notification
        message: Corps du message
        timeout: Durée en secondes
        app_name: Nom de l'application

    Returns:
        True si envoyé, False sinon
    """
    if HAS_PLYER:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name=app_name,
                timeout=timeout,
            )
            logger.debug(f"Desktop notification sent: {title}")
            return True
        except Exception as e:
            logger.debug(f"plyer notification failed: {e}")

    # Fallback: terminal bell + message
    beep()
    console.print(f"\n[bold blue]🔔 {title}[/bold blue]: {message}")
    return False


def notify_completion(task_name: str, success: bool = True, details: str | None = None) -> None:
    """
    Notifier la fin d'une tâche.

    Args:
        task_name: Nom de la tâche
        success: Succès ou échec
        details: Détails supplémentaires
    """
    if success:
        title = f"✅ {task_name} terminé"
        message = details or "Tâche complétée avec succès"
    else:
        title = f"❌ {task_name} échoué"
        message = details or "Une erreur s'est produite"

    notify_desktop(title, message)


# ==============================================================================
# CLIPBOARD
# ==============================================================================


def copy_to_clipboard(text: str, show_message: bool = True) -> bool:
    """
    Copier du texte dans le presse-papier.

    Args:
        text: Texte à copier
        show_message: Afficher confirmation

    Returns:
        True si copié, False sinon
    """
    if HAS_PYPERCLIP:
        try:
            pyperclip.copy(text)
            if show_message:
                console.print("[green]✓ Copié dans le presse-papier[/green]")
            return True
        except Exception as e:
            logger.debug(f"pyperclip copy failed: {e}")

    if show_message:
        console.print("[yellow]⚠ Impossible de copier (pyperclip non disponible)[/yellow]")
    return False


def paste_from_clipboard() -> str | None:
    """
    Coller depuis le presse-papier.

    Returns:
        Contenu du presse-papier ou None
    """
    if HAS_PYPERCLIP:
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.debug(f"pyperclip paste failed: {e}")
    return None


def output_with_copy_option(content: str, title: str = "Result", syntax: str | None = None) -> None:
    """
    Afficher du contenu avec option de copier.

    Args:
        content: Contenu à afficher
        title: Titre
        syntax: Langage pour syntax highlighting
    """
    console.print(f"\n[bold]{title}:[/bold]")

    if syntax:
        from rich.syntax import Syntax

        console.print(Syntax(content, syntax, theme="monokai"))
    else:
        console.print(content)

    if HAS_PYPERCLIP:
        try:
            import questionary

            if questionary.confirm("Copier dans le presse-papier?", default=False).ask():
                copy_to_clipboard(content, show_message=True)
        except Exception:
            pass


# ==============================================================================
# TERMINAL BELL
# ==============================================================================


def beep(count: int = 1) -> None:
    """
    Émettre un bip terminal.

    Args:
        count: Nombre de bips
    """
    for _ in range(count):
        print("\a", end="", flush=True)


def alert_attention() -> None:
    """Attirer l'attention de l'utilisateur"""
    beep(2)
    console.print("\n[bold yellow]⚠️  Attention requise![/bold yellow]")


# ==============================================================================
# FILE PATH HELPERS
# ==============================================================================


def select_file(
    prompt: str = "Select file",
    default: str = "./",
    must_exist: bool = True,
    file_filter: str | None = None,
) -> str | None:
    """
    Sélectionner un fichier avec validation.

    Args:
        prompt: Message de prompt
        default: Chemin par défaut
        must_exist: Le fichier doit exister
        file_filter: Extension à filtrer (ex: "*.json")

    Returns:
        Chemin sélectionné ou None
    """
    if HAS_INQUIRERPY:
        try:
            result = inquirer.filepath(
                message=prompt,
                default=default,
                validate=InquirerPathValidator(is_file=must_exist, message="Fichier invalide")
                if must_exist
                else None,
            ).execute()
            return result
        except Exception as e:
            logger.debug(f"InquirerPy filepath failed: {e}")

    # Fallback: questionary
    try:
        import questionary

        path = questionary.path(prompt, default=default).ask()
        if must_exist and path and not Path(path).exists():
            console.print("[red]Fichier introuvable[/red]")
            return None
        return path
    except Exception:
        pass

    # Fallback final
    path = input(f"{prompt} [{default}]: ").strip() or default
    if must_exist and not Path(path).exists():
        console.print("[red]Fichier introuvable[/red]")
        return None
    return path


# ==============================================================================
# ASYNC HELPERS
# ==============================================================================


async def run_with_notification(coro: Any, task_name: str, show_progress: bool = True) -> Any:
    """
    Exécuter une coroutine avec notification de fin.

    Args:
        coro: Coroutine à exécuter
        task_name: Nom de la tâche
        show_progress: Afficher spinner

    Returns:
        Résultat de la coroutine
    """
    if show_progress:
        console.print(f"[bold]⏳ {task_name}...[/bold]")

    try:
        result = await coro
        notify_completion(task_name, success=True)
        return result
    except Exception as e:
        notify_completion(task_name, success=False, details=str(e)[:100])
        raise


# ==============================================================================
# AVAILABILITY CHECK
# ==============================================================================


def get_available_features() -> dict[str, bool]:
    """Obtenir la liste des features disponibles"""
    return {
        "fuzzy_finder": HAS_ITERFZF,
        "inquirer_prompts": HAS_INQUIRERPY,
        "animated_progress": HAS_ALIVE_PROGRESS,
        "clipboard": HAS_PYPERCLIP,
        "desktop_notifications": HAS_PLYER,
        "fuzzy_matching": HAS_THEFUZZ,
    }


def print_features_status() -> None:
    """Afficher le statut des features UX"""
    from rich.table import Table

    features = get_available_features()

    table = Table(title="UX Features Status")
    table.add_column("Feature", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Library")

    libs = {
        "fuzzy_finder": "iterfzf",
        "inquirer_prompts": "InquirerPy",
        "animated_progress": "alive-progress",
        "clipboard": "pyperclip",
        "desktop_notifications": "plyer",
        "fuzzy_matching": "thefuzz",
    }

    for feature, available in features.items():
        status = "✅ Available" if available else "❌ Not installed"
        table.add_row(feature.replace("_", " ").title(), status, libs.get(feature, ""))

    console.print(table)
