# Chat Logging & Debug Guide

## How to See Organization Context

The organization context (organization name, subscription, user info) is automatically added to the **system message** that gets sent to the agent. You can view this in two ways:

### 1. Debug Mode (Recommended for Testing)

Add `"debug": true` to your chat request to see the exact system instructions sent to the agent:

**Request:**
```json
{
  "message": "Hello!",
  "debug": true
}
```

**Response:**
```json
{
  "response": "Hi! How can I help you?",
  "agent_name": "ZoeaAssistant",
  "diagram": null,
  "system_instructions": "Organization Context:\n- Organization: Citrus Grove\n- Subscription: Pro\n- User: brian (brian@citrusgrove.tech)\n\nYou are a helpful AI assistant for Zoea Studio.",
  "organization": "Citrus Grove"
}
```

### 2. Server Logs

The chat API now logs every interaction. View them in your terminal where the backend is running:

```bash
# In terminal 1 - run backend with logging
mise run dev-backend

# You'll see logs like:
# [INFO] Chat request from user 'brian' (org: 'Citrus Grove', subscription: 'pro')
# [DEBUG] Enhanced instructions:
# Organization Context:
# - Organization: Citrus Grove
# - Subscription: Pro
# - User: brian (brian@citrusgrove.tech)
#
# You are a helpful AI assistant for Zoea Studio.
# [INFO] User message: Hello!...
# [INFO] Agent response: Hi! How can I help you?...
```

To see DEBUG level logs, update your Django settings.

## Current Logging

### What's Being Logged

**Currently logged to console:**
- User making the request
- Organization and subscription level
- System instructions (DEBUG level)
- User messages (first 100 chars)
- Agent responses (first 100 chars)

**Location:** Console output where `mise run dev-backend` is running

**Format:** Python logging module

### What's NOT Being Logged

❌ **Not saved to database:**
- No conversation history persistence
- No message storage
- No audit trail

❌ **Not tracked:**
- Conversation threads/sessions
- User engagement metrics
- Token usage/costs

## Future: Database Logging

To persist conversations, you'll want to create models like:

```python
# backend/chat/models.py
from django.db import models
from django.contrib.auth import get_user_model
from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()

class Conversation(models.Model):
    """A conversation thread between a user and an agent."""
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    agent_name = models.CharField(max_length=100)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-updated_at']

class Message(models.Model):
    """A single message in a conversation."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User'),
            ('assistant', 'Assistant'),
            ('system', 'System'),
        ]
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional metadata
    token_count = models.IntegerField(null=True, blank=True)
    model_used = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['created_at']
```

### Benefits of Database Logging

✅ **Conversation History:**
- Load previous conversations
- Continue where you left off
- Search through past interactions

✅ **Analytics:**
- Track usage per organization
- Monitor costs (tokens used)
- Identify popular features

✅ **Audit Trail:**
- Compliance requirements
- User support/debugging
- Quality improvement

✅ **Features:**
- Conversation sharing
- Export conversations
- Favorite responses

## Implementation Checklist

When you're ready to add database logging:

- [ ] Create Conversation and Message models
- [ ] Add migration files
- [ ] Update chat API to save messages
- [ ] Add conversation retrieval endpoint
- [ ] Update frontend to display history
- [ ] Add conversation management (delete, rename, etc.)
- [ ] Implement search functionality
- [ ] Add export feature

## Privacy Considerations

⚠️ **Important:** When logging conversations:
- Store organization ID with each conversation
- Filter queries by user's organization (multi-tenant)
- Consider data retention policies
- Implement user data deletion
- Add encryption for sensitive data
- Follow GDPR/privacy regulations

## Example: Adding Basic Logging

Here's how you'd modify the chat endpoint to save to database:

```python
@router.post("/chat", response=ChatResponse)
async def chat(request, payload: ChatRequest):
    # ... existing code ...

    # Get or create conversation
    @sync_to_async
    def _get_or_create_conversation():
        conversation, created = Conversation.objects.get_or_create(
            organization=organization,
            created_by=request.user,
            agent_name=payload.agent_name,
            # Could use conversation_id from frontend
        )
        return conversation

    conversation = await _get_or_create_conversation()

    # Save user message
    @sync_to_async
    def _save_message(role, content):
        return Message.objects.create(
            conversation=conversation,
            role=role,
            content=content
        )

    await _save_message('user', payload.message)

    # ... get agent response ...

    # Save agent response
    await _save_message('assistant', response_text)

    # ... return response ...
```

## Recommendation

**For now:** Use debug mode and console logs for development

**Next step:** Decide if you want to persist conversations
- If yes: Implement Conversation/Message models
- If no: Continue with console logging only

**Production:** Always have some form of logging for:
- Error tracking
- Usage monitoring
- Support/debugging
