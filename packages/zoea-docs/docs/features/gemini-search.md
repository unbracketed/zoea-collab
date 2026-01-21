# Gemini File Search Query Examples

This document provides examples of using the `query_gemini_store` management command to perform semantic search and RAG (Retrieval Augmented Generation) on project documents.

## Basic Usage

### Simple Query

```bash
python manage.py query_gemini_store "What is this project about?" --project "My Project"
```

**Example Output:**
```
======================================================================
Gemini File Search Query
======================================================================

Query Configuration:
  Project: My Project (Test Organization)
  Store ID: fileSearchStores/abc123xyz
  Query: What is this project about?
  Model: gemini-2.5-flash

----------------------------------------------------------------------

Response:

  This project is a Django-based web application that provides
  document management and AI-powered chat capabilities. It uses
  provider-based LLM integrations and includes a unique Graphologue
  diagram generation system for visualizing conversation concepts.

----------------------------------------------------------------------
```

## Query with Citations

Show which documents were used to answer the query:

```bash
python manage.py query_gemini_store \
  "How do I configure authentication?" \
  --project "My Project" \
  --show-citations
```

**Example Output:**
```
======================================================================
Gemini File Search Query
======================================================================

Query Configuration:
  Project: My Project (Test Organization)
  Store ID: fileSearchStores/abc123xyz
  Query: How do I configure authentication?
  Model: gemini-2.5-flash

----------------------------------------------------------------------

Response:

  To configure authentication, you need to set up django-organizations
  for multi-tenant support. Each user must be part of an Organization
  via the OrganizationUser model. Add the ALLOWED_HOSTS setting to
  your .env file and ensure SECRET_KEY is properly configured.

----------------------------------------------------------------------

Citations:

  Found 2 source(s):

  [1] Source:
      Title: CLAUDE.md
      URI: files/doc-abc123
      Snippet: **⚠️ CRITICAL: All developers MUST follow the
               django-organizations patterns documented in
               `docs/DJANGO_ORGANIZATIONS_GUIDE.md`** Core Principle:
               Every Django user is part of an Organization via the
               OrganizationUser model...

  [2] Source:
      Title: settings.py
      URI: files/doc-def456
      Snippet: ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS",
               "localhost,127.0.0.1").split(",") SECRET_KEY =
               os.getenv("SECRET_KEY",
               'django-insecure-...')

----------------------------------------------------------------------
```

## Query with Metadata Filtering

Search only specific document types:

```bash
python manage.py query_gemini_store \
  "Find all API endpoints" \
  --project "My Project" \
  --metadata-filter "document_type=Markdown"
```

This limits the search to only Markdown documents, ignoring PDFs, Images, etc.

**Other Filter Examples:**
- `document_type=PDF` - Only search PDF documents
- `author=admin` - Only documents created by user "admin"
- `created_at>"2024-01-01T00:00:00"` - Documents created after a date
- `project_id=5` - Documents from project ID 5 (when querying org-level store)

## Verbose Mode

See detailed grounding metadata:

```bash
python manage.py query_gemini_store \
  "What are the main features?" \
  --project "My Project" \
  --verbose
```

Shows additional information including:
- Full grounding metadata structure
- Grounding support segments
- Confidence scores (if available)
- Raw metadata from Gemini API

## Query by Store ID

Bypass project lookup and query directly by store ID:

```bash
python manage.py query_gemini_store \
  "What documents are indexed?" \
  --store-id "fileSearchStores/abc123xyz"
```

Useful when:
- You have the store ID from `list_gemini_stores`
- Testing specific stores
- Working with stores not linked to projects

## Custom Model Selection

Use a different Gemini model:

```bash
python manage.py query_gemini_store \
  "Explain the architecture in detail" \
  --project "My Project" \
  --model "gemini-2.0-flash"
```

Available models:
- `gemini-2.5-flash` (default, fastest)
- `gemini-2.5-pro` (more capable, slower)
- `gemini-2.0-flash` (latest generation, experimental features)

## Common Use Cases

### 1. Documentation Q&A

```bash
python manage.py query_gemini_store \
  "How do I run the tests?" \
  --project "My Project" \
  --metadata-filter "document_type=Markdown" \
  --show-citations
```

### 2. Code Understanding

```bash
python manage.py query_gemini_store \
  "What does the ChatAgentService class do?" \
  --project "My Project" \
  --show-citations
```

### 3. Configuration Lookup

```bash
python manage.py query_gemini_store \
  "What environment variables are required?" \
  --project "My Project" \
  --metadata-filter "document_type=Markdown"
```

### 4. Feature Discovery

```bash
python manage.py query_gemini_store \
  "What testing frameworks are used in this project?" \
  --project "My Project"
```

### 5. Troubleshooting

```bash
python manage.py query_gemini_store \
  "How do I fix CORS errors in development?" \
  --project "My Project" \
  --show-citations
```

## Tips for Better Results

1. **Be Specific**: Instead of "authentication", ask "How do I configure JWT authentication?"
2. **Use Filters**: Narrow down to relevant document types with `--metadata-filter`
3. **Request Citations**: Use `--show-citations` to verify the source of answers
4. **Follow-up Queries**: Each query is independent, so include context in your question
5. **Check Sync Status**: Ensure documents are synced first with `list_gemini_stores`

## Workflow: First Time Setup

```bash
# 1. Sync your documents to create the File Search store
python manage.py sync_gemini_file_search --project "My Project"

# 2. Verify the store was created
python manage.py list_gemini_stores

# 3. Query your documents
python manage.py query_gemini_store \
  "What is this project about?" \
  --project "My Project" \
  --show-citations

# 4. If results are not relevant, try with metadata filtering
python manage.py query_gemini_store \
  "What is this project about?" \
  --project "My Project" \
  --metadata-filter "document_type=Markdown" \
  --show-citations
```

## Error Messages

### "Project does not have a File Search store"
```
Solution: Run sync_gemini_file_search first to create the store
```

### "Project 'XYZ' not found"
```
Solution: Check project name spelling or use project ID instead
```

### "GEMINI_API_KEY not found"
```
Solution: Add GEMINI_API_KEY to your .env file
```

### "Query failed: API connection error"
```
Solution: Check internet connection and verify API key is valid
```

## Advanced: Combining with Other Commands

```bash
# Create a project knowledge base workflow

# 1. List all projects
python manage.py list_gemini_stores

# 2. Sync a specific project's documents
python manage.py sync_gemini_file_search --project "Documentation"

# 3. Query for specific information
python manage.py query_gemini_store \
  "How do I deploy this application?" \
  --project "Documentation" \
  --show-citations

# 4. Filter to only deployment docs
python manage.py query_gemini_store \
  "What are the deployment steps?" \
  --project "Documentation" \
  --metadata-filter "document_type=Markdown" \
  --show-citations
```

## Output Format

The command provides structured output:

1. **Header**: Query configuration and settings
2. **Response**: AI-generated answer based on documents
3. **Citations** (with `--show-citations`): Source documents used
4. **Grounding Metadata** (with `--verbose`): Full API response details

Each section is clearly separated for easy reading and parsing.
