"""Unified Learning CLI commands.

Provides commands for the UAA learning pipeline:
- pipeline: Manage the learning pipeline
- annotate: Push/pull annotations to/from Label Studio
- train: Train model with collected data
- export: Export dataset for training
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.utils.async_runner import run_async

console = Console()
app = typer.Typer(
    name="learning",
    help="UAA Learning Pipeline - Annotation, Training & Deployment",
    no_args_is_help=True,
)

# Global pipeline instance
_pipeline_instance = None


def get_pipeline():
    """Get or create the learning pipeline."""
    global _pipeline_instance
    if _pipeline_instance is None:
        from src.infrastructure.learning import UnifiedLearningPipeline
        _pipeline_instance = UnifiedLearningPipeline()
    return _pipeline_instance


@app.command("status")
def status():
    """Show learning pipeline status."""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()

    table = Table(title="Learning Pipeline Status", box=None)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", justify="right")

    table.add_row("Examples Collected", f"[green]{stats['examples_collected']}[/green]")
    table.add_row("Candidates Queued", f"[yellow]{stats['candidates_queued']}[/yellow]")
    table.add_row("Training Runs", str(stats['training_runs']))
    table.add_row(
        "Avg Instruction Length",
        f"{stats['dataset_stats']['avg_instruction_len']:.0f} chars",
    )
    table.add_row(
        "Avg Output Length",
        f"{stats['dataset_stats']['avg_output_len']:.0f} chars",
    )

    console.print(Panel(table, border_style="blue"))


@app.command("push")
def push_for_annotation(
    max_candidates: int = typer.Option(50, "--max", "-m", help="Maximum candidates to push"),
    project_name: str = typer.Option("UAA Training", "--project", "-p", help="Label Studio project name"),
):
    """Push candidates to Label Studio for annotation.

    Uses active learning to prioritize the most valuable examples.
    """
    pipeline = get_pipeline()

    console.print("[cyan]Pushing candidates to Label Studio...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Pushing candidates...", total=None)

        # Create project if needed
        if not pipeline.label_studio.config.project_id:
            project_id = run_async(
                pipeline.label_studio.create_annotation_project(project_name)
            )
            if project_id:
                console.print(f"[green]Created project: {project_id}[/green]")

        num_pushed = run_async(pipeline.push_for_annotation(max_candidates))

    if num_pushed > 0:
        console.print(Panel(
            f"[green]Pushed {num_pushed} candidates for annotation[/green]\n\n"
            f"Open Label Studio to annotate:\n"
            f"[cyan]http://localhost:8080/projects/{pipeline.label_studio.config.project_id}[/cyan]",
            title="Success",
            border_style="green",
        ))
    else:
        console.print("[yellow]No candidates to push (queue empty or Label Studio unavailable)[/yellow]")


@app.command("pull")
def pull_annotations():
    """Pull completed annotations from Label Studio.

    Adds validated annotations to the training dataset.
    """
    pipeline = get_pipeline()

    console.print("[cyan]Pulling annotations from Label Studio...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Pulling annotations...", total=None)
        num_pulled = run_async(pipeline.pull_annotations())

    if num_pulled > 0:
        console.print(Panel(
            f"[green]Pulled {num_pulled} quality annotations[/green]\n\n"
            f"Total examples: {pipeline.dataset_builder.stats.total_examples}",
            title="Success",
            border_style="green",
        ))
    else:
        console.print("[yellow]No new annotations found[/yellow]")


@app.command("train")
def train(
    model_name: str | None = typer.Option(None, "--name", "-n", help="Model name"),
    base_model: str = typer.Option("qwen2.5-coder:7b", "--base", "-b", help="Base model"),
    epochs: int = typer.Option(3, "--epochs", "-e", help="Training epochs"),
    batch_size: int = typer.Option(4, "--batch", help="Batch size"),
    use_lora: bool = typer.Option(True, "--lora/--full", help="Use LoRA fine-tuning"),
):
    """Train model with collected examples.

    Uses LLaMA-Factory for fine-tuning with LoRA.
    """
    from src.infrastructure.learning import LlamaFactoryConfig

    pipeline = get_pipeline()

    # Check if we have enough examples
    stats = pipeline.get_stats()
    if stats["examples_collected"] < 10:
        console.print(Panel(
            f"[red]Not enough examples[/red]\n\n"
            f"Have: {stats['examples_collected']}\n"
            f"Need: at least 10\n\n"
            f"Use [cyan]tawiza learning push[/cyan] and annotate in Label Studio first",
            title="Cannot Train",
            border_style="red",
        ))
        raise typer.Exit(1)

    # Update config
    pipeline.llama_factory.config = LlamaFactoryConfig(
        base_model=base_model,
        num_epochs=epochs,
        batch_size=batch_size,
        use_lora=use_lora,
    )

    console.print(Panel(
        f"[bold]Training Configuration[/bold]\n\n"
        f"Base Model: {base_model}\n"
        f"Examples: {stats['examples_collected']}\n"
        f"Epochs: {epochs}\n"
        f"Batch Size: {batch_size}\n"
        f"Method: {'LoRA' if use_lora else 'Full'}",
        title="Starting Training",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Training model...", total=None)
        result = run_async(pipeline.train(model_name))

    if result.get("success"):
        console.print(Panel(
            f"[green]Training completed successfully![/green]\n\n"
            f"Run ID: {result.get('run_id', 'N/A')}\n"
            f"Output: {result.get('output_dir', 'N/A')}",
            title="Training Complete",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Training failed[/red]\n\n"
            f"Error: {result.get('error', 'Unknown error')}",
            title="Training Failed",
            border_style="red",
        ))


@app.command("export")
def export_dataset(
    output: Path = typer.Option("data/uaa_dataset.jsonl", "--output", "-o", help="Output path"),
    format: str = typer.Option("jsonl", "--format", "-f", help="Format: jsonl, alpaca, sharegpt"),
):
    """Export collected examples as a dataset file.

    Formats:
    - jsonl: Simple JSON lines (instruction, output)
    - alpaca: Alpaca format (instruction, input, output)
    - sharegpt: ShareGPT format (conversations)
    """
    from src.infrastructure.learning import DatasetFormat

    format_map = {
        "jsonl": DatasetFormat.JSONL,
        "alpaca": DatasetFormat.ALPACA,
        "sharegpt": DatasetFormat.SHAREGPT,
    }

    if format.lower() not in format_map:
        console.print(f"[red]Unknown format: {format}. Use: jsonl, alpaca, sharegpt[/red]")
        raise typer.Exit(1)

    pipeline = get_pipeline()

    if pipeline.dataset_builder.stats.total_examples == 0:
        console.print("[yellow]No examples to export[/yellow]")
        raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    saved_path = pipeline.dataset_builder.save(str(output), format_map[format.lower()])

    console.print(Panel(
        f"[green]Dataset exported successfully![/green]\n\n"
        f"Path: {saved_path}\n"
        f"Format: {format}\n"
        f"Examples: {pipeline.dataset_builder.stats.total_examples}",
        title="Export Complete",
        border_style="green",
    ))


@app.command("import")
def import_dataset(
    input_file: Path = typer.Argument(..., help="Dataset file to import"),
    format: str = typer.Option("jsonl", "--format", "-f", help="Format: jsonl, alpaca, sharegpt"),
):
    """Import examples from an existing dataset file.

    Adds examples to the learning pipeline for training.
    """
    from src.infrastructure.learning import DatasetExample

    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        raise typer.Exit(1)

    pipeline = get_pipeline()

    try:
        with open(input_file) as f:
            if format.lower() == "jsonl":
                for line in f:
                    data = json.loads(line)
                    example = DatasetExample(
                        instruction=data.get("instruction", ""),
                        output=data.get("output", ""),
                        input=data.get("input", ""),
                    )
                    pipeline.dataset_builder.add_example(example)

            elif format.lower() == "alpaca":
                data = json.load(f)
                for item in data:
                    example = DatasetExample(
                        instruction=item.get("instruction", ""),
                        output=item.get("output", ""),
                        input=item.get("input", ""),
                    )
                    pipeline.dataset_builder.add_example(example)

            elif format.lower() == "sharegpt":
                data = json.load(f)
                for item in data:
                    conversations = item.get("conversations", [])
                    if len(conversations) >= 2:
                        example = DatasetExample(
                            instruction=conversations[0].get("value", ""),
                            output=conversations[1].get("value", ""),
                        )
                        pipeline.dataset_builder.add_example(example)

        console.print(Panel(
            f"[green]Dataset imported successfully![/green]\n\n"
            f"Total examples: {pipeline.dataset_builder.stats.total_examples}",
            title="Import Complete",
            border_style="green",
        ))

    except Exception as e:
        console.print(f"[red]Error importing: {e}[/red]")
        raise typer.Exit(1)


@app.command("add")
def add_example(
    instruction: str = typer.Argument(..., help="Instruction/query"),
    output: str = typer.Argument(..., help="Expected output/response"),
    input_text: str | None = typer.Option("", "--input", "-i", help="Additional input context"),
):
    """Manually add a training example.

    Useful for adding specific examples you want the model to learn.
    """
    from src.infrastructure.learning import DatasetExample

    pipeline = get_pipeline()

    example = DatasetExample(
        instruction=instruction,
        output=output,
        input=input_text,
    )
    pipeline.dataset_builder.add_example(example)

    console.print(Panel(
        f"[green]Example added![/green]\n\n"
        f"Instruction: {instruction[:50]}...\n"
        f"Output: {output[:50]}...\n\n"
        f"Total examples: {pipeline.dataset_builder.stats.total_examples}",
        title="Example Added",
        border_style="green",
    ))


@app.command("full-cycle")
def full_cycle(
    model_name: str | None = typer.Option(None, "--name", "-n", help="Model name"),
):
    """Run full learning cycle: pull annotations → train → deploy.

    This is the main command for automated learning.
    """
    pipeline = get_pipeline()

    console.print("[bold cyan]Starting Full Learning Cycle[/bold cyan]\n")

    # Step 1: Pull annotations
    console.print("[cyan]Step 1: Pulling annotations from Label Studio...[/cyan]")
    num_pulled = run_async(pipeline.pull_annotations())
    console.print(f"  Pulled {num_pulled} new annotations")

    # Check if we have enough
    stats = pipeline.get_stats()
    if stats["examples_collected"] < 10:
        console.print(Panel(
            f"[yellow]Not enough examples yet[/yellow]\n\n"
            f"Have: {stats['examples_collected']}\n"
            f"Need: at least 10\n\n"
            f"Continue annotating in Label Studio",
            title="Waiting for More Data",
            border_style="yellow",
        ))
        return

    # Step 2: Train
    console.print("\n[cyan]Step 2: Training model...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Training...", total=None)
        result = run_async(pipeline.train(model_name))

    if result.get("success"):
        console.print(Panel(
            f"[green]Learning cycle completed![/green]\n\n"
            f"Model: {result.get('output_dir', 'N/A')}\n"
            f"Examples trained: {stats['examples_collected']}\n\n"
            f"Next steps:\n"
            f"1. Deploy with: [cyan]tawiza uaa config --set-model {result.get('output_dir')}[/cyan]\n"
            f"2. Continue collecting feedback",
            title="Cycle Complete",
            border_style="green",
        ))
    else:
        console.print(f"[red]Training failed: {result.get('error')}[/red]")
