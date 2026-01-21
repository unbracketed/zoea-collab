# Common Workflows

Practical examples of common development workflows in Zoea Studio.

## Adding a New API Endpoint

### 1. Define Pydantic Schemas

Create request and response schemas in `*/schemas.py`:

```python
# myapp/schemas.py
from pydantic import BaseModel, Field

class CreateItemRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")

class ItemResponse(BaseModel):
    id: int
    title: str
    description: str
    created_at: str
```

### 2. Create the Endpoint

Add endpoint to router in `*/api.py`:

```python
# myapp/api.py
from ninja import Router
from .schemas import CreateItemRequest, ItemResponse
from .models import Item
from accounts.utils import require_organization

router = Router()

@router.post("/items", response=ItemResponse)
def create_item(request, data: CreateItemRequest):
    org = require_organization(request.user)

    item = Item.objects.create(
        organization=org,
        created_by=request.user,
        title=data.title,
        description=data.description
    )

    return ItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        created_at=item.created_at.isoformat()
    )
```

### 3. Register the Router

In `backend/zoeastudio/urls.py`:

```python
from myapp.api import router as myapp_router

api.add_router("/myapp", myapp_router)
```

### 4. Test the Endpoint

```python
# myapp/tests.py
import pytest
from django.contrib.auth.models import User
from accounts.models import Account

@pytest.mark.django_db
def test_create_item(client):
    # Setup
    org = Account.objects.create(name="Test Org")
    user = User.objects.create_user(username="test", password="pass")
    org.add_user(user)
    client.force_login(user)

    # Test
    response = client.post('/api/myapp/items', {
        'title': 'Test Item',
        'description': 'Test description'
    }, content_type='application/json')

    assert response.status_code == 200
    data = response.json()
    assert data['title'] == 'Test Item'
```

### 5. Try it Out

```bash
# Start backend
mise run dev-backend

# Visit http://localhost:8000/api/docs
# Try the new endpoint in Swagger UI
```

## Working with the Agent Service

### 1. Create an Agent Instance

```python
from chat.agent_service import ChatAgentService

service = ChatAgentService()
service.create_agent(
    name="MyAssistant",
    instructions="You are a helpful assistant specialized in..."
)
```

### 2. Send a Message

```python
# Complete response
response = await service.chat("Hello, how are you?")
print(response)
```

### 3. Stream Responses

```python
# Streaming
async for chunk in service.chat_stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

### 4. Use in API Endpoints

```python
@router.post("/chat")
async def chat(request, data: ChatRequest):
    org = require_organization(request.user)

    service = ChatAgentService()
    service.create_agent(
        name="OrgAssistant",
        instructions=f"You are assisting {request.user.username} from {org.name}."
    )

    response = await service.chat(data.message)

    return ChatResponse(response=response)
```

## Modifying Graphologue Logic

### 1. Understanding the System

Graphologue converts conversation text into annotated concept maps.

**Location:** `backend/chat/graphologue_service.py`

### 2. Customizing the Prompt

```python
# chat/graphologue_service.py
GRAPH_PROMPT = """
Annotate this text with entities and relationships...

[Your custom instructions here]
"""
```

### 3. Adjusting Parsing

```python
# Modify regex patterns
NODE_REGEX = r'\[([^\]]+?)\s+\(\$N\d+\)\]'
EDGE_REGEX = r'\[([^\]]+?)\s+\(\$H,\s*\$N\d+,\s*\$N\d+\)\]'

# Update parse_nodes() and parse_edges() functions
def parse_nodes(annotated_text: str) -> list[dict]:
    # Your parsing logic
    pass
```

### 4. Testing Changes

```python
@pytest.mark.asyncio
async def test_graphologue_parsing():
    service = GraphologueService()

    text = "Alice went to the store."
    result = await service.convert_to_diagram(text)

    assert 'nodes' in result
    assert 'edges' in result
```

## Adding a New Django Model

### 1. Create the Model

```python
# myapp/models.py
from django.db import models
from accounts.managers import OrganizationScopedQuerySet

class MyModelQuerySet(OrganizationScopedQuerySet):
    def for_user(self, user):
        return self.filter(
            organization__organization_users__user=user
        )

class MyModel(models.Model):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MyModelQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
        ]
```

### 2. Create and Run Migrations

```bash
cd backend
uv run python manage.py makemigrations
uv run python manage.py migrate
```

### 3. Register in Admin

```python
# myapp/admin.py
from django.contrib import admin
from .models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ['title', 'organization', 'created_by', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['title']
```

### 4. Test the Model

```python
@pytest.mark.django_db
def test_mymodel_for_user():
    org = Account.objects.create(name="Test Org")
    user = User.objects.create_user(username="test", password="pass")
    org.add_user(user)

    obj = MyModel.objects.create(
        organization=org,
        created_by=user,
        title="Test"
    )

    # Should be visible to user
    assert obj in MyModel.objects.for_user(user)

    # Should NOT be visible to other users
    other_user = User.objects.create_user(username="other", password="pass")
    assert obj not in MyModel.objects.for_user(other_user)
```

## Adding a React Component

### 1. Create the Component

```javascript
// src/components/MyComponent.jsx
import { useState, useEffect } from 'react';

export default function MyComponent({ title }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch('/api/myapp/items');
        const json = await response.json();
        setData(json);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);  // Empty deps = run once on mount

  if (loading) return <div>Loading...</div>;

  return (
    <div className="my-component">
      <h2>{title}</h2>
      {data && <pre>{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}
```

### 2. Add to Router

```javascript
// src/App.jsx
import MyComponent from './components/MyComponent';

<Route path="/mycomponent" element={<MyComponent title="My Page" />} />
```

### 3. Test with Playwright

```javascript
// tests/e2e/mycomponent.spec.js
import { test, expect } from '@playwright/test';

test('MyComponent displays data', async ({ page }) => {
  await page.goto('/mycomponent');

  await expect(page.locator('h2')).toContainText('My Page');
  await expect(page.locator('.my-component')).toBeVisible();
});
```

## Running Tests

### Backend Unit Tests

```bash
# All tests
mise run test

# Specific file
cd backend && uv run pytest myapp/tests.py

# Specific test
cd backend && uv run pytest myapp/tests.py::test_mymodel

# With coverage
mise run test-cov

# With verbose output
cd backend && uv run pytest -vv
```

### Frontend E2E Tests

```bash
# Headless
mise run test-e2e

# With UI
mise run test-e2e-ui

# Headed (visible browser)
mise run test-e2e-headed

# Specific test
cd frontend && npm run test:e2e -- tests/e2e/mytest.spec.js
```

### All Tests

```bash
mise run test-all
```

## Database Operations

### Resetting the Database (Development)

```bash
cd backend
rm db.sqlite3
uv run python manage.py migrate
uv run python manage.py initialize_local_user
```

### Creating a Superuser

```bash
cd backend
uv run python manage.py createsuperuser
```

### Running Migrations

```bash
cd backend

# Create migrations for changes
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate

# View migration SQL (without applying)
uv run python manage.py sqlmigrate myapp 0001
```

### Django Shell

```bash
cd backend
uv run python manage.py shell
```

```python
# In shell
from accounts.models import Account
from django.contrib.auth.models import User

# Get all organizations
orgs = Account.objects.all()

# Create a user
user = User.objects.create_user('newuser', 'email@example.com', 'password')

# Add user to organization
org = Account.objects.first()
org.add_user(user)
```

## Git Workflows

### Feature Branch Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "Add my feature"

# Push to remote
git push -u origin feature/my-feature

# Create PR on GitHub
# (Or use gh CLI: gh pr create)
```

### Running Pre-commit Checks

```bash
# Format code
mise run format

# Check linting
mise run lint

# Run tests
mise run test-all
```

## Deployment

### Building for Production

```bash
# Backend: Install production dependencies
cd backend && uv sync --no-dev

# Frontend: Build static files
cd frontend && npm run build
```

### Collecting Static Files

```bash
cd backend
uv run python manage.py collectstatic --noinput
```

### Running Production Server

```bash
# Using Gunicorn
cd backend
uv run gunicorn zoeastudio.wsgi:application --bind 0.0.0.0:8000
```

## Debugging

### Backend Debug Mode

Django debug toolbar (add to dev dependencies):

```bash
cd backend
uv add django-debug-toolbar --group dev
```

```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
```

### Frontend Debug Mode

React DevTools browser extension for debugging components and state.

### Print Debugging in Tests

```bash
cd backend
uv run pytest -s myapp/tests.py  # -s shows print statements
```

## Related Documentation

- [Getting Started](../getting-started/index.md) - Initial setup
- [Architecture](../architecture/overview.md) - System design
- [Multi-Tenant Guide](../architecture/multi-tenant.md) - Critical patterns
- [Testing Guide](../development/testing.md) - Testing strategies
