"""
Type definitions for workflow inputs, outputs, and services.

Provides Pydantic models for validating workflow configuration from YAML files.
"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field, model_validator


# Map config type strings to Python types
PYDANTIC_TYPE_MAP: Dict[str, Type] = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "PositiveInt": int,  # Validated separately
    "float": float,
    "bool": bool,
    "boolean": bool,
    # Internal Zoea types resolve to str (paths) or int (IDs)
    "Folder": str,
    "MarkdownDocument": str,
    "Clipboard": int,
    "D2Diagram": str,
    "Image": str,
    "PDF": str,
}


class InputSpec(BaseModel):
    """Specification for a workflow input parameter."""

    name: str = Field(..., description="Input parameter name")
    type: str = Field(default="str", description="Input type (str, int, PositiveInt, etc.)")
    value: Optional[Any] = Field(default=None, description="Default value if not provided")
    required: bool = Field(default=True, description="Whether input is required")
    description: str = Field(default="", description="Human-readable description")

    @property
    def python_type(self) -> Type:
        """Get the Python type for this input."""
        return PYDANTIC_TYPE_MAP.get(self.type, str)

    def validate_value(self, value: Any) -> Any:
        """Validate and coerce a value to the expected type."""
        if value is None:
            if self.required and self.value is None:
                raise ValueError(f"Required input '{self.name}' not provided")
            return self.value

        # Type coercion
        try:
            typed_value = self.python_type(value)

            # Additional validation for PositiveInt
            if self.type == "PositiveInt" and typed_value <= 0:
                raise ValueError(f"Input '{self.name}' must be a positive integer")

            return typed_value
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid value for input '{self.name}': {e}")


class OutputSpec(BaseModel):
    """Specification for a workflow output."""

    name: str = Field(..., description="Output name (can contain {variable} templates)")
    type: str = Field(..., description="Output type (MarkdownDocument, D2Diagram, etc.)")
    target: Optional[str] = Field(
        default=None, description="Target folder path (can contain {variable} templates)"
    )
    folder: Optional[str] = Field(
        default=None, description="Alias for target (backwards compatibility)"
    )

    @model_validator(mode="after")
    def set_target_from_folder(self) -> "OutputSpec":
        """Use folder as target if target not specified."""
        if self.target is None and self.folder:
            self.target = self.folder
        return self


class ServiceSpec(BaseModel):
    """Specification for a workflow service binding."""

    name: str = Field(..., description="Service class name (e.g., PyGithubInterface)")
    ctxref: str = Field(..., description="Context reference name (e.g., 'gh', 'ai')")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Service configuration parameters"
    )


class WorkflowSpec(BaseModel):
    """Complete workflow specification from YAML config."""

    slug: str = Field(..., description="Workflow identifier (derived from directory name)")
    name: Optional[str] = Field(default=None, description="Human-readable name")
    description: str = Field(default="", description="Workflow description")
    graph_id: Optional[str] = Field(
        default=None, description="Optional LangGraph graph identifier"
    )
    inputs: List[InputSpec] = Field(default_factory=list, description="Input specifications")
    outputs: List[OutputSpec] = Field(default_factory=list, description="Output specifications")
    services: List[ServiceSpec] = Field(default_factory=list, description="Service bindings")

    @model_validator(mode="after")
    def default_name_from_slug(self) -> "WorkflowSpec":
        """Generate default name from slug if not provided."""
        if self.name is None and self.slug:
            self.name = self.slug.replace("-", " ").replace("_", " ").title()
        return self

    def get_input_spec(self, name: str) -> Optional[InputSpec]:
        """Get input spec by name."""
        for inp in self.inputs:
            if inp.name == name:
                return inp
        return None

    def get_output_spec(self, name: str) -> Optional[OutputSpec]:
        """Get output spec by name."""
        for out in self.outputs:
            if out.name == name:
                return out
        return None

    def get_service_spec(self, ctxref: str) -> Optional[ServiceSpec]:
        """Get service spec by context reference."""
        for svc in self.services:
            if svc.ctxref == ctxref:
                return svc
        return None
