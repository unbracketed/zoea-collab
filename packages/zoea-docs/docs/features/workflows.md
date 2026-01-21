# Workflows

Zoea Studio includes a powerful workflow orchestration system built on [PocketFlow](https://github.com/minimaLLM/pocketflow). Workflows automate multi-step processes with AI integration, external service bindings, and automatic document generation.

## Overview

Workflows in Zoea Studio are:

- **YAML-Configured**: Define inputs, outputs, and services in declarative YAML
- **PocketFlow-Powered**: Use PocketFlow's node-based execution model
- **Service-Integrated**: Bind external services like GitHub, OpenAI, and document generation
- **Output-Oriented**: Automatically create documents from workflow outputs
- **Organization-Scoped**: All outputs respect multi-tenant boundaries

## Quick Start

### Running a Workflow

```bash
# List available workflows
zoea workflows list

# Run a workflow with inputs
zoea workflows run plan_github_issue issue_number=7

# Specify project and workspace for outputs
zoea workflows run plan_github_issue issue_number=7 \
    --project "ZoeaStudio" \
    --workspace "Development"
```

### Workflow Output

Workflows can generate documents automatically:

```
Workflow completed! Run ID: a1b2c3d4

Outputs:
  Issue 7 Implementation Spec:
    type: MarkdownDocument
    id: 42
    name: Issue 7 Implementation Spec
    folder: SDLC/Specs/Issue-7
```

## Workflow Configuration

Workflows are defined using YAML configuration files with three main sections: `INPUTS`, `OUTPUTS`, and `SERVICES`.

### Example: `flow-config.yaml`

```yaml
INPUTS:
  - name: issue_number
    type: PositiveInt
    description: GitHub issue number to create implementation plan for

OUTPUTS:
  - name: Issue {issue_number} Implementation Spec
    type: MarkdownDocument
    target: SDLC/Specs/Issue-{issue_number}

SERVICES:
  - name: PyGithubInterface
    ctxref: gh
    config:
      repo: owner/repository
  - name: AIService
    ctxref: ai
```

### Inputs

Define workflow input parameters:

```yaml
INPUTS:
  - name: issue_number
    type: PositiveInt
    description: GitHub issue number
    required: true  # default

  - name: verbose
    type: bool
    value: false    # default value
    required: false
```

**Supported Types:**

| Type | Python Type | Description |
|------|-------------|-------------|
| `str`, `string` | `str` | Text input |
| `int`, `integer` | `int` | Integer value |
| `PositiveInt` | `int` | Positive integer (> 0) |
| `float` | `float` | Floating point number |
| `bool`, `boolean` | `bool` | Boolean flag |
| `Folder` | `str` | Folder path |
| `MarkdownDocument` | `str` | Document reference |
| `Clipboard` | `int` | Clipboard item ID |

### Outputs

Define workflow outputs with templated names and target folders:

```yaml
OUTPUTS:
  - name: Issue {issue_number} Implementation Spec
    type: MarkdownDocument
    target: SDLC/Specs/Issue-{issue_number}
```

**Template Variables:**

Output names and targets support `{variable}` interpolation from input values:

- `{issue_number}` → replaced with the `issue_number` input value
- `Issue {issue_number} Spec` → becomes `Issue 42 Spec`

**Supported Output Types:**

| Type | Description |
|------|-------------|
| `MarkdownDocument` | Creates a Markdown document in the workspace |
| `D2Diagram` | Creates a D2 diagram (planned) |
| `Image` | Creates an image document (planned) |

### Services

Bind external services for use in workflow nodes:

```yaml
SERVICES:
  - name: PyGithubInterface
    ctxref: gh
    config:
      repo: owner/repository

  - name: AIService
    ctxref: ai
```

**Available Services:**

| Service | Context Ref | Description |
|---------|-------------|-------------|
| `AIService` | `ai` | OpenAI ChatCompletion wrapper |
| `PyGithubInterface` | `gh` | GitHub API client |
| `DocumentService` | `docs` | Document creation service |

## Workflow Structure

Each workflow lives in a directory under `backend/workflows/builtin/`:

```
workflows/builtin/
└── plan_github_issue/
    ├── flow-config.yaml    # Workflow specification
    ├── flow.py             # PocketFlow definition
    ├── nodes.py            # Custom node implementations
    └── __init__.py
```

### Flow Definition (`flow.py`)

```python
from pocketflow import Flow
from .nodes import ReadGithubIssue, PlanIssue

def build_flow():
    """Build the workflow flow."""
    flow = Flow()

    # Define nodes
    read_issue = ReadGithubIssue()
    plan_issue = PlanIssue()

    # Connect nodes
    flow.add_node("read_issue", read_issue)
    flow.add_node("plan_issue", plan_issue)
    flow.add_edge("read_issue", "plan_issue")

    flow.set_entry_point("read_issue")

    return flow
```

### Custom Nodes (`nodes.py`)

```python
from pocketflow import Node

class ReadGithubIssue(Node):
    """Read a GitHub issue and add to context."""

    def run(self, shared: dict) -> str:
        # Access services via context
        gh = shared["services"]["gh"]
        issue_number = shared["inputs"]["issue_number"]

        # Fetch issue
        issue = gh.get_issue(issue_number)

        # Store in state
        shared["state"]["issue_title"] = issue.title
        shared["state"]["issue_body"] = issue.body

        return "success"


class PlanIssue(Node):
    """Generate implementation plan using AI."""

    def run(self, shared: dict) -> str:
        ai = shared["services"]["ai"]
        title = shared["state"]["issue_title"]
        body = shared["state"]["issue_body"]

        prompt = f"""Create an implementation plan for:
        Title: {title}
        Description: {body}
        """

        plan = ai.chat(prompt)

        # Set output (will be saved as document)
        shared["outputs"]["Issue {issue_number} Implementation Spec"] = plan

        return "success"
```

## Workflow Context

The `WorkflowContext` provides access to:

### Inputs Container

```python
# Access validated inputs
issue_number = shared["inputs"]["issue_number"]
```

### Outputs Container

```python
# Set output values (matched to output specs)
shared["outputs"]["Document Name"] = content
```

### Services Container

```python
# Access bound services
gh = shared["services"]["gh"]
ai = shared["services"]["ai"]

# Use services
issue = gh.get_issue(42)
response = ai.chat("Hello")
```

### State Container

```python
# Store intermediate state
shared["state"]["issue_data"] = {...}

# Read state in later nodes
data = shared["state"]["issue_data"]
```

### Django Context

```python
# Access Django objects
org = shared["organization"]
project = shared["project"]
workspace = shared["workspace"]
user = shared["user"]
```

## WorkflowRunner

The `WorkflowRunner` class orchestrates workflow execution:

```python
from workflows.runner import WorkflowRunner

runner = WorkflowRunner(
    organization=organization,
    project=project,
    workspace=workspace,
    user=user,
)

result = await runner.run(
    workflow_slug="plan_github_issue",
    inputs={"issue_number": 42},
)

print(result["run_id"])      # Unique run identifier
print(result["outputs"])     # Output results with document IDs
print(result["state"])       # Final workflow state
```

### Synchronous Execution

For simpler use cases:

```python
from workflows.runner import run_workflow_sync

result = run_workflow_sync(
    workflow_slug="plan_github_issue",
    inputs={"issue_number": 42},
    organization=org,
    project=proj,
    workspace=ws,
    user=user,
)
```

## Creating a New Workflow

### Step 1: Create Workflow Directory

```bash
mkdir -p backend/workflows/builtin/my_workflow
```

### Step 2: Define Configuration

Create `flow-config.yaml`:

```yaml
INPUTS:
  - name: topic
    type: str
    description: Topic to research

OUTPUTS:
  - name: Research Report on {topic}
    type: MarkdownDocument
    target: Research/{topic}

SERVICES:
  - name: AIService
    ctxref: ai
```

### Step 3: Implement Nodes

Create `nodes.py`:

```python
from pocketflow import Node

class ResearchTopic(Node):
    def run(self, shared: dict) -> str:
        ai = shared["services"]["ai"]
        topic = shared["inputs"]["topic"]

        report = ai.chat(f"Write a research report about {topic}")

        shared["outputs"][f"Research Report on {topic}"] = report
        return "success"
```

### Step 4: Build Flow

Create `flow.py`:

```python
from pocketflow import Flow
from .nodes import ResearchTopic

def build_flow():
    flow = Flow()
    flow.add_node("research", ResearchTopic())
    flow.set_entry_point("research")
    return flow
```

### Step 5: Create `__init__.py`

```python
from .flow import build_flow

__all__ = ["build_flow"]
```

### Step 6: Test

```bash
zoea workflows show my_workflow
zoea workflows run my_workflow topic="Machine Learning" --dry-run
zoea workflows run my_workflow topic="Machine Learning"
```

## Architecture

### Component Overview

```
workflows/
├── models.py           # Django model (org-scoped)
├── runner.py           # WorkflowRunner async engine
├── config.py           # YAML config loader
├── types.py            # Pydantic specs (InputSpec, OutputSpec, etc.)
├── context.py          # WorkflowContext dataclass
├── registry.py         # Service and Workflow registries
├── exceptions.py       # WorkflowError
├── base_nodes.py       # PocketFlow node base classes
├── services/
│   ├── ai.py           # AIService (OpenAI wrapper)
│   ├── github.py       # PyGithubInterface
│   └── documents.py    # DocumentService
└── builtin/
    └── plan_github_issue/
        ├── flow-config.yaml
        ├── flow.py
        └── nodes.py
```

### Execution Flow

1. **Load Configuration**: Parse `flow-config.yaml` into `WorkflowSpec`
2. **Validate Inputs**: Check required inputs, coerce types
3. **Build Context**: Create `WorkflowContext` with inputs and Django objects
4. **Bind Services**: Instantiate and register services
5. **Get Flow Builder**: Import `build_flow()` from workflow directory
6. **Run Flow**: Execute PocketFlow with shared context dict
7. **Process Outputs**: Create documents from output specifications

### Service Registry

Services are registered globally and instantiated per-run:

```python
from workflows.registry import ServiceRegistry

registry = ServiceRegistry.get_instance()

# Register custom service
registry.register("MyService", MyServiceClass)

# Create instance with config
service = registry.create("MyService", {"api_key": "..."})
```

## Best Practices

### Input Validation

Always specify input types for automatic validation:

```yaml
INPUTS:
  - name: count
    type: PositiveInt  # Ensures > 0
```

### Error Handling

Handle errors gracefully in nodes:

```python
class MyNode(Node):
    def run(self, shared: dict) -> str:
        try:
            # risky operation
            result = external_api_call()
            shared["state"]["result"] = result
            return "success"
        except APIError as e:
            shared["state"]["error"] = str(e)
            return "error"
```

### State Management

Use state for intermediate results between nodes:

```python
# Node 1: Fetch data
shared["state"]["raw_data"] = fetch_data()

# Node 2: Process data
raw = shared["state"]["raw_data"]
shared["state"]["processed"] = process(raw)

# Node 3: Generate output
processed = shared["state"]["processed"]
shared["outputs"]["Report"] = generate_report(processed)
```

### Output Templates

Use meaningful template variables:

```yaml
OUTPUTS:
  - name: "{topic} Analysis - {date}"
    type: MarkdownDocument
    target: Reports/{topic}/{date}
```

## Related Documentation

- [CLI](cli.md) - Run workflows from command line
- [Backend Architecture](../architecture/backend.md) - Service layer patterns
- [Multi-Tenant Guide](../architecture/multi-tenant.md) - Organization scoping
