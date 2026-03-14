#!/usr/bin/env python3
"""
Wizards de Configuration pour CLI Tawiza-V2
Wizards multi-étapes pour configuration guidée
"""

from dataclasses import dataclass
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.ui.interactive import FormField, InteractiveMenu, InteractivePrompt, ValidationRule

console = Console()


# ===== WIZARD BASE CLASS =====


@dataclass
class WizardStep:
    """Étape d'un wizard"""

    name: str
    title: str
    description: str
    fields: list[FormField]
    skippable: bool = False


class Wizard:
    """Classe de base pour les wizards"""

    def __init__(self, title: str, steps: list[WizardStep]):
        self.title = title
        self.steps = steps
        self.results: dict[str, Any] = {}
        self.current_step = 0

    def show_header(self, step: WizardStep):
        """Afficher le header d'une étape"""
        console.clear()
        progress = f"Step {self.current_step + 1}/{len(self.steps)}"

        console.print(
            Panel(
                f"[bold cyan]{self.title}[/]\n[dim]{progress}[/]",
                border_style="cyan",
                box=box.DOUBLE,
            )
        )
        console.print()

        console.print(
            Panel(
                f"[bold]{step.title}[/]\n[dim]{step.description}[/]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )
        console.print()

    def run_step(self, step: WizardStep) -> dict[str, Any]:
        """Exécuter une étape"""
        self.show_header(step)

        step_results = {}

        for field in step.fields:
            if field.field_type == "text":
                value = InteractivePrompt.text(
                    field.question, default=str(field.default or ""), validate=field.validate
                )

            elif field.field_type == "integer":
                value = InteractivePrompt.integer(
                    field.question,
                    default=field.default,
                    min_value=field.min_value,
                    max_value=field.max_value,
                )

            elif field.field_type == "number":
                value = InteractivePrompt.number(
                    field.question,
                    default=field.default,
                    min_value=field.min_value,
                    max_value=field.max_value,
                )

            elif field.field_type == "select":
                value = InteractiveMenu.select(
                    field.question, choices=field.choices or [], default=field.default
                )

            elif field.field_type == "multi_select":
                value = InteractiveMenu.multi_select(
                    field.question, choices=field.choices or [], default=field.default
                )

            elif field.field_type == "confirm":
                value = InteractivePrompt.confirm(field.question, default=field.default or False)

            step_results[field.name] = value

        return step_results

    def show_summary(self):
        """Afficher le résumé de configuration"""
        console.clear()
        console.print(
            Panel(
                f"[bold cyan]{self.title}[/]\n[bold green]Configuration Summary[/]",
                border_style="green",
                box=box.DOUBLE,
            )
        )
        console.print()

        table = Table(title="Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for key, value in self.results.items():
            table.add_row(key, str(value))

        console.print(table)
        console.print()

    def run(self) -> dict[str, Any]:
        """Exécuter le wizard complet"""
        for i, step in enumerate(self.steps):
            self.current_step = i
            step_results = self.run_step(step)
            self.results.update(step_results)

            # Ask to continue (except for last step)
            if i < len(self.steps) - 1:
                console.print()
                if not InteractivePrompt.confirm("Continue to next step?", default=True):
                    console.print("[yellow]Wizard cancelled[/]")
                    return {}

        # Show summary and confirm
        self.show_summary()

        if InteractivePrompt.confirm("Apply this configuration?", default=True):
            console.print()
            console.print("[bold green]✓ Configuration applied![/]")
            return self.results
        else:
            console.print()
            console.print("[yellow]✗ Configuration cancelled[/]")
            return {}


# ===== WIZARD PRÉDÉFINIS =====


def setup_wizard() -> dict[str, Any]:
    """Wizard de configuration initiale du système"""
    steps = [
        WizardStep(
            name="basic",
            title="Basic Configuration",
            description="Configure basic system settings",
            fields=[
                FormField(
                    name="project_name",
                    question="Project name:",
                    field_type="text",
                    default="Tawiza-V2",
                    validate=ValidationRule(
                        validator=lambda x: len(x) > 0, error_message="Project name cannot be empty"
                    ),
                ),
                FormField(
                    name="theme",
                    question="Select theme:",
                    field_type="select",
                    choices=["🌅 Sunset", "🌊 Ocean", "🌲 Forest", "⚡ Neon", "🌙 Midnight"],
                    default="🌅 Sunset",
                ),
            ],
        ),
        WizardStep(
            name="performance",
            title="Performance Settings",
            description="Configure performance and optimization",
            fields=[
                FormField(
                    name="workers",
                    question="Number of parallel workers:",
                    field_type="integer",
                    default=4,
                    min_value=1,
                    max_value=16,
                ),
                FormField(
                    name="cache_size",
                    question="Cache size (max entries):",
                    field_type="integer",
                    default=1000,
                    min_value=100,
                    max_value=10000,
                ),
                FormField(
                    name="enable_gpu",
                    question="Enable GPU optimization?",
                    field_type="confirm",
                    default=True,
                ),
            ],
        ),
        WizardStep(
            name="features",
            title="Features Selection",
            description="Select features to enable",
            fields=[
                FormField(
                    name="features",
                    question="Select features to enable:",
                    field_type="multi_select",
                    choices=["Smart Cache", "Auto-retry", "Monitoring", "Logging", "Benchmarking"],
                    default=["Smart Cache", "Monitoring"],
                ),
            ],
        ),
    ]

    wizard = Wizard("Tawiza-V2 Setup Wizard", steps)
    return wizard.run()


def agent_configuration_wizard() -> dict[str, Any]:
    """Wizard de configuration d'agent"""
    steps = [
        WizardStep(
            name="agent_type",
            title="Agent Type Selection",
            description="Select the type of agent to configure",
            fields=[
                FormField(
                    name="agent_type",
                    question="Select agent type:",
                    field_type="select",
                    choices=[
                        "🤖 ML Engineer",
                        "📊 Data Analyst",
                        "🔍 Code Reviewer",
                        "⚡ Optimizer",
                        "📝 Documentation Writer",
                    ],
                ),
            ],
        ),
        WizardStep(
            name="agent_config",
            title="Agent Configuration",
            description="Configure agent parameters",
            fields=[
                FormField(
                    name="priority",
                    question="Default priority:",
                    field_type="select",
                    choices=["Low", "Normal", "High", "Critical"],
                    default="Normal",
                ),
                FormField(
                    name="max_retries",
                    question="Maximum retries:",
                    field_type="integer",
                    default=3,
                    min_value=0,
                    max_value=10,
                ),
                FormField(
                    name="timeout",
                    question="Timeout (seconds):",
                    field_type="number",
                    default=300.0,
                    min_value=10.0,
                    max_value=3600.0,
                ),
                FormField(
                    name="enable_cache",
                    question="Enable caching for this agent?",
                    field_type="confirm",
                    default=True,
                ),
            ],
        ),
    ]

    wizard = Wizard("Agent Configuration Wizard", steps)
    return wizard.run()


def model_selection_wizard() -> dict[str, Any]:
    """Wizard de sélection de modèle"""
    steps = [
        WizardStep(
            name="model_type",
            title="Model Type",
            description="Select the type of model",
            fields=[
                FormField(
                    name="model_category",
                    question="Model category:",
                    field_type="select",
                    choices=[
                        "Large Language Model (LLM)",
                        "Computer Vision",
                        "Speech Recognition",
                        "Multimodal",
                    ],
                ),
            ],
        ),
        WizardStep(
            name="model_selection",
            title="Model Selection",
            description="Select specific model",
            fields=[
                FormField(
                    name="model_name",
                    question="Select model:",
                    field_type="select",
                    choices=["Qwen-Coder-7B", "Llama-3.1-8B", "Mistral-7B", "Gemma-7B"],
                ),
                FormField(
                    name="quantization",
                    question="Quantization:",
                    field_type="select",
                    choices=["None (FP16)", "8-bit", "4-bit"],
                    default="None (FP16)",
                ),
            ],
        ),
        WizardStep(
            name="deployment",
            title="Deployment Settings",
            description="Configure deployment parameters",
            fields=[
                FormField(
                    name="batch_size",
                    question="Batch size:",
                    field_type="integer",
                    default=8,
                    min_value=1,
                    max_value=128,
                ),
                FormField(
                    name="max_length",
                    question="Max sequence length:",
                    field_type="integer",
                    default=2048,
                    min_value=128,
                    max_value=8192,
                ),
                FormField(
                    name="use_flash_attention",
                    question="Use Flash Attention?",
                    field_type="confirm",
                    default=True,
                ),
            ],
        ),
    ]

    wizard = Wizard("Model Selection Wizard", steps)
    return wizard.run()


def performance_tuning_wizard() -> dict[str, Any]:
    """Wizard de tuning de performance"""
    steps = [
        WizardStep(
            name="target",
            title="Optimization Target",
            description="What do you want to optimize?",
            fields=[
                FormField(
                    name="optimization_target",
                    question="Select optimization target:",
                    field_type="multi_select",
                    choices=[
                        "Throughput",
                        "Latency",
                        "Memory Usage",
                        "GPU Utilization",
                        "Cache Hit Rate",
                    ],
                ),
            ],
        ),
        WizardStep(
            name="settings",
            title="Performance Settings",
            description="Configure performance parameters",
            fields=[
                FormField(
                    name="workers",
                    question="Number of workers:",
                    field_type="integer",
                    default=4,
                    min_value=1,
                    max_value=32,
                ),
                FormField(
                    name="queue_size",
                    question="Task queue size:",
                    field_type="integer",
                    default=1000,
                    min_value=100,
                    max_value=10000,
                ),
                FormField(
                    name="cache_strategy",
                    question="Cache strategy:",
                    field_type="select",
                    choices=["LRU", "LFU", "FIFO", "Smart"],
                    default="Smart",
                ),
            ],
        ),
        WizardStep(
            name="monitoring",
            title="Monitoring Configuration",
            description="Configure monitoring and alerts",
            fields=[
                FormField(
                    name="enable_monitoring",
                    question="Enable real-time monitoring?",
                    field_type="confirm",
                    default=True,
                ),
                FormField(
                    name="alert_threshold",
                    question="Alert threshold for CPU usage (%):",
                    field_type="integer",
                    default=90,
                    min_value=50,
                    max_value=100,
                ),
                FormField(
                    name="log_level",
                    question="Log level:",
                    field_type="select",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    default="INFO",
                ),
            ],
        ),
    ]

    wizard = Wizard("Performance Tuning Wizard", steps)
    return wizard.run()


# ===== DEMO =====

if __name__ == "__main__":
    console.clear()
    console.print(
        Panel(
            "[bold cyan]Wizards Demo[/]\n[dim]Multi-step configuration wizards[/]",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )
    console.print()

    # Choose wizard
    wizard_choice = InteractiveMenu.select(
        "Select a wizard to run:",
        choices=[
            "🚀 Setup Wizard",
            "🤖 Agent Configuration",
            "🎯 Model Selection",
            "⚡ Performance Tuning",
            "❌ Exit",
        ],
    )

    if wizard_choice == "❌ Exit":
        console.print("[yellow]Exiting...[/]")
    elif wizard_choice == "🚀 Setup Wizard":
        results = setup_wizard()
        if results:
            console.print(f"\n[green]Configuration saved:[/] {results}")
    elif wizard_choice == "🤖 Agent Configuration":
        results = agent_configuration_wizard()
        if results:
            console.print(f"\n[green]Agent configured:[/] {results}")
    elif wizard_choice == "🎯 Model Selection":
        results = model_selection_wizard()
        if results:
            console.print(f"\n[green]Model selected:[/] {results}")
    elif wizard_choice == "⚡ Performance Tuning":
        results = performance_tuning_wizard()
        if results:
            console.print(f"\n[green]Performance tuned:[/] {results}")
