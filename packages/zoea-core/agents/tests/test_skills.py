"""Tests for Agent Skills registry and helpers."""

from django.test import override_settings

from agents.skills import SkillFileError, SkillRegistry


def _write_skill(path, name="pdf-processing", description="Handle PDFs"):
    path.mkdir()
    skill_md = path / "SKILL.md"
    skill_md.write_text(
        """---
name: {name}
description: {description}
---
# Skill
""".format(name=name, description=description)
    )


def test_skill_registry_discovers_valid_skill(tmp_path):
    skill_dir = tmp_path / "pdf-processing"
    _write_skill(skill_dir)

    with override_settings(AGENT_SKILLS_DIRS=[tmp_path]):
        SkillRegistry.reset_instance()
        registry = SkillRegistry.get_instance()
        skills = registry.list_skills()
        prompt = registry.build_available_skills_prompt()
    SkillRegistry.reset_instance()

    assert len(skills) == 1
    assert skills[0].name == "pdf-processing"
    assert "PDF" in skills[0].description
    assert "<available_skills>" in prompt
    assert "<name>pdf-processing</name>" in prompt


def test_skill_registry_skips_invalid_skill(tmp_path):
    skill_dir = tmp_path / "pdf-processing"
    _write_skill(skill_dir, name="pdf_processing")  # invalid name

    with override_settings(AGENT_SKILLS_DIRS=[tmp_path]):
        SkillRegistry.reset_instance()
        registry = SkillRegistry.get_instance()
        skills = registry.list_skills()
    SkillRegistry.reset_instance()

    assert skills == []


def test_skill_registry_read_file_guardrails(tmp_path):
    skill_dir = tmp_path / "pdf-processing"
    _write_skill(skill_dir)

    with override_settings(AGENT_SKILLS_DIRS=[tmp_path]):
        SkillRegistry.reset_instance()
        registry = SkillRegistry.get_instance()

        content = registry.read_skill_file("pdf-processing")
        assert "# Skill" in content

        try:
            registry.read_skill_file("pdf-processing", "../secret.txt")
        except SkillFileError:
            pass
        else:
            raise AssertionError("Expected SkillFileError for path traversal")
    SkillRegistry.reset_instance()
