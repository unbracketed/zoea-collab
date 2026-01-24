"""Tests for code block extraction from conversation messages."""

import pytest
from django.contrib.auth import get_user_model

from chat.code_block_extractor import (
    CODE_BLOCK_PATTERN,
    ExtractedCodeBlock,
    create_artifacts_from_code_blocks,
    extract_code_blocks,
    extract_markdown_tables,
    extract_all_content_blocks,
)
from chat.models import Conversation, Message
from documents.models import CollectionItemSourceChannel, CollectionType, DocumentCollection

User = get_user_model()


class TestExtractCodeBlocks:
    """Tests for the extract_code_blocks function."""

    def test_extract_single_code_block(self):
        """Test extracting a single code block."""
        text = '''Here is some code:

```python
def hello():
    print("Hello, World!")
```

That's it!'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 1
        assert blocks[0].language == 'python'
        assert 'def hello():' in blocks[0].content
        assert 'print("Hello, World!")' in blocks[0].content

    def test_extract_multiple_code_blocks(self):
        """Test extracting multiple code blocks."""
        text = '''First block:

```javascript
const x = 1;
```

Second block:

```python
x = 1
```

Third block:

```sql
SELECT * FROM users;
```'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 3
        assert blocks[0].language == 'javascript'
        assert blocks[1].language == 'python'
        assert blocks[2].language == 'sql'

    def test_extract_code_block_without_language(self):
        """Test extracting code block without language specifier."""
        text = '''```
some code
```'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 1
        assert blocks[0].language == 'text'
        assert blocks[0].content == 'some code'

    def test_extract_empty_code_block_ignored(self):
        """Test that empty code blocks are ignored."""
        text = '''```python
```'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 0

    def test_no_code_blocks(self):
        """Test text without code blocks."""
        text = "Just some regular text without any code."

        blocks = extract_code_blocks(text)

        assert len(blocks) == 0

    def test_code_block_preserves_whitespace(self):
        """Test that code block content preserves internal whitespace."""
        text = '''```python
def foo():
    if True:
        return 1
```'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 1
        assert '    if True:' in blocks[0].content
        assert '        return 1' in blocks[0].content

    def test_code_block_positions(self):
        """Test that positions are correctly tracked."""
        text = '''Start
```python
code
```
End'''

        blocks = extract_code_blocks(text)

        assert len(blocks) == 1
        assert blocks[0].start_pos == 6  # After "Start\n"
        assert blocks[0].end_pos < len(text)


class TestExtractMarkdownTables:
    """Tests for the extract_markdown_tables function."""

    def test_extract_simple_table(self):
        """Test extracting a simple markdown table."""
        text = '''Here is a table:

| Name | Age |
|------|-----|
| John | 30  |
| Jane | 25  |

That's it!'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 1
        assert tables[0].language == 'markdown'
        assert '| Name | Age |' in tables[0].content
        assert '| John | 30  |' in tables[0].content

    def test_extract_table_with_alignment(self):
        """Test extracting table with column alignment."""
        text = '''| Left | Center | Right |
|:-----|:------:|------:|
| A    |   B    |     C |'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 1
        assert ':------:' in tables[0].content

    def test_skip_table_without_separator(self):
        """Test that tables without proper separator are skipped."""
        text = '''| Header1 | Header2 |
| Data1   | Data2   |'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 0  # No separator row

    def test_skip_table_inside_code_block(self):
        """Test that tables inside code blocks are not extracted."""
        text = '''```markdown
| Name | Age |
|------|-----|
| John | 30  |
```'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 0  # Inside code block

    def test_multiple_tables(self):
        """Test extracting multiple tables."""
        text = '''First table:

| A | B |
|---|---|
| 1 | 2 |

Second table:

| X | Y |
|---|---|
| 3 | 4 |'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 2

    def test_table_minimum_rows(self):
        """Test that table needs at least 3 rows (header, separator, data)."""
        text = '''| Header |
|--------|'''

        tables = extract_markdown_tables(text)

        assert len(tables) == 0  # Only 2 rows, need at least 3


class TestExtractAllContentBlocks:
    """Tests for combined extraction of code blocks and tables."""

    def test_extracts_both_code_and_tables(self):
        """Test that both code blocks and tables are extracted."""
        text = '''Here's some code:

```python
print("hello")
```

And a table:

| Game | Time |
|------|------|
| A vs B | 7PM |'''

        blocks = extract_all_content_blocks(text)

        assert len(blocks) == 2
        assert blocks[0].language == 'python'  # Code block first by position
        assert blocks[1].language == 'markdown'  # Table second

    def test_sorted_by_position(self):
        """Test blocks are sorted by position."""
        text = '''| A | B |
|---|---|
| 1 | 2 |

```python
code
```'''

        blocks = extract_all_content_blocks(text)

        assert len(blocks) == 2
        assert blocks[0].language == 'markdown'  # Table is first in text
        assert blocks[1].language == 'python'


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass',
    )


@pytest.fixture
def organization(db):
    """Create a test organization."""
    from organizations.models import Organization
    return Organization.objects.create(name='Test Org')


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    from projects.models import Project
    return Project.objects.create(
        organization=organization,
        name='Test Project',
        created_by=user,
    )


@pytest.fixture
def conversation(db, organization, project, user):
    """Create a test conversation."""
    return Conversation.objects.create(
        organization=organization,
        project=project,
        created_by=user,
        title='Test Conversation',
    )


class TestCreateArtifactsFromCodeBlocks:
    """Tests for creating artifacts from code blocks."""

    def test_creates_artifacts_for_assistant_message(
        self, conversation, user
    ):
        """Test that artifacts are created for assistant message with code blocks."""
        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='''Here's some code:

```python
def hello():
    print("Hello!")
```

And more:

```javascript
console.log("Hi");
```''',
        )

        count = create_artifacts_from_code_blocks(conversation, message, user)

        assert count == 2

        # Verify conversation has artifacts collection
        conversation.refresh_from_db()
        assert conversation.artifacts is not None
        assert conversation.artifacts.collection_type == CollectionType.ARTIFACT

        # Verify items created
        items = list(conversation.artifacts.items.all())
        assert len(items) == 2

        # Verify metadata
        python_item = next(
            i for i in items if i.source_metadata.get('language') == 'python'
        )
        assert 'def hello():' in python_item.source_metadata['code']
        assert python_item.source_metadata['message_id'] == message.id
        assert python_item.source_channel == CollectionItemSourceChannel.CODE

    def test_skips_user_messages(self, conversation, user):
        """Test that user messages are skipped."""
        message = Message.objects.create(
            conversation=conversation,
            role='user',
            content='''```python
some code
```''',
        )

        count = create_artifacts_from_code_blocks(conversation, message, user)

        assert count == 0

    def test_handles_message_without_code_blocks(self, conversation, user):
        """Test handling of message without code blocks."""
        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Just some text without code.',
        )

        count = create_artifacts_from_code_blocks(conversation, message, user)

        assert count == 0
        # Should not create artifacts collection
        conversation.refresh_from_db()
        assert conversation.artifacts is None

    def test_reuses_existing_artifacts_collection(
        self, conversation, organization, project, user
    ):
        """Test that existing artifacts collection is reused."""
        # Pre-create artifacts collection
        existing = DocumentCollection.objects.create(
            organization=organization,
            project=project,
            collection_type=CollectionType.ARTIFACT,
            name='Existing',
            created_by=user,
        )
        conversation.artifacts = existing
        conversation.save()

        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='''```python
code
```''',
        )

        create_artifacts_from_code_blocks(conversation, message, user)

        # Should use existing collection
        conversation.refresh_from_db()
        assert conversation.artifacts_id == existing.id
        assert existing.items.count() == 1
