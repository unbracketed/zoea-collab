"""
Agent Skill Loader tool.

Allows the agent to load SKILL.md instructions or referenced files from
registered Agent Skills directories.
"""

import logging

from smolagents import Tool

from agents.skills import SkillFileError, SkillNotFoundError, SkillRegistry

logger = logging.getLogger(__name__)


class SkillLoaderTool(Tool):
    """
    Load Agent Skills instructions and resources.

    Use this tool to retrieve SKILL.md or related files from a skill directory.
    """

    name = "load_skill"
    description = (
        "Load Agent Skills instructions or files from a skill directory. "
        "Use this to read SKILL.md or referenced files when a skill is relevant."
    )

    inputs = {
        "name": {
            "type": "string",
            "description": "Skill name to load (matches the skill directory)",
        },
        "path": {
            "type": "string",
            "description": "Relative file path inside the skill (default: SKILL.md)",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, name: str, path: str | None = None) -> str:
        registry = SkillRegistry.get_instance()
        requested_path = path or "SKILL.md"

        try:
            content = registry.read_skill_file(name, requested_path)
        except SkillNotFoundError:
            return f"Skill '{name}' was not found."
        except SkillFileError as exc:
            return f"Unable to load skill file '{name}/{requested_path}': {exc}"
        except Exception as exc:  # pragma: no cover - unexpected errors
            logger.exception("Unexpected skill loader error")
            return f"Unexpected error loading skill '{name}': {exc}"

        header = f"Skill file: {name}/{requested_path}"
        return f"{header}\n\n{content}"
