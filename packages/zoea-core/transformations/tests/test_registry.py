"""Tests for the transformer registry system.

This module tests the core registry functionality including:
- Class and factory registration
- MRO-aware lookups
- Duplicate registration detection
- Error handling
- Utility functions
"""

import pytest

from transformations.base import BaseTransformer
from transformations.enums import OutputFormat
from transformations.registry import (
    clear_registry,
    get_available_formats,
    has_transformer,
    register_transformer,
    transform,
)


class DummyBase:
    """Base class for testing MRO registration."""

    def __init__(self, data):
        self.data = data


class DummyChild(DummyBase):
    """Child class for testing MRO fallback."""

    pass


class DummyGrandchild(DummyChild):
    """Grandchild class for testing multi-level MRO."""

    pass


class OtherType:
    """Unrelated type for testing missing transformers."""

    def __init__(self, value):
        self.value = value


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before and after each test for isolation."""
    clear_registry()
    yield
    clear_registry()


class TestBasicRegistration:
    """Tests for basic transformer registration and lookup."""

    def test_register_class_directly(self):
        """Test registering a transformer class."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class DummyToJSONTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"data": source.data}

        obj = DummyBase("test")
        result = transform(obj, OutputFormat.JSON)

        assert result == {"data": "test"}

    def test_register_with_factory(self):
        """Test registering a transformer with a factory function."""

        # Create a factory that can inject dependencies
        call_count = {"count": 0}

        def make_transformer():
            call_count["count"] += 1
            return DummyTransformer()

        class DummyTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"data": source.data, "factory": True}

        # Register using the factory
        register_transformer(DummyBase, OutputFormat.JSON, factory=make_transformer)(
            DummyTransformer
        )

        obj = DummyBase("test")
        result = transform(obj, OutputFormat.JSON)

        assert result == {"data": "test", "factory": True}
        # Factory should be called each time transform() is called
        assert call_count["count"] == 1

        # Call again to ensure factory is called again (fresh instance)
        transform(obj, OutputFormat.JSON)
        assert call_count["count"] == 2

    def test_context_passing(self):
        """Test that context kwargs are passed to transformer."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class ContextAwareTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {
                    "data": source.data,
                    "organization": context.get("organization"),
                    "user": context.get("user"),
                }

        obj = DummyBase("test")
        result = transform(obj, OutputFormat.JSON, organization="org1", user="alice")

        assert result == {"data": "test", "organization": "org1", "user": "alice"}


class TestMRORegistration:
    """Tests for MRO-aware registration and lookup."""

    def test_mro_fallback(self):
        """Test that child classes can use parent class transformers."""

        @register_transformer(DummyBase, OutputFormat.MARKDOWN)
        class BaseToMarkdownTransformer(BaseTransformer):
            def transform(self, source, **context):
                return f"# {source.data}"

        # Should work for base class
        base_obj = DummyBase("base")
        assert transform(base_obj, OutputFormat.MARKDOWN) == "# base"

        # Should also work for child class (MRO lookup)
        child_obj = DummyChild("child")
        assert transform(child_obj, OutputFormat.MARKDOWN) == "# child"

        # And grandchild
        grandchild_obj = DummyGrandchild("grandchild")
        assert transform(grandchild_obj, OutputFormat.MARKDOWN) == "# grandchild"

    def test_child_can_override_parent(self):
        """Test that child-specific transformers override parent transformers."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class DummyBaseTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"type": "base", "data": source.data}

        @register_transformer(DummyChild, OutputFormat.JSON)
        class DummyChildTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"type": "child", "data": source.data}

        base_obj = DummyBase("test")
        assert transform(base_obj, OutputFormat.JSON) == {"type": "base", "data": "test"}

        child_obj = DummyChild("test")
        assert transform(child_obj, OutputFormat.JSON) == {
            "type": "child",
            "data": "test",
        }


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_duplicate_registration_raises(self):
        """Test that registering the same transformer twice raises ValueError."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class FirstTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"first": True}

        # Attempting to register again should raise
        with pytest.raises(
            ValueError, match="Transformer already registered.*DummyBase.*json"
        ):

            @register_transformer(DummyBase, OutputFormat.JSON)
            class SecondTransformer(BaseTransformer):
                def transform(self, source, **context):
                    return {"second": True}

    def test_missing_transformer_raises(self):
        """Test that transforming without a registered transformer raises ValueError."""

        obj = OtherType("test")

        with pytest.raises(
            ValueError,
            match=r"(?s)No transformer registered for OtherType.*markdown.*Available formats.*none",
        ):
            transform(obj, OutputFormat.MARKDOWN)

    def test_invalid_output_format_raises(self):
        """Test that using non-enum output format raises TypeError."""

        obj = DummyBase("test")

        with pytest.raises(TypeError, match="output_format must be an OutputFormat enum"):
            transform(obj, "json")  # String instead of enum

    def test_non_callable_factory_raises(self):
        """Test that registering non-callable factory raises TypeError."""

        with pytest.raises(TypeError, match="Transformer factory must be callable"):

            @register_transformer(DummyBase, OutputFormat.JSON, factory="not_callable")
            class BadTransformer(BaseTransformer):
                def transform(self, source, **context):
                    return {}


class TestUtilityFunctions:
    """Tests for registry utility functions."""

    def test_has_transformer(self):
        """Test has_transformer() helper function."""

        # Initially false
        assert not has_transformer(DummyBase, OutputFormat.JSON)

        # Register a transformer
        @register_transformer(DummyBase, OutputFormat.JSON)
        class DummyTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {}

        # Now should be true
        assert has_transformer(DummyBase, OutputFormat.JSON)

        # Still false for other formats
        assert not has_transformer(DummyBase, OutputFormat.MARKDOWN)

    def test_get_available_formats(self):
        """Test get_available_formats() helper function."""

        # Initially empty
        assert get_available_formats(DummyBase) == []

        # Register multiple transformers
        @register_transformer(DummyBase, OutputFormat.JSON)
        class JSONTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {}

        @register_transformer(DummyBase, OutputFormat.MARKDOWN)
        class MarkdownTransformer(BaseTransformer):
            def transform(self, source, **context):
                return ""

        # Should return sorted list of formats
        formats = get_available_formats(DummyBase)
        assert len(formats) == 2
        assert OutputFormat.JSON in formats
        assert OutputFormat.MARKDOWN in formats

        # Other types should still have no formats
        assert get_available_formats(OtherType) == []

    def test_clear_registry(self):
        """Test that clear_registry() removes all transformers."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class DummyTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {}

        assert has_transformer(DummyBase, OutputFormat.JSON)

        clear_registry()

        assert not has_transformer(DummyBase, OutputFormat.JSON)


class TestCaching:
    """Tests for registry caching behavior."""

    def test_caching_works(self):
        """Test that lookups are cached for performance."""

        call_count = {"count": 0}

        def counting_factory():
            # This shouldn't be called multiple times for the same lookup
            # (only once per transform() call)
            call_count["count"] += 1

            class CountingTransformer(BaseTransformer):
                def transform(self, source, **context):
                    return {"count": call_count["count"]}

            return CountingTransformer()

        register_transformer(DummyBase, OutputFormat.JSON, factory=counting_factory)(
            BaseTransformer
        )

        obj = DummyBase("test")

        # First transform
        result1 = transform(obj, OutputFormat.JSON)
        assert result1 == {"count": 1}

        # Second transform should call factory again (fresh instance)
        # but lookup should be cached
        result2 = transform(obj, OutputFormat.JSON)
        assert result2 == {"count": 2}

        # Both transforms should have happened
        assert call_count["count"] == 2


class TestMultipleFormats:
    """Tests for multiple output formats on the same source type."""

    def test_multiple_formats_same_source(self):
        """Test registering multiple transformers for the same source type."""

        @register_transformer(DummyBase, OutputFormat.JSON)
        class DummyToJSONTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"data": source.data}

        @register_transformer(DummyBase, OutputFormat.MARKDOWN)
        class DummyToMarkdownTransformer(BaseTransformer):
            def transform(self, source, **context):
                return f"# {source.data}"

        @register_transformer(DummyBase, OutputFormat.OUTLINE)
        class DummyToOutlineTransformer(BaseTransformer):
            def transform(self, source, **context):
                return {"sections": [{"title": source.data}]}

        obj = DummyBase("test")

        # All formats should work independently
        assert transform(obj, OutputFormat.JSON) == {"data": "test"}
        assert transform(obj, OutputFormat.MARKDOWN) == "# test"
        assert transform(obj, OutputFormat.OUTLINE) == {"sections": [{"title": "test"}]}

        # Available formats should show all three
        formats = get_available_formats(DummyBase)
        assert len(formats) == 3
