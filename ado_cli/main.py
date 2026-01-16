"""Azure DevOps CLI - Main entrypoint."""

import re
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ado_cli.client import AzureDevOpsClient
from ado_cli.config import clear_config_cache, get_config, save_config
from ado_cli.exceptions import AdoCliError

app = typer.Typer(name="ado", help="Azure DevOps CLI", no_args_is_help=True)
item_app = typer.Typer(help="Work item operations")
comment_app = typer.Typer(help="Comment operations")
sprint_app = typer.Typer(help="Sprint operations")

app.add_typer(item_app, name="item")
app.add_typer(comment_app, name="comment")
app.add_typer(sprint_app, name="sprint")

console = Console()


def get_client() -> AzureDevOpsClient:
    config = get_config()
    config.validate_or_raise()
    return AzureDevOpsClient(config)


def handle_error(e: Exception) -> None:
    if isinstance(e, AdoCliError):
        console.print(f"[red]Error:[/red] {e.message}")
        if e.details:
            console.print(f"[dim]{e.details}[/dim]")
    else:
        console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(1)


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    for old, new in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')]:
        text = text.replace(old, new)
    return text.strip()


@app.command()
def config(show: Annotated[bool, typer.Option("--show", "-s")] = False):
    """Configure Azure DevOps connection."""
    if show:
        cfg = get_config()
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Organization", cfg.organization or "[red]Not set[/red]")
        table.add_row("Project", cfg.project or "[red]Not set[/red]")
        table.add_row("PAT", "***" if cfg.pat else "[red]Not set[/red]")
        table.add_row("Team", cfg.team or "[dim](defaults to project)[/dim]")
        table.add_row("Status", "[green]OK[/green]" if cfg.is_configured() else "[red]Incomplete[/red]")
        console.print(table)
        return

    console.print(Panel("Azure DevOps Configuration", style="bold blue"))
    organization = Prompt.ask("Organization")
    project = Prompt.ask("Project")
    pat = Prompt.ask("PAT", password=True)
    team = Prompt.ask("Team (optional)", default="")

    save_config(organization, project, pat, team)
    clear_config_cache()
    console.print("[green]✓ Saved to ~/.ado-cli/config.yaml[/green]")

    if Confirm.ask("Test connection?", default=True):
        try:
            with get_client() as client:
                client.test_connection()
                console.print("[green]✓ Connected[/green]")
        except Exception as e:
            handle_error(e)


@app.command()
def test():
    """Test connection to Azure DevOps."""
    try:
        with get_client() as client:
            client.test_connection()
            cfg = get_config()
            console.print(f"[green]✓ Connected to {cfg.organization}/{cfg.project}[/green]")
    except Exception as e:
        handle_error(e)


@item_app.command("list")
def item_list(state: Annotated[Optional[str], typer.Option("--state", "-s")] = None):
    """List my work items."""
    try:
        with get_client() as client:
            items = client.get_my_work_items(state=state)
            if not items:
                console.print("[yellow]No work items found[/yellow]")
                return

            table = Table(title=f"My Work Items ({len(items)})", header_style="bold")
            table.add_column("ID", style="cyan", justify="right", width=7)
            table.add_column("Type", style="magenta", width=10)
            table.add_column("State", style="green", width=14)
            table.add_column("Title", width=50, overflow="ellipsis")
            table.add_column("Rem", style="yellow", justify="right", width=4)

            for item in items:
                rem = str(int(item.remaining_work)) if item.remaining_work else "-"
                table.add_row(str(item.id), item.work_item_type, item.state, item.title, rem)
            console.print(table)
    except Exception as e:
        handle_error(e)


@item_app.command("get")
def item_get(work_item_id: Annotated[int, typer.Argument()]):
    """Get work item details."""
    try:
        with get_client() as client:
            item = client.get_work_item(work_item_id)
            cfg = get_config()

            info = f"""[cyan]ID:[/cyan] {item.id}
[cyan]Type:[/cyan] {item.work_item_type}
[cyan]Title:[/cyan] {item.title}
[cyan]State:[/cyan] {item.state}
[cyan]Assigned To:[/cyan] {item.assigned_to.display_name if item.assigned_to else 'Unassigned'}
[cyan]Iteration:[/cyan] {item.iteration_path}
[cyan]Area:[/cyan] {item.area_path}

[cyan]Story Points:[/cyan] {item.story_points or '-'}
[cyan]Original Estimate:[/cyan] {item.original_estimate or '-'}
[cyan]Remaining Work:[/cyan] {item.remaining_work or '-'}
[cyan]Completed Work:[/cyan] {item.completed_work or '-'}

[cyan]Tags:[/cyan] {item.tags or '-'}
[cyan]URL:[/cyan] {cfg.web_url}/{item.id}"""

            console.print(Panel(info, title=f"Work Item {item.id}", border_style="blue"))
            if item.description:
                console.print(Panel(strip_html(item.description), title="Description", border_style="dim"))
    except Exception as e:
        handle_error(e)


@item_app.command("create")
def item_create(
    title: Annotated[str, typer.Argument()],
    work_type: Annotated[str, typer.Option("--type", "-t")] = "Story",
    description: Annotated[Optional[str], typer.Option("--desc", "-d")] = None,
    state: Annotated[Optional[str], typer.Option("--state", "-s")] = None,
    remaining: Annotated[Optional[float], typer.Option("--remaining", "-r")] = None,
    estimate: Annotated[Optional[float], typer.Option("--estimate", "-e")] = None,
    completed: Annotated[Optional[float], typer.Option("--completed", "-c")] = None,
    points: Annotated[Optional[float], typer.Option("--points", "-p")] = None,
    target_date: Annotated[Optional[str], typer.Option("--target-date")] = None,
    labels: Annotated[Optional[str], typer.Option("--labels")] = None,
    pii_impact: Annotated[Optional[str], typer.Option("--pii-impact")] = None,
    load_testing: Annotated[Optional[str], typer.Option("--load-testing")] = None,
    sprint_committed: Annotated[Optional[str], typer.Option("--sprint-committed")] = None,
    iteration: Annotated[Optional[str], typer.Option("--iteration")] = None,
    area: Annotated[Optional[str], typer.Option("--area")] = None,
):
    """Create a new work item."""
    try:
        with get_client() as client:
            item = client.create_work_item(
                work_item_type=work_type,
                title=title,
                description=description,
                state=state,
                remaining_work=remaining,
                original_estimate=estimate,
                completed_work=completed,
                story_points=points,
                target_date=target_date,
                labels=labels,
                pii_impact=pii_impact,
                load_testing=load_testing,
                sprint_committed=sprint_committed,
                iteration_path=iteration,
                area_path=area,
            )
            cfg = get_config()
            console.print(f"[green]✓ Created {item.work_item_type} #{item.id}:[/green] {item.title}")
            console.print(f"[dim]{cfg.web_url}/{item.id}[/dim]")
    except Exception as e:
        handle_error(e)


@item_app.command("update")
def item_update(
    work_item_id: Annotated[int, typer.Argument()],
    state: Annotated[Optional[str], typer.Option("--state", "-s")] = None,
    title: Annotated[Optional[str], typer.Option("--title", "-t")] = None,
    description: Annotated[Optional[str], typer.Option("--desc", "-d")] = None,
    remaining: Annotated[Optional[float], typer.Option("--remaining", "-r")] = None,
    points: Annotated[Optional[float], typer.Option("--points", "-p")] = None,
    estimate: Annotated[Optional[float], typer.Option("--estimate", "-e")] = None,
    completed: Annotated[Optional[float], typer.Option("--completed", "-c")] = None,
    interactive: Annotated[bool, typer.Option("--interactive", "-i")] = False,
):
    """Update a work item."""
    try:
        with get_client() as client:
            if interactive:
                current = client.get_work_item(work_item_id)
                console.print(f"[cyan]Updating #{work_item_id}[/cyan] [dim](Enter to keep)[/dim]\n")

                new_title = Prompt.ask("Title", default=current.title)
                new_state = Prompt.ask("State", default=current.state)
                new_rem = Prompt.ask("Remaining", default=str(current.remaining_work or ""))
                new_desc = Prompt.ask("Description", default="")

                updates = {}
                if new_title != current.title:
                    updates["title"] = new_title
                if new_state != current.state:
                    updates["state"] = new_state
                if new_rem and new_rem != str(current.remaining_work):
                    updates["remaining_work"] = float(new_rem)
                if new_desc:
                    updates["description"] = new_desc

                if not updates:
                    console.print("[yellow]No changes[/yellow]")
                    return
                state, title, description, remaining = updates.get("state"), updates.get("title"), updates.get("description"), updates.get("remaining_work")

            updates = {}
            if state:
                updates["state"] = state
            if title:
                updates["title"] = title
            if description:
                updates["description"] = description
            if remaining is not None:
                updates["remaining_work"] = remaining
            if points is not None:
                updates["story_points"] = points
            if estimate is not None:
                updates["original_estimate"] = estimate
            if completed is not None:
                updates["completed_work"] = completed

            if not updates:
                console.print("[yellow]No fields specified[/yellow]")
                raise typer.Exit(1)

            item = client.update_work_item(work_item_id, **updates)
            console.print(f"[green]✓ Updated #{item.id}[/green]")
            for k, v in updates.items():
                console.print(f"  [cyan]{k}:[/cyan] {v}")
    except Exception as e:
        handle_error(e)


@item_app.command("delete")
def item_delete(
    work_item_id: Annotated[int, typer.Argument()],
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
    destroy: Annotated[bool, typer.Option("--destroy")] = False,
):
    """Delete a work item."""
    try:
        if not force:
            action = "permanently delete" if destroy else "delete"
            if not Confirm.ask(f"{action.capitalize()} #{work_item_id}?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        with get_client() as client:
            client.delete_work_item(work_item_id, destroy=destroy)
            console.print(f"[green]✓ Deleted #{work_item_id}[/green]")
    except Exception as e:
        handle_error(e)


@comment_app.command("list")
def comment_list(work_item_id: Annotated[int, typer.Argument()]):
    """List comments on a work item."""
    try:
        with get_client() as client:
            comments = client.get_comments(work_item_id)
            if not comments:
                console.print(f"[yellow]No comments on #{work_item_id}[/yellow]")
                return

            console.print(f"[cyan]Comments on #{work_item_id}[/cyan]\n")
            for c in comments:
                author = c.created_by.display_name if c.created_by else "Unknown"
                date = c.created_date.strftime("%Y-%m-%d %H:%M") if c.created_date else ""
                console.print(f"[dim]─── {author} • {date} ───[/dim]")
                console.print(strip_html(c.text))
                console.print()
    except Exception as e:
        handle_error(e)


@comment_app.command("add")
def comment_add(
    work_item_id: Annotated[int, typer.Argument()],
    text: Annotated[Optional[str], typer.Argument()] = None,
):
    """Add a comment to a work item."""
    try:
        if not text:
            text = Prompt.ask("Comment")
            if not text:
                console.print("[yellow]No comment[/yellow]")
                return

        with get_client() as client:
            comment = client.add_comment(work_item_id, text)
            console.print(f"[green]✓ Added comment to #{work_item_id}[/green] [dim](ID: {comment.id})[/dim]")
    except Exception as e:
        handle_error(e)


@sprint_app.command("board")
def sprint_board(user: Annotated[Optional[str], typer.Option("--user", "-u")] = None):
    """Show current sprint board."""
    try:
        with get_client() as client:
            try:
                iteration = client.get_current_iteration()
                if iteration:
                    console.print(f"[cyan]Sprint:[/cyan] {iteration.name}")
                    if iteration.start_date and iteration.finish_date:
                        console.print(f"[dim]{iteration.start_date:%Y-%m-%d} → {iteration.finish_date:%Y-%m-%d}[/dim]")
                    console.print()
            except Exception:
                pass

            items = client.get_sprint_work_items(user=user)
            if not items:
                console.print(f"[yellow]No items in sprint for {user or 'you'}[/yellow]")
                return

            by_state: dict[str, list] = {}
            for item in items:
                by_state.setdefault(item.state, []).append(item)

            for state, state_items in by_state.items():
                table = Table(title=f"{state} ({len(state_items)})", header_style="bold")
                table.add_column("ID", style="cyan", justify="right", width=7)
                table.add_column("Type", style="magenta", width=10)
                table.add_column("Title", width=55, overflow="ellipsis")
                table.add_column("Rem", style="yellow", justify="right", width=4)

                for item in state_items:
                    rem = str(int(item.remaining_work)) if item.remaining_work else "-"
                    table.add_row(str(item.id), item.work_item_type, item.title, rem)
                console.print(table)
                console.print()
    except Exception as e:
        handle_error(e)


@sprint_app.command("summary")
def sprint_summary(user: Annotated[Optional[str], typer.Option("--user", "-u")] = None):
    """Show sprint effort summary."""
    try:
        with get_client() as client:
            try:
                iteration = client.get_current_iteration()
                if iteration:
                    console.print(f"[cyan]Sprint:[/cyan] {iteration.name}")
                    if iteration.start_date and iteration.finish_date:
                        console.print(f"[dim]{iteration.start_date:%Y-%m-%d} → {iteration.finish_date:%Y-%m-%d}[/dim]")
                    console.print()
            except Exception:
                pass

            items = client.get_sprint_work_items(user=user)
            if not items:
                console.print(f"[yellow]No items for {user or 'you'}[/yellow]")
                return

            total_original = sum(i.original_estimate or 0 for i in items)
            total_remaining = sum(i.remaining_work or 0 for i in items)
            total_completed = sum(i.completed_work or 0 for i in items)
            total_points = sum(i.story_points or 0 for i in items)

            by_state: dict[str, int] = {}
            for item in items:
                by_state[item.state] = by_state.get(item.state, 0) + 1

            table = Table(title="Sprint Summary", header_style="bold")
            table.add_column("Metric", style="cyan", width=20)
            table.add_column("Value", style="green", justify="right", width=10)

            table.add_row("Total Items", str(len(items)))
            table.add_row("Story Points", f"{total_points:.1f}" if total_points else "-")
            table.add_row("Original Estimate", f"{total_original:.1f}h" if total_original else "-")
            table.add_row("Completed Work", f"{total_completed:.1f}h" if total_completed else "-")
            table.add_row("Remaining Work", f"{total_remaining:.1f}h" if total_remaining else "-")

            if total_original > 0:
                table.add_row("Progress", f"{(total_completed / total_original) * 100:.0f}%")

            console.print(table)
            console.print()

            state_table = Table(title="By State", header_style="bold")
            state_table.add_column("State", style="magenta", width=20)
            state_table.add_column("Count", style="yellow", justify="right", width=10)
            for state, count in sorted(by_state.items()):
                state_table.add_row(state, str(count))
            console.print(state_table)
    except Exception as e:
        handle_error(e)


@sprint_app.command("list")
def sprint_list():
    """List all sprints."""
    try:
        with get_client() as client:
            iterations = client.get_iterations()
            if not iterations:
                console.print("[yellow]No iterations found[/yellow]")
                return

            table = Table(title="Sprints")
            table.add_column("Name", style="cyan")
            table.add_column("Start", style="dim")
            table.add_column("End", style="dim")
            table.add_column("Status", style="green")

            for i in iterations:
                start = i.start_date.strftime("%Y-%m-%d") if i.start_date else "-"
                end = i.finish_date.strftime("%Y-%m-%d") if i.finish_date else "-"
                status = "[green]● Current[/green]" if i.is_current else i.time_frame
                table.add_row(i.name, start, end, status)
            console.print(table)
    except Exception as e:
        handle_error(e)


@app.command("my")
def my_items():
    """List my work items."""
    item_list(state=None)


@app.command("board")
def board(user: Annotated[Optional[str], typer.Option("--user", "-u")] = None):
    """Show sprint board."""
    sprint_board(user=user)


if __name__ == "__main__":
    app()
