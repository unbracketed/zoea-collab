"""Configuration management for Zoea CLI."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ZoeaConfig(BaseModel):
    """Zoea CLI configuration."""

    default_organization: Optional[str] = Field(
        default=None, description="Default organization for CLI commands"
    )
    verbose: bool = Field(default=False, description="Verbose output by default")

    class Config:
        """Pydantic config."""

        extra = "ignore"


def get_config_path() -> Path:
    """Get the path to the Zoea config file.

    Returns:
        Path to ~/.zoea/config.yaml
    """
    config_dir = Path.home() / ".zoea"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yaml"


def load_config() -> ZoeaConfig:
    """Load configuration from file.

    Returns:
        ZoeaConfig instance with loaded or default values
    """
    config_path = get_config_path()

    if not config_path.exists():
        return ZoeaConfig()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return ZoeaConfig(**data)
    except Exception:
        # If config file is malformed, return default config
        return ZoeaConfig()


def save_config(config: ZoeaConfig):
    """Save configuration to file.

    Args:
        config: ZoeaConfig instance to save
    """
    config_path = get_config_path()
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(exclude_none=True), f, default_flow_style=False)


def get_organization_filter(org_flag: Optional[str]) -> Optional[str]:
    """Get organization name from flag or config.

    Args:
        org_flag: Organization name from command-line flag

    Returns:
        Organization name to use, or None to show all
    """
    if org_flag:
        return org_flag

    config = load_config()
    return config.default_organization
