"""Rich formatting utilities for CLI output."""

import json
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

# Shared console instance
console = Console()


class OutputFormat(str, Enum):
    """Output format options for CLI commands."""

    TABLE = "table"
    JSON = "json"


# Type annotation for the --format option
FormatOption = typer.Option(
    OutputFormat.TABLE,
    "--format",
    "-f",
    help="Output format: table (default) or json",
    case_sensitive=False,
)


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for objects not serializable by default.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(data: Any, indent: int = 2) -> str:
    """Convert data to formatted JSON string.

    Args:
        data: Data to convert
        indent: Indentation level for pretty printing

    Returns:
        JSON string
    """
    return json.dumps(data, default=json_serializer, indent=indent)


def print_json(data: Any):
    """Print data as formatted JSON.

    Args:
        data: Data to print as JSON
    """
    console.print(to_json(data))


def output_list(
    items: list[Any],
    format: OutputFormat,
    table_title: str,
    columns: list[tuple],
    row_builder: Callable[[Any], list[str]],
    json_builder: Callable[[Any], dict],
):
    """Output a list of items in the specified format.

    Args:
        items: List of items to output
        format: Output format (table or json)
        table_title: Title for table output
        columns: Column definitions for table [(name, style, no_wrap), ...]
        row_builder: Function to build table row from an item
        json_builder: Function to build JSON dict from an item
    """
    if format == OutputFormat.JSON:
        json_data = [json_builder(item) for item in items]
        print_json(json_data)
    else:
        table = create_table(table_title, columns)
        for item in items:
            row = row_builder(item)
            table.add_row(*row)
        console.print(table)


def output_item(
    item: Any,
    format: OutputFormat,
    panel_builder: Callable[[Any], None],
    json_builder: Callable[[Any], dict],
):
    """Output a single item in the specified format.

    Args:
        item: Item to output
        format: Output format (table or json)
        panel_builder: Function to display item as rich panel/text
        json_builder: Function to build JSON dict from item
    """
    if format == OutputFormat.JSON:
        print_json(json_builder(item))
    else:
        panel_builder(item)


def format_timestamp(dt: datetime | None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime for display.

    Args:
        dt: DateTime to format
        format_str: strftime format string

    Returns:
        Formatted string or "N/A" if dt is None
    """
    if not dt:
        return "N/A"
    return dt.strftime(format_str)


def format_date(dt: datetime | None) -> str:
    """Format datetime as date only.

    Args:
        dt: DateTime to format

    Returns:
        Formatted date string or "N/A" if dt is None
    """
    return format_timestamp(dt, "%Y-%m-%d")


def get_status_color(status: str) -> str:
    """Map status to rich style.

    Args:
        status: Status string

    Returns:
        Rich style color name
    """
    status_colors = {
        "active": "green",
        "inactive": "yellow",
        "archived": "dim",
        "error": "red",
        "completed": "green",
        "failed": "red",
        "running": "yellow",
        "pending": "blue",
    }
    return status_colors.get(status.lower(), "white")


def create_table(title: str, columns: list[tuple]) -> Table:
    """Create a Rich table with specified columns.

    Args:
        title: Table title
        columns: List of (column_name, style, no_wrap) tuples

    Returns:
        Configured Rich Table
    """
    table = Table(title=title)
    for col_data in columns:
        name = col_data[0]
        style = col_data[1] if len(col_data) > 1 else None
        no_wrap = col_data[2] if len(col_data) > 2 else False
        table.add_column(name, style=style, no_wrap=no_wrap)
    return table


def print_error(message: str):
    """Print an error message with consistent styling.

    Args:
        message: Error message to display
    """
    console.print(f"❌ {message}", style="bold red")


def print_success(message: str):
    """Print a success message with consistent styling.

    Args:
        message: Success message to display
    """
    console.print(f"✅ {message}", style="bold green")


def print_warning(message: str):
    """Print a warning message with consistent styling.

    Args:
        message: Warning message to display
    """
    console.print(f"⚠️  {message}", style="bold yellow")


def print_info(message: str):
    """Print an info message with consistent styling.

    Args:
        message: Info message to display
    """
    console.print(f"ℹ️  {message}", style="bold blue")
