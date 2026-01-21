"""
Agent Skills registry and prompt helpers.

Discovers Agent Skills on disk, validates SKILL.md frontmatter, and
provides helpers for listing skills and building prompt metadata.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

import yaml
from django.conf import settings

logger = logging.getLogger(__name__)

SKILL_LOADER_TOOL_NAME = "load_skill"

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500


class SkillRegistryError(Exception):
    """Base error for skill registry operations."""


class SkillNotFoundError(SkillRegistryError):
    """Raised when a skill cannot be found."""


class SkillFileError(SkillRegistryError):
    """Raised when a skill file cannot be read."""


@dataclass(frozen=True)
class SkillMetadata:
    """Metadata for a discovered Agent Skill."""

    name: str
    description: str
    root: Path
    skill_path: Path
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    supported_contexts: list[str] = field(default_factory=lambda: ["*"])


class SkillRegistry:
    """
    Registry for skills discovered on disk.

    Uses configured roots from Django settings to discover skill directories
    containing a SKILL.md file. Results are cached per process.
    """

    _instance: Optional["SkillRegistry"] = None

    def __init__(self, roots: list[Path]):
        self._roots = roots
        self._skills: dict[str, SkillMetadata] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Return the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls(_load_skill_roots())
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def list_skills(
        self,
        *,
        context: str | None = None,
        refresh: bool = False,
    ) -> list[SkillMetadata]:
        """
        Return skills discovered on disk.

        Args:
            context: Optional context name for filtering.
            refresh: Force a rescan of skill directories.
        """
        self._ensure_loaded(refresh=refresh)
        skills = sorted(self._skills.values(), key=lambda skill: skill.name)
        if not context:
            return skills
        return [skill for skill in skills if _supports_context(skill, context)]

    def get_skill(self, name: str) -> SkillMetadata | None:
        """Return metadata for a skill by name."""
        self._ensure_loaded()
        return self._skills.get(name)

    def read_skill_file(self, name: str, relative_path: str | None = None) -> str:
        """
        Read a file within a skill directory.

        Args:
            name: Skill name
            relative_path: Relative path within the skill directory

        Raises:
            SkillNotFoundError: If the skill is not found
            SkillFileError: If the file is missing or invalid
        """
        self._ensure_loaded()
        skill = self._skills.get(name)
        if not skill:
            raise SkillNotFoundError(f"Skill '{name}' not found")

        rel_path = relative_path or "SKILL.md"
        target_path = Path(rel_path)
        if target_path.is_absolute() or ".." in target_path.parts:
            raise SkillFileError("Invalid skill file path")

        full_path = (skill.root / target_path).resolve()
        root_path = skill.root.resolve()
        if not full_path.is_relative_to(root_path):
            raise SkillFileError("Skill file path escapes skill directory")
        if not full_path.exists() or not full_path.is_file():
            raise SkillFileError("Skill file does not exist")

        return full_path.read_text(encoding="utf-8", errors="replace")

    def build_available_skills_prompt(
        self,
        *,
        context: str | None = None,
        include_locations: bool = False,
    ) -> str | None:
        """
        Build an <available_skills> XML block for prompt injection.

        Args:
            context: Optional context name for filtering.
            include_locations: Include absolute SKILL.md paths.
        """
        skills = self.list_skills(context=context)
        if not skills:
            return None

        lines = ["<available_skills>"]
        for skill in skills:
            lines.append("  <skill>")
            lines.append(f"    <name>{escape(skill.name)}</name>")
            lines.append(f"    <description>{escape(skill.description)}</description>")
            if include_locations:
                lines.append(
                    f"    <location>{escape(str(skill.skill_path))}</location>"
                )
            lines.append("  </skill>")
        lines.append("</available_skills>")

        return "\n".join(lines)

    def _ensure_loaded(self, refresh: bool = False) -> None:
        if not self._loaded or refresh:
            self._skills = self._discover_skills()
            self._loaded = True

    def _discover_skills(self) -> dict[str, SkillMetadata]:
        skills: dict[str, SkillMetadata] = {}
        for root in self._roots:
            if not root.exists():
                logger.debug("Skill root does not exist: %s", root)
                continue
            if not root.is_dir():
                logger.warning("Skill root is not a directory: %s", root)
                continue

            for child in root.iterdir():
                if not child.is_dir():
                    continue
                skill_path = child / "SKILL.md"
                if not skill_path.exists():
                    continue

                metadata = _parse_skill_metadata(skill_path)
                if not metadata:
                    continue

                if metadata.name in skills:
                    logger.warning(
                        "Duplicate skill name '%s' found at %s; skipping",
                        metadata.name,
                        skill_path,
                    )
                    continue

                skills[metadata.name] = metadata

        return skills


def build_skills_context_block(
    *,
    context: str | None,
    tool_name: str | None,
    include_locations: bool = False,
) -> str:
    """
    Build a prompt block describing available skills and how to load them.

    Returns an empty string when skills are unavailable.
    """
    registry = SkillRegistry.get_instance()
    skills_prompt = registry.build_available_skills_prompt(
        context=context,
        include_locations=include_locations,
    )
    if not skills_prompt:
        return ""

    if tool_name:
        instruction = (
            f"To use a skill, call the `{tool_name}` tool to load SKILL.md "
            "instructions or related files."
        )
    elif include_locations:
        instruction = "Skill instructions can be read from the locations above."
    else:
        instruction = ""

    tail = f"\n\n{instruction}" if instruction else ""
    return f"Available Agent Skills:\n{skills_prompt}{tail}"


def _load_skill_roots() -> list[Path]:
    raw_roots = getattr(settings, "AGENT_SKILLS_DIRS", [])
    if isinstance(raw_roots, (str, Path)):
        raw_roots = [raw_roots]
    roots: list[Path] = []
    for root in raw_roots:
        if not root:
            continue
        roots.append(Path(root).expanduser())
    return roots


def _parse_skill_metadata(skill_path: Path) -> SkillMetadata | None:
    try:
        content = skill_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read skill %s: %s", skill_path, exc)
        return None

    try:
        frontmatter = _extract_frontmatter(content)
    except ValueError as exc:
        logger.warning("Invalid frontmatter in %s: %s", skill_path, exc)
        return None

    try:
        data = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s", skill_path, exc)
        return None

    if not isinstance(data, dict):
        logger.warning("Frontmatter must be a mapping in %s", skill_path)
        return None

    name = _coerce_str(data.get("name"))
    description = _coerce_str(data.get("description"))

    if not _valid_skill_name(name):
        logger.warning("Invalid skill name '%s' in %s", name, skill_path)
        return None
    if len(name) > MAX_NAME_LENGTH:
        logger.warning("Skill name too long in %s", skill_path)
        return None
    if not description or len(description) > MAX_DESCRIPTION_LENGTH:
        logger.warning("Invalid description for skill %s", skill_path)
        return None

    if name != skill_path.parent.name:
        logger.warning(
            "Skill name '%s' does not match directory '%s'",
            name,
            skill_path.parent.name,
        )
        return None

    license_value = _coerce_optional_str(data.get("license"))
    compatibility = _coerce_optional_str(data.get("compatibility"))
    if compatibility and len(compatibility) > MAX_COMPATIBILITY_LENGTH:
        logger.warning("Compatibility field too long in %s", skill_path)
        return None

    metadata = _normalize_metadata(data.get("metadata"))
    allowed_tools = _parse_allowed_tools(data.get("allowed-tools"))
    supported_contexts = _parse_supported_contexts(metadata)

    return SkillMetadata(
        name=name,
        description=description,
        root=skill_path.parent,
        skill_path=skill_path,
        license=license_value,
        compatibility=compatibility,
        metadata=metadata,
        allowed_tools=allowed_tools,
        supported_contexts=supported_contexts,
    )


def _extract_frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing frontmatter delimiter")

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter_lines = lines[1:idx]
            if not frontmatter_lines:
                raise ValueError("Empty frontmatter")
            return "\n".join(frontmatter_lines)

    raise ValueError("Closing frontmatter delimiter not found")


def _valid_skill_name(name: str) -> bool:
    if not name:
        return False
    return bool(SKILL_NAME_PATTERN.match(name))


def _coerce_str(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_metadata(value: object | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, entry in value.items():
        if key is None:
            continue
        normalized[str(key)] = "" if entry is None else str(entry)
    return normalized


def _parse_allowed_tools(value: object | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part for part in value.split() if part]
    return []


def _parse_supported_contexts(metadata: dict[str, str]) -> list[str]:
    raw = metadata.get("zoea_contexts") or metadata.get("zoea_context")
    if not raw:
        return ["*"]

    contexts = [
        part.strip().lower()
        for part in re.split(r"[\s,]+", raw)
        if part.strip()
    ]
    return contexts or ["*"]


def _supports_context(skill: SkillMetadata, context: str) -> bool:
    normalized = context.lower()
    return "*" in skill.supported_contexts or normalized in skill.supported_contexts
