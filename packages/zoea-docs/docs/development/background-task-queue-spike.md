# Background Task Queue Spike: Django-Q2

**Issue:** ZoeaStudio-ree9
**Date:** 2025-12-09
**Status:** Complete
**Decision:** Use Django-Q2 with PostgreSQL ORM broker

## Summary

Evaluated task queue options for running workflows as background tasks. Selected **Django-Q2** as it:
- Works with existing PostgreSQL database (no Redis/additional services needed)
- Supports Python 3.12 and Django 6.0 (matches project requirements)
- Provides admin interface integration
- Has built-in retry/timeout handling
- Is actively maintained (v1.9.0 released Dec 2025)

## Options Evaluated

| Feature | Django-Q2 | Huey | Django-RQ |
|---------|-----------|------|-----------|
| Requires Redis | No (ORM option) | Yes | Yes |
| Django Admin UI | Yes | No | Yes |
| Async Task Support | Yes | Yes | Yes |
| Scheduled Tasks | Yes | Yes | Yes |
| Python 3.12 | Yes | Unknown | Unknown |
| Django 6.0 | Yes | Unknown | Unknown |
| Retry Handling | Built-in | Built-in | Manual |

## Recommended Configuration

### Installation

```bash
uv add django-q2
```

### Django Settings (`zoeastudio/settings.py`)

```python
INSTALLED_APPS = [
    # ... existing apps
    'django_q',
]

# Django-Q2 Configuration
Q_CLUSTER = {
    'name': 'ZoeaStudio',
    'workers': 2,  # Start low, increase based on load
    'timeout': 600,  # 10 minutes - workflows can be long-running
    'retry': 900,  # 15 minutes - must be > timeout
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',  # Use PostgreSQL via Django ORM
    'save_limit': 100,  # Keep last 100 successful tasks
    'compress': True,  # Compress large payloads
    'catch_up': False,  # Don't run missed scheduled tasks on startup
    'label': 'Background Tasks',
}
```

### Mise Tasks (`.mise.toml`)

```toml
[tasks.worker]
description = "Start Django-Q2 background worker"
run = "cd backend && uv run python manage.py qcluster"

[tasks.worker-bg]
description = "Start Django-Q2 worker in background"
run = "cd backend && nohup uv run python manage.py qcluster > logs/worker.log 2>&1 &"
```

### Task Definition Pattern

```python
# backend/workflows/tasks.py
from django_q.tasks import async_task
from workflows.runner import WorkflowRunner

def execute_workflow_background(
    run_id: str,
    workflow_slug: str,
    inputs: dict,
    org_id: int,
    project_id: int,
    workspace_id: int,
    user_id: int,
):
    """Background task to execute a workflow."""
    from django.contrib.auth import get_user_model
    from organizations.models import Organization
    from projects.models import Project
    from workspaces.models import Workspace
    from workflows.models import WorkflowRun

    # Load context objects
    org = Organization.objects.get(id=org_id)
    project = Project.objects.get(id=project_id)
    workspace = Workspace.objects.get(id=workspace_id)
    user = get_user_model().objects.get(id=user_id)

    # Update run status
    run = WorkflowRun.objects.get(run_id=run_id)
    run.status = 'running'
    run.started_at = timezone.now()
    run.save()

    try:
        # Execute workflow synchronously within the task
        import asyncio
        runner = WorkflowRunner(org, project, workspace, user)
        result = asyncio.run(runner.run(workflow_slug, inputs))

        # Update with results
        run.status = 'completed'
        run.outputs = result.get('outputs', {})
        run.completed_at = timezone.now()
        run.save()

        return {'run_id': run_id, 'status': 'completed'}

    except Exception as e:
        run.status = 'failed'
        run.error = str(e)
        run.completed_at = timezone.now()
        run.save()
        raise  # Re-raise so Django-Q marks task as failed


# Usage in API:
def queue_workflow(run_id, slug, inputs, org, project, workspace, user):
    """Queue a workflow for background execution."""
    async_task(
        'workflows.tasks.execute_workflow_background',
        run_id,
        slug,
        inputs,
        org.id,
        project.id,
        workspace.id,
        user.id,
        task_name=f'workflow-{run_id}',
        timeout=600,  # 10 minute timeout
    )
```

## Database Tables Created

Django-Q2 creates these tables via migration:

- `django_q_ormq` - Task queue (pending tasks)
- `django_q_task` - Task results/history
- `django_q_schedule` - Scheduled/recurring tasks

## Admin Interface

Django-Q2 adds these admin views:
- **Queued Tasks** - View/manage pending tasks
- **Successful Tasks** - View completed tasks
- **Failed Tasks** - View and retry failed tasks
- **Scheduled Tasks** - Manage recurring tasks

## Production Considerations

1. **Worker Count**: Start with 2 workers, monitor and adjust
2. **Timeout**: Set to longest expected workflow time + buffer
3. **Memory**: Use `max_rss` to recycle workers on high memory usage
4. **Logging**: Configure Django logging for `django_q` namespace
5. **Monitoring**: Use admin interface or integrate Sentry via `error_reporter`

## Development Workflow

1. Start database: `mise run db-start`
2. Start backend: `mise run dev-backend`
3. Start worker: `mise run worker` (in separate terminal)

## Next Steps

1. ✅ Spike complete - Django-Q2 selected
2. → Create WorkflowRun model (ZoeaStudio-4l4z)
3. → Add django-q2 dependency (ZoeaStudio-rw98)
4. → Implement background executor (ZoeaStudio-4g48)
