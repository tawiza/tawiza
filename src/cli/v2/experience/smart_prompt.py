"""Smart prompt - context-aware welcome and suggestions."""

from dataclasses import dataclass, field
from pathlib import Path

from src.cli.v2.ui.mascot import MASCOT


@dataclass
class ProjectContext:
    """Detected project context."""

    project_type: str = "unknown"
    data_files: list[Path] = field(default_factory=list)
    has_git: bool = False
    has_tests: bool = False
    main_language: str = "unknown"


class SmartPrompt:
    """Context-aware welcome screen and suggestions."""

    def __init__(self):
        self._recent_tasks: list[str] = []

    def render_welcome(self, version: str = "2.0") -> str:
        """Render the welcome screen with mascot and status.

        Args:
            version: Version string to display

        Returns:
            Welcome screen string
        """
        lines = MASCOT.get_art("default")
        lines.append("")
        lines.append(f"                    ─── tawiza v{version} ───")
        lines.append("")

        # Status line
        lines.append("   ● System: ready    ● Agents: online")
        lines.append("")

        # Recent tasks if any
        if self._recent_tasks:
            lines.append("   Recent:")
            for task in self._recent_tasks[-3:]:
                lines.append(f'     "{task[:40]}..."' if len(task) > 40 else f'     "{task}"')
            lines.append("")

        lines.append("   What would you like to do?")
        lines.append("")
        lines.append("   [data] [code] [browse] [ask]")

        return "\n".join(lines)

    def detect_context(self, path: Path) -> ProjectContext:
        """Detect project context from directory.

        Args:
            path: Directory to analyze

        Returns:
            ProjectContext with detected info
        """
        context = ProjectContext()

        # Detect project type
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            context.project_type = "python"
            context.main_language = "python"
        elif (path / "package.json").exists():
            context.project_type = "node"
            context.main_language = "javascript"
        elif (path / "Cargo.toml").exists():
            context.project_type = "rust"
            context.main_language = "rust"
        elif (path / "go.mod").exists():
            context.project_type = "go"
            context.main_language = "go"
        else:
            # Detect by file extensions
            py_files = list(path.glob("*.py"))
            if py_files:
                context.project_type = "python"
                context.main_language = "python"
            elif list(path.glob("*.js")) or list(path.glob("*.ts")):
                context.project_type = "node"
                context.main_language = "javascript"
            elif list(path.glob("*.rs")):
                context.project_type = "rust"
                context.main_language = "rust"
            elif list(path.glob("*.go")):
                context.project_type = "go"
                context.main_language = "go"

        # Find data files
        data_extensions = {".csv", ".json", ".xlsx", ".parquet"}
        for ext in data_extensions:
            context.data_files.extend(path.glob(f"*{ext}"))

        # Check for git
        context.has_git = (path / ".git").exists()

        # Check for tests
        context.has_tests = (path / "tests").exists() or (path / "test").exists()

        return context

    def get_suggestions(self, context: ProjectContext) -> list[str]:
        """Generate suggestions based on context.

        Args:
            context: Detected project context

        Returns:
            List of suggested actions
        """
        suggestions = []

        if context.data_files:
            file_name = context.data_files[0].name
            suggestions.append(f"analyze {file_name}")

        if context.project_type == "python":
            suggestions.append("run tests")
            suggestions.append("review code")

        if context.has_git:
            suggestions.append("show git status")

        if not suggestions:
            suggestions.append("help me get started")

        return suggestions

    def add_recent_task(self, task: str) -> None:
        """Add a task to recent history.

        Args:
            task: Task description
        """
        # Remove if already exists (move to end)
        if task in self._recent_tasks:
            self._recent_tasks.remove(task)
        self._recent_tasks.append(task)

        # Keep only last 10
        if len(self._recent_tasks) > 10:
            self._recent_tasks = self._recent_tasks[-10:]

    def get_recent_tasks(self) -> list[str]:
        """Get recent tasks.

        Returns:
            List of recent task descriptions
        """
        return list(self._recent_tasks)
