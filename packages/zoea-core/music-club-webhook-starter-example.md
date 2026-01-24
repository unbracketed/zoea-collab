# Music Club Webhook Pipeline: Starter Example

This document outlines how to set up a webhook-driven extraction pipeline for a music club using the Zoea CLI. The use case: receive miscellaneous content via webhook, extract structured music event data, store as artifacts, and notify an external calendar system.

## Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Inbound        │     │   Event      │     │   Extraction    │     │   Outbound       │
│  Webhook        │────▶│   Trigger    │────▶│   Workflow      │────▶│   Webhook        │
│  (content in)   │     │              │     │   + Artifacts   │     │   (calendar API) │
└─────────────────┘     └──────────────┘     └─────────────────┘     └──────────────────┘
```

---

## Part 1: What You Can Do Now (CLI)

### Step 1: Create the Project

```bash
zoea projects create "music-club" "/path/to/music-club" \
  --description "Music club event extraction and calendar sync pipeline"
```

Verify:
```bash
zoea projects show music-club
```

### Step 2: Create the Inbound Webhook

This webhook receives content from various sources (email forwards, form submissions, social media feeds, etc.):

```bash
zoea webhooks create "music-content-ingest" \
  --project "music-club" \
  --description "Receives miscellaneous content to scan for music events"
```

The CLI will output a webhook URL and secret. Save these for configuring your content sources.

Example output:
```
Webhook created successfully!
  ID: 42
  UUID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  URL: https://your-domain.com/platform/webhooks/a1b2c3d4-e5f6-7890-abcd-ef1234567890/
  Secret: whsec_xxxxxxxxxxxxxxxxxxxx
```

### Step 3: List Available Workflows

```bash
zoea workflows list
```

Current built-in workflows:
| Slug | Description |
|------|-------------|
| `summarize_content` | Summarize documents/content |
| `plan_github_issue` | Create implementation specs from GitHub issues |
| `project_activity_summary` | Summarize project activity |

### Step 4: Create an Event Trigger

Connect the webhook to a workflow:

```bash
zoea events create "extract-music-events" \
  --project "music-club" \
  --event-type webhook_received \
  --skill summarize_content  # placeholder until custom workflow exists
```

### Step 5: Explore Available Skills

```bash
zoea skills list
zoea skills show <skill-name>
```

---

## Part 2: Current Architecture

### Components That Exist

| Component | Model/Module | Status | CLI Support |
|-----------|--------------|--------|-------------|
| Projects | `Project` | Ready | `zoea projects` |
| Inbound Webhooks | `WebhookConnection` | Ready | `zoea webhooks` |
| Event Triggers | `EventTrigger` | Ready | `zoea events` |
| Workflows | `ExecutionRun` | Ready | `zoea workflows` |
| Artifacts | `DocumentCollection` (type=ARTIFACT) | Ready | Partial |
| Output Dispatch | `OutputRoute`, `DispatchLog` | Ready | **Missing CLI** |

### Webhook Connection Model

```python
# core/models/webhook_connection.py
class WebhookConnection(models.Model):
    organization = models.ForeignKey(Organization, ...)
    project = models.ForeignKey(Project, null=True, ...)
    name = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    webhook_secret = models.CharField(max_length=255)  # HMAC validation
    is_active = models.BooleanField(default=True)
    field_mapping = models.JSONField(default=dict)  # Map incoming fields
    message_count = models.IntegerField(default=0)
```

### Event Trigger Model

```python
# core/models/event_trigger.py
class EventTrigger(models.Model):
    class EventType(models.TextChoices):
        WEBHOOK_RECEIVED = "webhook_received"
        DOCUMENT_CREATED = "document_created"
        SCHEDULED = "scheduled"
        # ... more event types

    organization = models.ForeignKey(Organization, ...)
    project = models.ForeignKey(Project, null=True, ...)
    name = models.CharField(max_length=255)
    event_type = models.CharField(choices=EventType.choices)
    skill = models.ForeignKey(AgentSkill, null=True, ...)
    is_enabled = models.BooleanField(default=True)
    filters = models.JSONField(default=dict)  # Event filtering rules
    config = models.JSONField(default=dict)   # Execution config
```

### Output Route Model

```python
# core/models/output_dispatch.py
class OutputRoute(models.Model):
    class DestinationType(models.TextChoices):
        SLACK = "slack"
        DISCORD = "discord"
        WEBHOOK = "webhook"
        DOCUMENT = "document"
        EMAIL = "email"
        PLATFORM_REPLY = "platform_reply"

    organization = models.ForeignKey(Organization, ...)
    project = models.ForeignKey(Project, null=True, ...)
    event_trigger = models.ForeignKey(EventTrigger, null=True, ...)
    destination_type = models.CharField(choices=DestinationType.choices)
    destination_config = models.JSONField()  # URL, channel, etc.
    template = models.TextField(blank=True)  # Jinja2 template
    format = models.CharField(choices=[("text", "json", "markdown")])
    is_enabled = models.BooleanField(default=True)
```

---

## Part 3: What's Missing

### Gap 1: Custom Extraction Workflow

The built-in workflows don't handle structured data extraction with custom schemas. You need a workflow that:

1. Accepts raw content (text, HTML, etc.)
2. Uses an LLM to identify and extract music events
3. Validates against a schema
4. Creates artifacts for each extracted event

#### Proposed Music Event Schema

```python
# core/schemas/music_event.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MusicEvent(BaseModel):
    """Structured music event extracted from content."""
    title: str
    artist: str
    venue: str
    event_date: datetime
    event_time: Optional[str] = None
    ticket_url: Optional[str] = None
    ticket_price: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    source_content_snippet: Optional[str] = None  # What triggered extraction

class MusicEventExtractionResult(BaseModel):
    """Result of extraction workflow."""
    events: list[MusicEvent]
    raw_content_length: int
    extraction_confidence: float
    extraction_notes: Optional[str] = None
```

#### Proposed Workflow Implementation

```python
# workflows/music_event_extraction.py
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from typing import TypedDict
import json

from core.schemas.music_event import MusicEvent, MusicEventExtractionResult
from core.services.llm import get_openai_client


class ExtractionState(TypedDict):
    raw_content: str
    extracted_events: list[dict]
    artifacts_created: list[str]
    error: str | None


EXTRACTION_PROMPT = """
Analyze the following content and extract any music events mentioned.
For each event found, extract:
- title: Event name or show title
- artist: Performing artist(s)
- venue: Location/venue name
- event_date: Date of the event (ISO format)
- event_time: Start time if mentioned
- ticket_url: Link to tickets if present
- ticket_price: Price info if mentioned
- description: Brief description
- genre: Music genre if identifiable

Return a JSON array of events. If no events found, return an empty array.

Content:
{content}

JSON Response:
"""


async def extract_events(state: ExtractionState) -> ExtractionState:
    """Use LLM to extract structured events from raw content."""
    client = get_openai_client()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You extract structured music event data from text. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(content=state["raw_content"])
            }
        ],
        response_format={"type": "json_object"}
    )

    try:
        result = json.loads(response.choices[0].message.content)
        events = result.get("events", [])
        # Validate each event against schema
        validated = [MusicEvent(**e).model_dump() for e in events]
        state["extracted_events"] = validated
    except Exception as e:
        state["error"] = f"Extraction failed: {str(e)}"
        state["extracted_events"] = []

    return state


async def create_artifacts(state: ExtractionState) -> ExtractionState:
    """Store extracted events as artifacts."""
    from core.models import DocumentCollection, Document

    if not state["extracted_events"]:
        return state

    artifact_ids = []
    for event in state["extracted_events"]:
        # Create artifact document
        doc = await Document.objects.acreate(
            title=f"Music Event: {event['title']}",
            content_type="application/json",
            content=json.dumps(event, default=str),
            metadata={
                "artifact_type": "music_event",
                "extracted_at": datetime.now().isoformat()
            }
        )
        artifact_ids.append(str(doc.id))

    state["artifacts_created"] = artifact_ids
    return state


def should_create_artifacts(state: ExtractionState) -> str:
    """Conditional edge: only create artifacts if events were found."""
    if state.get("error") or not state.get("extracted_events"):
        return "end"
    return "create_artifacts"


# Build the workflow graph
def build_music_extraction_workflow():
    workflow = StateGraph(ExtractionState)

    workflow.add_node("extract_events", extract_events)
    workflow.add_node("create_artifacts", create_artifacts)

    workflow.set_entry_point("extract_events")
    workflow.add_conditional_edges(
        "extract_events",
        should_create_artifacts,
        {
            "create_artifacts": "create_artifacts",
            "end": END
        }
    )
    workflow.add_edge("create_artifacts", END)

    return workflow.compile()


# Workflow metadata for registration
WORKFLOW_METADATA = {
    "slug": "extract_music_events",
    "name": "Extract Music Events",
    "description": "Extract structured music event data from raw content",
    "inputs": [
        {"name": "raw_content", "type": "string", "required": True}
    ],
    "outputs": [
        {"name": "extracted_events", "type": "array"},
        {"name": "artifacts_created", "type": "array"}
    ]
}
```

### Gap 2: Output Route CLI Commands

No CLI commands exist for configuring output routes. Proposed commands:

```bash
# List output routes
zoea routes list --project music-club

# Create outbound webhook route
zoea routes create "calendar-sync" \
  --project "music-club" \
  --destination-type webhook \
  --url "https://music-club.com/api/calendar/events" \
  --format json \
  --trigger "extract-music-events"

# Show route details
zoea routes show calendar-sync

# Delete route
zoea routes delete calendar-sync
```

#### Proposed CLI Implementation

```python
# cli/commands/routes.py
import typer
from rich.console import Console
from rich.table import Table

from core.models import OutputRoute, EventTrigger, Project

app = typer.Typer(help="Manage output routes for dispatching workflow results")
console = Console()


@app.command("list")
def list_routes(
    project: str = typer.Option(None, "--project", "-p", help="Filter by project"),
    org: str = typer.Option(None, "--org", "-o", help="Filter by organization"),
):
    """List configured output routes."""
    filters = {}
    if project:
        filters["project__name"] = project
    if org:
        filters["organization__slug"] = org

    routes = OutputRoute.objects.filter(**filters).select_related(
        "project", "organization", "event_trigger"
    )

    table = Table(title="Output Routes")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Project")
    table.add_column("Trigger")
    table.add_column("Enabled")

    for route in routes:
        table.add_row(
            str(route.id),
            route.name,
            route.destination_type,
            route.project.name if route.project else "-",
            route.event_trigger.name if route.event_trigger else "-",
            "Yes" if route.is_enabled else "No"
        )

    console.print(table)


@app.command("create")
def create_route(
    name: str = typer.Argument(..., help="Route name"),
    destination_type: str = typer.Option(..., "--destination-type", "-d",
        help="Destination type: webhook, slack, discord, email"),
    url: str = typer.Option(None, "--url", help="Destination URL (for webhook)"),
    project: str = typer.Option(None, "--project", "-p", help="Project name"),
    trigger: str = typer.Option(None, "--trigger", "-t", help="Event trigger name"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
    template: str = typer.Option(None, "--template", help="Jinja2 template for output"),
):
    """Create a new output route."""
    from core.models import Organization

    # Build destination config based on type
    destination_config = {}
    if destination_type == "webhook":
        if not url:
            console.print("[red]Error: --url required for webhook destination[/red]")
            raise typer.Exit(1)
        destination_config["url"] = url
        destination_config["method"] = "POST"
        destination_config["headers"] = {"Content-Type": "application/json"}

    # Look up related objects
    project_obj = None
    if project:
        project_obj = Project.objects.get(name=project)

    trigger_obj = None
    if trigger:
        trigger_obj = EventTrigger.objects.get(name=trigger)

    org = project_obj.organization if project_obj else Organization.objects.first()

    route = OutputRoute.objects.create(
        organization=org,
        project=project_obj,
        event_trigger=trigger_obj,
        name=name,
        destination_type=destination_type,
        destination_config=destination_config,
        format=format,
        template=template or "",
        is_enabled=True
    )

    console.print(f"[green]Output route '{name}' created successfully![/green]")
    console.print(f"  ID: {route.id}")
    console.print(f"  Destination: {destination_type}")
    if url:
        console.print(f"  URL: {url}")
```

### Gap 3: End-to-End Pipeline Wiring

Currently, connecting all pieces requires manual steps or API calls. The ideal flow:

```bash
# Complete setup in one compound command (proposed)
zoea pipelines create "music-event-sync" \
  --project "music-club" \
  --inbound-webhook "music-content-ingest" \
  --workflow "extract_music_events" \
  --outbound-webhook "https://music-club.com/api/calendar/events" \
  --on-success "notify-slack"
```

---

## Part 4: Workarounds for Missing Features

### Option A: Use Django Admin

Access `/admin/` to manually configure:
1. Output routes via `OutputRoute` model
2. Custom workflow registration
3. Pipeline wiring via `EventTrigger` → `Skill` connections

### Option B: Direct API Calls

```bash
# Create output route via API
curl -X POST https://your-domain.com/platform/routes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "calendar-sync",
    "project_id": 1,
    "destination_type": "webhook",
    "destination_config": {
      "url": "https://music-club.com/api/calendar/events",
      "method": "POST"
    },
    "format": "json",
    "is_enabled": true
  }'
```

### Option C: Django Shell

```python
# python manage.py shell_plus

from core.models import OutputRoute, Project, EventTrigger

project = Project.objects.get(name="music-club")
trigger = EventTrigger.objects.get(name="extract-music-events")

route = OutputRoute.objects.create(
    organization=project.organization,
    project=project,
    event_trigger=trigger,
    name="calendar-sync",
    destination_type="webhook",
    destination_config={
        "url": "https://music-club.com/api/calendar/events",
        "method": "POST",
        "headers": {"Content-Type": "application/json"}
    },
    format="json",
    is_enabled=True
)
print(f"Created route: {route.id}")
```

---

## Part 5: Testing the Pipeline

### Send Test Webhook

```bash
# Get your webhook URL and secret from: zoea webhooks show music-content-ingest

WEBHOOK_URL="https://your-domain.com/platform/webhooks/YOUR-UUID/"
WEBHOOK_SECRET="whsec_xxxxx"

# Create HMAC signature
PAYLOAD='{"content": "Jazz Night at Blue Note - Miles Davis Tribute featuring the John Coltrane Quartet. Saturday, March 15th at 8pm. Tickets $25 at bluenote.com/tickets"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)

# Send webhook
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

### Verify Extraction

```bash
# Check workflow runs
zoea workflows runs --project music-club --limit 5

# Check created artifacts (via API or admin)
curl https://your-domain.com/platform/workflows/runs/LATEST_RUN_ID/artifacts \
  -H "Authorization: Bearer $TOKEN"
```

---

## Summary: Implementation Roadmap

| Priority | Task | Effort |
|----------|------|--------|
| 1 | Create `extract_music_events` workflow | Medium |
| 2 | Add `zoea routes` CLI commands | Low |
| 3 | Register workflow with skill system | Low |
| 4 | Add `zoea pipelines` compound commands | Medium |
| 5 | Add webhook signature helpers to CLI | Low |

### Quick Start (What Works Today)

```bash
# 1. Create project
zoea projects create "music-club" "~/projects/music-club"

# 2. Create inbound webhook
zoea webhooks create "content-ingest" --project music-club

# 3. Create event trigger (use existing workflow as placeholder)
zoea events create "process-content" \
  --project music-club \
  --event-type webhook_received

# 4. Configure output route via Django admin or shell
# 5. Implement custom extraction workflow
# 6. Test with sample webhook payload
```

---

## Appendix: Full Example Output Route Template

For the outbound webhook to the calendar API, use a Jinja2 template:

```jinja2
{
  "events": [
    {% for event in extracted_events %}
    {
      "title": "{{ event.title }}",
      "artist": "{{ event.artist }}",
      "venue": "{{ event.venue }}",
      "date": "{{ event.event_date }}",
      "time": "{{ event.event_time | default('TBA') }}",
      "ticketUrl": "{{ event.ticket_url | default('') }}",
      "price": "{{ event.ticket_price | default('') }}",
      "description": "{{ event.description | default('') }}",
      "genre": "{{ event.genre | default('') }}",
      "source": "zoea-extraction",
      "extractedAt": "{{ now().isoformat() }}"
    }{% if not loop.last %},{% endif %}
    {% endfor %}
  ],
  "metadata": {
    "workflowRunId": "{{ run_id }}",
    "eventCount": {{ extracted_events | length }},
    "projectId": "{{ project.id }}"
  }
}
```
