# Command-Line Interface (CLI)

Zoea Studio includes a powerful Typer-based CLI (`zoea`) for managing projects, workspaces, workflows, and more from the command line.

## Installation

The CLI is automatically available after installing the backend package:

```bash
cd backend && uv sync
```

The `zoea` command is registered as a console script in `pyproject.toml`.

## Quick Start

```bash
# List all projects
zoea projects list

# Show project details
zoea projects show "My Project"

# List available workflows
zoea workflows list

# Run a workflow
zoea workflows run plan_github_issue issue_number=7
```

## Command Groups

The CLI is organized into six command groups:

| Command Group | Description |
|---------------|-------------|
| `zoea projects` | Manage projects |
| `zoea workspaces` | Manage workspaces |
| `zoea workflows` | Discover and run workflows |
| `zoea documents` | Document operations |
| `zoea clipboard` | Clipboard management |
| `zoea chats` | Chat/conversation management |

## Projects Commands

### List Projects

```bash
# List all projects
zoea projects list

# Filter by organization
zoea projects list --org "Team Zoea"

# Show detailed information
zoea projects list --verbose
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--org` | `-o` | Filter by organization name |
| `--verbose` | `-v` | Show detailed information (workspace count, IDs) |

### Show Project Details

```bash
# Show by name
zoea projects show "My Project"

# Show by ID
zoea projects show 1

# Specify organization if name is ambiguous
zoea projects show "My Project" --org "Team Zoea"
```

**Output includes:**
- Project name and description
- Organization
- Working and worktree directories
- Gemini File Search integration status
- Recent workspaces

## Workspaces Commands

### List Workspaces

```bash
# List all workspaces
zoea workspaces list

# Filter by project
zoea workspaces list --project "My Project"
```

### Show Workspace Details

```bash
zoea workspaces show 1
```

### Display Workspace Hierarchy

```bash
# Show tree view of workspaces for a project
zoea workspaces tree "My Project"
```

## Workflows Commands

Workflows are the heart of Zoea Studio's automation capabilities. See [Workflows](workflows.md) for detailed workflow documentation.

### List Available Workflows

```bash
zoea workflows list
```

**Output:**

| Column | Description |
|--------|-------------|
| Slug | Workflow identifier |
| Name | Human-readable name |
| Inputs | Required input parameters |
| Description | Brief description |

### Show Workflow Details

```bash
zoea workflows show plan_github_issue
```

**Output includes:**
- Workflow slug and name
- Description
- Required and optional inputs with types
- Output specifications
- Service bindings

### Run a Workflow

```bash
# Basic usage
zoea workflows run plan_github_issue issue_number=7

# Specify project and workspace
zoea workflows run plan_github_issue issue_number=7 \
    --project "My Project" \
    --workspace "Development"

# Specify organization
zoea workflows run plan_github_issue issue_number=7 \
    --org "Team Zoea"

# Dry run (preview without executing)
zoea workflows run plan_github_issue issue_number=7 --dry-run
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Project name for output scoping |
| `--workspace` | `-w` | Workspace name for output scoping |
| `--org` | `-o` | Organization name |
| `--dry-run` | | Preview what would run without executing |

**Input Format:**

Inputs are passed as `key=value` pairs:

```bash
zoea workflows run my_workflow input1=value1 input2=42 input3=true
```

- String values: `name=MyDocument`
- Integer values: `issue_number=7`
- Boolean values: `verbose=true`

## Configuration

### Configuration File

Create `~/.zoea/config.yaml` to set defaults:

```yaml
# Default organization for CLI commands
default_organization: "Team Zoea"

# Verbose output by default
verbose: false
```

### Organization Filtering

The CLI supports organization-scoped filtering throughout:

1. **Explicit flag**: Use `--org "Organization Name"` on any command
2. **Configuration default**: Set `default_organization` in config file
3. **Auto-detection**: If omitted, shows data across all organizations

**Priority order:**
1. Command-line `--org` flag (highest)
2. Config file `default_organization`
3. All organizations (no filter)

## Architecture

### Project Structure

```
backend/cli/
├── cli.py                    # Main Typer app entry point
├── commands/
│   ├── projects.py           # Project management commands
│   ├── workspaces.py         # Workspace management commands
│   ├── workflows.py          # Workflow discovery and execution
│   ├── documents.py          # Document operations
│   ├── clipboard.py          # Clipboard management
│   └── chats.py              # Chat/conversation commands
└── utils/
    ├── config.py             # Configuration loading and org filtering
    ├── django_context.py     # @with_django decorator for DB access
    └── formatting.py         # Rich console formatting utilities
```

### Django Integration

The CLI uses a custom `@with_django` decorator to initialize Django before executing commands that require database access:

```python
from cli.utils.django_context import with_django

@with_django
def my_command():
    from django.apps import apps
    Project = apps.get_model("projects", "Project")
    # Now you can use Django models
```

### Rich Formatting

The CLI uses [Rich](https://rich.readthedocs.io/) for beautiful terminal output:

- Colored tables with headers
- Panels for detailed information
- Progress indicators
- Styled text with markup

## Examples

### Complete Workflow Example

```bash
# 1. Check available projects
zoea projects list --org "Team Zoea"

# 2. See project details
zoea projects show "ZoeaStudio"

# 3. View workspaces
zoea workspaces tree "ZoeaStudio"

# 4. List available workflows
zoea workflows list

# 5. Examine a workflow
zoea workflows show plan_github_issue

# 6. Dry run to preview
zoea workflows run plan_github_issue issue_number=42 \
    --project "ZoeaStudio" --dry-run

# 7. Execute the workflow
zoea workflows run plan_github_issue issue_number=42 \
    --project "ZoeaStudio"
```

### Quick Project Overview

```bash
# Get verbose project list with workspace counts
zoea projects list -v -o "Team Zoea"

# Display project workspace hierarchy
zoea workspaces tree "ZoeaStudio"
```

## Troubleshooting

### "No admin user found"

Run the initialization command first:

```bash
cd backend
uv run python manage.py initialize_local_user
```

### "Organization not found"

Check available organizations:

```bash
zoea projects list  # Shows all projects with their organizations
```

### "Workflow not found"

List available workflows:

```bash
zoea workflows list
```

Workflow slugs use underscores (e.g., `plan_github_issue`), but the CLI also accepts hyphens (`plan-github-issue`).

## Related Documentation

- [Workflows](workflows.md) - Detailed workflow system documentation
- [Getting Started](../getting-started/index.md) - Initial setup guide
- [Local User Initialization](../getting-started/initialization.md) - Setting up local users
