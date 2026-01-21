"""
Tests for SourceRegistry.
"""

import pytest

from sources.base import SourceInterface
from sources.registry import SourceRegistry
from sources.local import LocalFileSystemSource


class MockSource(SourceInterface):
    """Mock source for testing."""

    def validate_config(self):
        pass

    def list_documents(self):
        yield from []

    def read_document(self, path):
        return b''

    def get_display_name(self):
        return 'Mock Source'

    def test_connection(self):
        return True


class TestSourceRegistry:
    """Test SourceRegistry functionality."""

    def setup_method(self):
        """Clean up registry before each test."""
        # Save current registry state
        self._saved_registry = SourceRegistry._registry.copy()

        # Clear registry for isolated testing
        SourceRegistry._registry.clear()

    def teardown_method(self):
        """Restore registry after each test."""
        SourceRegistry._registry = self._saved_registry

    def test_register_source(self):
        """Test registering a source type."""
        SourceRegistry.register('mock', MockSource)

        assert SourceRegistry.is_registered('mock')
        assert SourceRegistry.get('mock') == MockSource

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate type raises error."""
        SourceRegistry.register('mock', MockSource)

        with pytest.raises(ValueError, match="already registered"):
            SourceRegistry.register('mock', MockSource)

    def test_register_non_source_raises_error(self):
        """Test that registering non-SourceInterface class raises error."""
        class NotASource:
            pass

        with pytest.raises(ValueError, match="must inherit from SourceInterface"):
            SourceRegistry.register('invalid', NotASource)

    def test_get_unregistered_raises_error(self):
        """Test that getting unregistered type raises error."""
        with pytest.raises(ValueError, match="Unknown source type"):
            SourceRegistry.get('nonexistent')

    def test_get_unregistered_error_message_includes_available(self):
        """Test that error message includes available types."""
        SourceRegistry.register('mock1', MockSource)
        SourceRegistry.register('mock2', MockSource)

        with pytest.raises(ValueError, match="Available types: mock1, mock2"):
            SourceRegistry.get('nonexistent')

    def test_get_registered_types(self):
        """Test getting all registered types."""
        SourceRegistry.register('mock1', MockSource)
        SourceRegistry.register('mock2', MockSource)

        types = SourceRegistry.get_registered_types()

        assert len(types) == 2
        assert types['mock1'] == MockSource
        assert types['mock2'] == MockSource

    def test_get_registered_types_returns_copy(self):
        """Test that get_registered_types returns a copy, not reference."""
        SourceRegistry.register('mock', MockSource)

        types1 = SourceRegistry.get_registered_types()
        types2 = SourceRegistry.get_registered_types()

        assert types1 is not types2  # Different objects
        assert types1 == types2  # But same content

    def test_is_registered(self):
        """Test checking if type is registered."""
        assert not SourceRegistry.is_registered('mock')

        SourceRegistry.register('mock', MockSource)

        assert SourceRegistry.is_registered('mock')

    def test_unregister(self):
        """Test unregistering a source type."""
        SourceRegistry.register('mock', MockSource)
        assert SourceRegistry.is_registered('mock')

        SourceRegistry.unregister('mock')
        assert not SourceRegistry.is_registered('mock')

    def test_unregister_nonexistent_raises_error(self):
        """Test that unregistering nonexistent type raises error."""
        with pytest.raises(ValueError, match="not registered"):
            SourceRegistry.unregister('nonexistent')

    def test_local_source_registered_by_default(self):
        """Test that LocalFileSystemSource is registered on import."""
        # Restore original registry for this test
        SourceRegistry._registry = self._saved_registry

        assert SourceRegistry.is_registered('local')
        assert SourceRegistry.get('local') == LocalFileSystemSource
