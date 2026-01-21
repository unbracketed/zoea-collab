# API Reference

Zoea Studio provides a RESTful API built with **django-ninja**, featuring automatic validation, type safety, and interactive documentation.

## Interactive API Documentation

When running the backend server locally, you can access the **interactive API documentation** (Swagger UI):

```
http://localhost:8000/api/docs
```

This interface provides:

- **All available endpoints** with request/response schemas
- **Try it out** functionality to test endpoints directly
- **Schema definitions** for all request and response models
- **Authentication details** and requirements

!!! tip "Live Testing"
    The `/api/docs` interface is the best way to explore and test the API. It's auto-generated from the code, so it's always up-to-date.

## API Base URL

**Development:**
```
http://localhost:8000/api
```

The base URL is configured via the `ZOEA_BACKEND_PORT` environment variable (default: 8000).

**Production:**
```
https://yourdomain.com/api
```

## Authentication

Currently, Zoea Studio uses **Django session-based authentication**:

- Session cookies are included automatically in requests
- CORS is configured to allow credentials from the frontend
- Organization membership is verified on protected endpoints

## Common Endpoints

### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "service": "chat"
}
```

**Use case:** Verify backend is running and accessible.

### Chat

```http
POST /api/chat
```

**Request:**
```json
{
  "message": "Hello, how can you help me?",
  "agent_name": "ZoeaAssistant",
  "instructions": "You are a helpful AI assistant.",
  "conversation_history": "User: Hi\n\nAssistant: Hello!"
}
```

**Response:**
```json
{
  "response": "I can help you with research, document management, and workflow automation. What would you like to work on?",
  "agent_name": "ZoeaAssistant",
  "diagram": null
}
```

**Features:**
- Requires authenticated user with organization membership
- Organization context automatically added to agent instructions
- Optional `conversation_history` for diagram generation
- Returns diagram data if conversation history is provided

### Content Transformation

```http
POST /api/transformations/transform
```

**Request:**
```json
{
  "content": "# Hello\n\nThis is **Markdown**",
  "from_format": "markdown",
  "to_format": "html"
}
```

**Response:**
```json
{
  "content": "<h1>Hello</h1>\n<p>This is <strong>Markdown</strong></p>",
  "from_format": "markdown",
  "to_format": "html"
}
```

**Supported Transformations:**
```http
GET /api/transformations/list
```

## Response Format

All API responses follow a consistent structure:

### Success Response

```json
{
  "field1": "value",
  "field2": 123,
  "nested": {
    "field": "value"
  }
}
```

### Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (not authenticated) |
| 403 | Forbidden (no organization or insufficient permissions) |
| 404 | Not Found |
| 500 | Internal Server Error |

## Request Validation

Django Ninja uses **Pydantic** for automatic request validation:

**Example Schema:**
```python
# chat/schemas.py
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    agent_name: str = Field(default="ZoeaAssistant")
    instructions: str = Field(default="You are a helpful assistant.")
    conversation_history: str | None = None
```

**Validation Errors:**

If you send invalid data, you'll receive a `400 Bad Request` with details:

```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Using the API from Frontend

### Fetch Example

```javascript
// Send a chat message
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include', // Include session cookies
  body: JSON.stringify({
    message: 'Hello!',
    agent_name: 'ZoeaAssistant',
  }),
});

const data = await response.json();
console.log(data.response);
```

### Axios Example

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  withCredentials: true, // Include cookies
});

// Send chat message
const { data } = await api.post('/chat', {
  message: 'Hello!',
  agent_name: 'ZoeaAssistant',
});

console.log(data.response);
```

## API Development

### Adding New Endpoints

Create endpoints in `*/api.py` files:

```python
# myapp/api.py
from ninja import Router
from .schemas import MyRequest, MyResponse

router = Router()

@router.post("/myendpoint", response=MyResponse)
def my_endpoint(request, data: MyRequest):
    # Pydantic validates data automatically
    result = process_data(data)
    return MyResponse(**result)
```

Register the router in `zoeastudio/urls.py`:

```python
from ninja import NinjaAPI
from myapp.api import router as myapp_router

api = NinjaAPI()
api.add_router("/myapp", myapp_router)
```

### Defining Schemas

Use Pydantic models in `*/schemas.py`:

```python
from pydantic import BaseModel, Field

class MyRequest(BaseModel):
    field1: str = Field(..., min_length=1, max_length=100)
    field2: int = Field(default=0, ge=0)

class MyResponse(BaseModel):
    result: str
    count: int
```

## OpenAPI Schema

The OpenAPI (Swagger) schema is auto-generated and available at:

```
http://localhost:8000/api/openapi.json
```

You can use this schema to:

- Generate API clients in other languages
- Create additional documentation
- Set up API testing tools

## Rate Limiting

!!! info "Future Enhancement"
    Rate limiting is not currently implemented but is planned for production deployments.

## CORS Configuration

CORS is configured in `backend/zoeastudio/settings.py`:

```python
CORS_ALLOWED_ORIGINS = [
    f"http://localhost:{os.getenv('ZOEA_FRONTEND_PORT', 5173)}"
]

CORS_ALLOW_CREDENTIALS = True
```

The frontend port is dynamically configured via the `ZOEA_FRONTEND_PORT` environment variable.

## Next Steps

- **[Backend Architecture](../architecture/backend.md)** - Learn how the API is structured
- **[Multi-Tenant Guide](../architecture/multi-tenant.md)** - Understand organization scoping
- **[Testing Guide](testing.md)** - Write API integration tests

## Additional Resources

- [Django Ninja Documentation](https://django-ninja.rest-framework.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAPI Specification](https://swagger.io/specification/)
