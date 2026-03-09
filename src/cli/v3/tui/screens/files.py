"""Files Screen - File browser and manager."""

from datetime import datetime
from pathlib import Path

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DirectoryTree, Static


class FilePreview(Static):
    """Preview panel for selected file."""

    DEFAULT_CSS = """
    FilePreview {
        width: 100%;
        height: 100%;
        padding: 1;
        background: $surface;
    }

    FilePreview .filename {
        text-style: bold;
        color: $accent;
    }

    FilePreview .meta {
        color: $text-muted;
        margin-bottom: 1;
    }

    FilePreview .content {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._file_path: Path | None = None
        self._content: str = ""
        self._file_size: int = 0
        self._modified: datetime | None = None

    def set_file(self, path: Path) -> None:
        """Set the file to preview."""
        self._file_path = path

        if path.is_file():
            stat = path.stat()
            self._file_size = stat.st_size
            self._modified = datetime.fromtimestamp(stat.st_mtime)

            # Read file content (limit for preview)
            try:
                if self._file_size > 50000:  # 50KB limit
                    self._content = "[dim]File too large for preview[/]"
                else:
                    with open(path, errors='replace') as f:
                        self._content = f.read()[:5000]  # First 5000 chars
                        if len(self._content) == 5000:
                            self._content += "\n\n[dim]... (truncated)[/]"
            except Exception as e:
                self._content = f"[red]Cannot preview: {e}[/]"
        else:
            self._content = "[dim]Select a file to preview[/]"
            self._file_size = 0
            self._modified = None

        self.refresh()

    def render(self) -> str:
        if not self._file_path:
            return "[dim]Select a file to preview[/]"

        name = self._file_path.name
        size = self._format_size(self._file_size)
        modified = self._modified.strftime("%Y-%m-%d %H:%M") if self._modified else "N/A"

        # Syntax highlighting hint based on extension
        ext = self._file_path.suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
            '.md': 'markdown', '.html': 'html', '.css': 'css',
            '.sh': 'bash', '.sql': 'sql', '.toml': 'toml',
        }
        lang = lang_map.get(ext, 'text')

        return f"""[bold cyan]{name}[/]
[dim]Size: {size} | Modified: {modified} | Type: {lang}[/]
{'─' * 50}

{self._content}"""

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class FilesScreen(Container):
    """Files content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+o", "open_file", "^O:Open", show=True, priority=True),
        Binding("ctrl+n", "new_file", "^N:New", show=True),
        Binding("ctrl+d", "delete_file", "^D:Delete", show=True),
        Binding("ctrl+r", "refresh_tree", "^R:Refresh", show=True),
        Binding("ctrl+h", "toggle_hidden", "^H:Hidden", show=True),
        Binding("ctrl+p", "go_parent", "^P:Parent", show=True),
        Binding("enter", "select_file", "Enter:Select", show=True),
    ]

    DEFAULT_CSS = """
    FilesScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #files-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #path-display {
        width: 1fr;
        margin-left: 1;
        color: $accent;
    }

    #files-content {
        height: 1fr;
    }

    #file-tree-container {
        width: 40%;
        border-right: solid $primary;
        padding: 1;
    }

    #file-preview-container {
        width: 60%;
        padding: 1;
    }

    DirectoryTree {
        height: 100%;
        background: $surface;
    }

    #file-stats {
        height: 2;
        padding: 0 1;
        border-top: solid $primary;
        background: $surface-darken-1;
    }
    """

    current_path = reactive(Path.cwd())
    show_hidden = reactive(False)
    selected_file = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from src.cli.constants import PROJECT_ROOT
        self._project_root = PROJECT_ROOT

    def compose(self) -> ComposeResult:
        """Create the files layout."""
        # Header with path
        with Horizontal(id="files-header"):
            yield Static("[bold cyan]FILES[/] - Project file browser")
            yield Static(str(self._project_root), id="path-display")

        # Content: tree + preview
        with Horizontal(id="files-content"):
            with Vertical(id="file-tree-container"):
                yield DirectoryTree(
                    str(self._project_root),
                    id="file-tree"
                )

            with Vertical(id="file-preview-container"):
                yield FilePreview(id="file-preview")

        # Stats bar
        yield Static("", id="file-stats")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._update_stats()
        tree = self.query_one("#file-tree", DirectoryTree)
        tree.show_root = True
        tree.guide_depth = 3

    def _update_stats(self) -> None:
        """Update the stats bar."""
        try:
            # Count files in current directory
            path = self._project_root
            files = list(path.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            dir_count = sum(1 for f in files if f.is_dir())

            # Get total size
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            size_str = self._format_size(total_size)

            stats = self.query_one("#file-stats", Static)
            stats.update(
                f"[cyan]{file_count}[/] files | "
                f"[yellow]{dir_count}[/] directories | "
                f"[green]{size_str}[/] total | "
                f"Hidden: {'ON' if self.show_hidden else 'OFF'}"
            )
        except Exception as e:
            logger.warning(f"Failed to update stats: {e}")

    def _format_size(self, size: int) -> str:
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in tree."""
        path = Path(event.path)
        self.selected_file = path

        # Update preview
        preview = self.query_one("#file-preview", FilePreview)
        preview.set_file(path)

        # Update path display
        path_display = self.query_one("#path-display", Static)
        path_display.update(str(path))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection."""
        path = Path(event.path)

        # Update path display
        path_display = self.query_one("#path-display", Static)
        path_display.update(str(path))

    def action_open_file(self) -> None:
        """Open selected file in editor."""
        if self.selected_file and self.selected_file.is_file():
            self.app.notify(f"Opening: {self.selected_file.name}", timeout=2)
            # In a full implementation, this would open an editor
        else:
            self.app.notify("No file selected", timeout=2)

    def action_new_file(self) -> None:
        """Create a new file."""
        self.app.notify("New file dialog coming soon!", timeout=2)

    def action_delete_file(self) -> None:
        """Delete selected file."""
        if self.selected_file:
            self.app.notify(f"Delete: {self.selected_file.name}? (Not implemented)", timeout=2)
        else:
            self.app.notify("No file selected", timeout=2)

    def action_refresh_tree(self) -> None:
        """Refresh the file tree."""
        tree = self.query_one("#file-tree", DirectoryTree)
        tree.reload()
        self._update_stats()
        self.app.notify("File tree refreshed", timeout=1)

    def action_toggle_hidden(self) -> None:
        """Toggle hidden file visibility."""
        self.show_hidden = not self.show_hidden
        tree = self.query_one("#file-tree", DirectoryTree)
        tree.show_hidden = self.show_hidden
        tree.reload()
        self._update_stats()
        status = "shown" if self.show_hidden else "hidden"
        self.app.notify(f"Hidden files: {status}", timeout=1)

    def action_go_parent(self) -> None:
        """Navigate to parent directory."""
        tree = self.query_one("#file-tree", DirectoryTree)
        # Navigate to parent of current root
        parent = Path(tree.path).parent
        if parent.exists():
            tree.path = str(parent)
            tree.reload()
            path_display = self.query_one("#path-display", Static)
            path_display.update(str(parent))
            self._update_stats()

    def action_select_file(self) -> None:
        """Confirm file selection."""
        if self.selected_file:
            self.app.notify(f"Selected: {self.selected_file.name}", timeout=1)
