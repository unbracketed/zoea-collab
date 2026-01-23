"""
YAML configuration loader for workflow definitions.

Handles loading and normalizing workflow configuration from YAML files,
including backwards compatibility for legacy naming conventions.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from .exceptions import ConfigurationError
from .types import InputSpec, OutputSpec, ServiceSpec, WorkflowSpec


def load_workflow_config(config_path: Path) -> WorkflowSpec:
    """
    Load and validate a workflow configuration from YAML.

    Args:
        config_path: Path to flow-config.yaml

    Returns:
        Validated WorkflowSpec instance

    Raises:
        ConfigurationError: If config file not found or invalid
    """
    if not config_path.exists():
        raise ConfigurationError(f"Config file not found: {config_path}")

    try:
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {e}")

    if not raw_config:
        raise ConfigurationError(f"Empty config file: {config_path}")

    # Derive slug from directory name
    slug = config_path.parent.name

    # Normalize config keys and structure
    normalized = normalize_config(raw_config, slug)

    try:
        return WorkflowSpec(**normalized)
    except Exception as e:
        raise ConfigurationError(f"Invalid config in {config_path}: {e}")


def normalize_config(raw: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """
    Normalize raw YAML config to expected schema.

    Handles:
    - PLUGINS -> services (legacy naming)
    - service -> name (field rename within service specs)
    - folder -> target (alias in output specs)
    - Case-insensitive key matching (INPUTS, Inputs, inputs)

    Args:
        raw: Raw dictionary from YAML
        slug: Workflow slug derived from directory name

    Returns:
        Normalized config dict ready for WorkflowSpec
    """
    result: Dict[str, Any] = {"slug": slug}

    # Normalize keys to lowercase for matching
    raw_lower = {k.lower(): v for k, v in raw.items()}

    # Process inputs
    inputs_raw = raw_lower.get("inputs", [])
    if inputs_raw:
        result["inputs"] = _normalize_inputs(inputs_raw)

    # Process outputs
    outputs_raw = raw_lower.get("outputs", [])
    if outputs_raw:
        result["outputs"] = _normalize_outputs(outputs_raw)

    # Process services (with PLUGINS fallback)
    services_raw = raw_lower.get("services") or raw_lower.get("plugins", [])
    if services_raw:
        result["services"] = _normalize_services(services_raw)

    # Pass through metadata fields
    if "name" in raw_lower:
        result["name"] = raw_lower["name"]
    if "description" in raw_lower:
        result["description"] = raw_lower["description"]
    if "graph_id" in raw_lower:
        result["graph_id"] = raw_lower["graph_id"]

    return result


def _normalize_inputs(inputs_raw: List[Dict[str, Any]]) -> List[InputSpec]:
    """Normalize input specifications."""
    inputs = []
    for inp in inputs_raw:
        # Fix common typos
        inp_type = inp.get("type", "str")
        if inp_type == "PostiveInt":  # Common typo
            inp_type = "PositiveInt"
        inp["type"] = inp_type

        inputs.append(InputSpec(**inp))
    return inputs


def _normalize_outputs(outputs_raw: List[Dict[str, Any]]) -> List[OutputSpec]:
    """Normalize output specifications."""
    outputs = []
    for out in outputs_raw:
        # Handle folder -> target alias
        if "folder" in out and "target" not in out:
            out["target"] = out["folder"]
        outputs.append(OutputSpec(**out))
    return outputs


def _normalize_services(services_raw: List[Dict[str, Any]]) -> List[ServiceSpec]:
    """Normalize service specifications."""
    services = []
    for svc in services_raw:
        # Handle 'service' -> 'name' field rename
        if "service" in svc and "name" not in svc:
            svc["name"] = svc.pop("service")
        services.append(ServiceSpec(**svc))
    return services


def interpolate_template(template: str, values: Dict[str, Any]) -> str:
    """
    Interpolate {variable} placeholders in template string.

    Args:
        template: String with {var} placeholders (e.g., "Issue {issue_number} Plan")
        values: Dictionary of values to substitute

    Returns:
        Interpolated string

    Raises:
        ConfigurationError: If a required variable is missing
    """
    try:
        return template.format(**values)
    except KeyError as e:
        raise ConfigurationError(f"Missing template variable: {e}")


def discover_builtin_workflows(base_path: Path) -> Dict[str, Path]:
    """
    Discover built-in workflows in the builtin/ directory.

    Args:
        base_path: Path to the workflows/ directory

    Returns:
        Dict mapping workflow slug to config file path
    """
    builtin_dir = base_path / "builtin"
    workflows = {}

    if not builtin_dir.exists():
        return workflows

    for workflow_dir in builtin_dir.iterdir():
        if not workflow_dir.is_dir():
            continue

        config_path = workflow_dir / "flow-config.yaml"
        if config_path.exists():
            workflows[workflow_dir.name] = config_path

    return workflows
