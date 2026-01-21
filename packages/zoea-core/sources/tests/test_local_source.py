"""
Tests for LocalFileSystemSource implementation.
"""

import tempfile
from pathlib import Path
import pytest

from sources.local import LocalFileSystemSource
from sources.base import DocumentMetadata


class TestLocalFileSystemSource:
    """Test LocalFileSystemSource implementation."""

    def test_validate_config_missing_path(self):
        """Test that validation fails when path is missing."""
        with pytest.raises(ValueError, match="requires 'path'"):
            LocalFileSystemSource({})

    def test_validate_config_relative_path(self):
        """Test that validation fails for relative paths."""
        with pytest.raises(ValueError, match="must be absolute"):
            LocalFileSystemSource({'path': 'relative/path'})

    def test_validate_config_nonexistent_path(self):
        """Test that validation fails for nonexistent paths."""
        with pytest.raises(ValueError, match="does not exist"):
            LocalFileSystemSource({'path': '/nonexistent/path/to/nowhere'})

    def test_validate_config_file_not_directory(self, tmp_path):
        """Test that validation fails when path is a file, not directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(ValueError, match="not a directory"):
            LocalFileSystemSource({'path': str(test_file)})

    def test_validate_config_success(self, tmp_path):
        """Test that validation succeeds for valid config."""
        source = LocalFileSystemSource({'path': str(tmp_path)})
        assert source.config['path'] == str(tmp_path)

    def test_list_documents_empty_directory(self, tmp_path):
        """Test listing documents from an empty directory."""
        source = LocalFileSystemSource({'path': str(tmp_path)})
        docs = list(source.list_documents())
        assert len(docs) == 0

    def test_list_documents_with_supported_files(self, tmp_path):
        """Test listing documents with supported file types."""
        # Create test files
        (tmp_path / "doc1.md").write_text("# Document 1")
        (tmp_path / "doc2.pdf").write_bytes(b"PDF content")
        (tmp_path / "image.png").write_bytes(b"PNG content")
        (tmp_path / "data.csv").write_text("a,b,c\n1,2,3")

        source = LocalFileSystemSource({'path': str(tmp_path)})
        docs = list(source.list_documents())

        assert len(docs) == 4
        assert all(isinstance(d, DocumentMetadata) for d in docs)

        # Check that all files are present
        names = {d.name for d in docs}
        assert names == {'doc1.md', 'doc2.pdf', 'image.png', 'data.csv'}

    def test_list_documents_ignores_unsupported_files(self, tmp_path):
        """Test that unsupported file types are ignored."""
        # Create test files
        (tmp_path / "doc.md").write_text("# Document")
        (tmp_path / "script.py").write_text("print('hello')")  # Unsupported
        (tmp_path / "binary.exe").write_bytes(b"EXE")  # Unsupported

        source = LocalFileSystemSource({'path': str(tmp_path)})
        docs = list(source.list_documents())

        assert len(docs) == 1
        assert docs[0].name == 'doc.md'

    def test_list_documents_recursive(self, tmp_path):
        """Test recursive directory traversal."""
        # Create nested structure
        (tmp_path / "doc1.md").write_text("# Root Doc")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc2.md").write_text("# Subdir Doc")

        source = LocalFileSystemSource({
            'path': str(tmp_path),
            'recursive': True
        })
        docs = list(source.list_documents())

        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {'doc1.md', 'doc2.md'}

    def test_list_documents_pattern_filter(self, tmp_path):
        """Test filtering with glob pattern."""
        # Create test files
        (tmp_path / "doc1.md").write_text("# Document 1")
        (tmp_path / "doc2.md").write_text("# Document 2")
        (tmp_path / "image.png").write_bytes(b"PNG")

        source = LocalFileSystemSource({
            'path': str(tmp_path),
            'pattern': '*.md'
        })
        docs = list(source.list_documents())

        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {'doc1.md', 'doc2.md'}

    def test_list_documents_metadata(self, tmp_path):
        """Test that document metadata is populated correctly."""
        test_file = tmp_path / "test.md"
        content = "# Test Document\nThis is a test."
        test_file.write_text(content)

        source = LocalFileSystemSource({'path': str(tmp_path)})
        docs = list(source.list_documents())

        assert len(docs) == 1
        doc = docs[0]

        assert doc.name == 'test.md'
        assert doc.path == str(test_file)
        assert doc.size == len(content.encode('utf-8'))
        assert doc.extension == '.md'
        assert doc.content_type == 'text/markdown'
        assert doc.modified_at is not None

    def test_read_document_success(self, tmp_path):
        """Test reading document content."""
        test_file = tmp_path / "test.md"
        content = "# Test Document\nThis is a test."
        test_file.write_text(content)

        source = LocalFileSystemSource({'path': str(tmp_path)})
        data = source.read_document(str(test_file))

        assert data == content.encode('utf-8')

    def test_read_document_not_found(self, tmp_path):
        """Test reading nonexistent document."""
        source = LocalFileSystemSource({'path': str(tmp_path)})

        with pytest.raises(FileNotFoundError):
            source.read_document(str(tmp_path / 'nonexistent.md'))

    def test_read_document_is_directory(self, tmp_path):
        """Test that reading a directory raises an error."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        source = LocalFileSystemSource({'path': str(tmp_path)})

        with pytest.raises(ValueError, match="not a file"):
            source.read_document(str(subdir))

    def test_get_display_name(self, tmp_path):
        """Test display name generation."""
        source = LocalFileSystemSource({'path': str(tmp_path)})
        display_name = source.get_display_name()

        assert 'Local Filesystem' in display_name
        assert str(tmp_path) in display_name

    def test_get_display_name_with_pattern(self, tmp_path):
        """Test display name includes pattern."""
        source = LocalFileSystemSource({
            'path': str(tmp_path),
            'pattern': '**/*.md'
        })
        display_name = source.get_display_name()

        assert 'Local Filesystem' in display_name
        assert str(tmp_path) in display_name
        assert '**/*.md' in display_name

    def test_test_connection_success(self, tmp_path):
        """Test successful connection test."""
        source = LocalFileSystemSource({'path': str(tmp_path)})
        assert source.test_connection() is True

    def test_test_connection_nonexistent_path(self, tmp_path):
        """Test connection test with nonexistent path."""
        # Create source with valid path first
        source = LocalFileSystemSource({'path': str(tmp_path)})

        # Manually change config to invalid path to test connection failure
        source.config['path'] = '/nonexistent/path'

        assert source.test_connection() is False

    def test_test_connection_permission_denied(self, tmp_path):
        """Test connection test with permission denied (Unix only)."""
        import sys
        if sys.platform == 'win32':
            pytest.skip("Permission tests not applicable on Windows")

        # Create directory and remove read permissions
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()
        restricted_dir.chmod(0o000)

        try:
            source = LocalFileSystemSource({'path': str(tmp_path)})
            source.config['path'] = str(restricted_dir)
            assert source.test_connection() is False
        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    def test_symlink_handling(self, tmp_path):
        """Test handling of symbolic links."""
        import sys
        if sys.platform == 'win32':
            pytest.skip("Symlink tests not fully supported on Windows")

        # Create real file
        real_file = tmp_path / "real.md"
        real_file.write_text("# Real Document")

        # Create symlink
        link_file = tmp_path / "link.md"
        link_file.symlink_to(real_file)

        # Test with follow_symlinks=False (default)
        source = LocalFileSystemSource({
            'path': str(tmp_path),
            'follow_symlinks': False
        })
        docs = list(source.list_documents())

        # Should only see the real file
        assert len(docs) == 1
        assert docs[0].name == 'real.md'

        # Test with follow_symlinks=True
        source = LocalFileSystemSource({
            'path': str(tmp_path),
            'follow_symlinks': True
        })
        docs = list(source.list_documents())

        # Should see both files
        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {'real.md', 'link.md'}
