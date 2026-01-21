"""
Email address utilities for Project and Workspace canonical/alias email generation.

This module provides centralized functions for:
- Generating canonical email addresses for projects and workspaces
- Generating alias email addresses
- Validating email alias formats
- Parsing inbound email addresses to resolve project/workspace/organization
"""

import re
import unicodedata
from typing import NamedTuple

from django.conf import settings
from django.utils.text import slugify


# Default domain for email addresses, configurable via settings
ZOEA_EMAIL_DOMAIN = getattr(settings, 'ZOEA_EMAIL_DOMAIN', 'zoea.studio')

# RFC 5321 limits local part to 64 characters
MAX_LOCAL_PART_LENGTH = 64

# Regex for validating email alias format
# - Must start with a letter
# - Can contain lowercase letters, numbers, hyphens, underscores
# - Min 2 chars, max 64 chars
EMAIL_ALIAS_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{1,63}$')


class ParsedEmail(NamedTuple):
    """Result of parsing an inbound email address."""
    org_slug: str | None
    project_slug: str | None
    workspace_slug: str | None
    is_alias: bool
    local_part: str
    domain: str


def slugify_for_email(name: str) -> str:
    """
    Convert a name to an email-safe slug.

    - Converts to lowercase
    - Replaces spaces and underscores with hyphens
    - Strips accents and special characters
    - Removes consecutive hyphens
    - Strips leading/trailing hyphens

    Args:
        name: The name to slugify (e.g., "Zoea Dev" or "Team Zoea")

    Returns:
        Email-safe slug (e.g., "zoea-dev" or "team-zoea")
    """
    # Normalize unicode characters (convert accents to base letters)
    normalized = unicodedata.normalize('NFKD', name)
    # Remove non-ASCII characters after normalization
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    # Use Django's slugify for the rest
    slug = slugify(ascii_name)
    # Ensure we have something - fall back to 'unnamed' if empty
    return slug if slug else 'unnamed'


def generate_project_canonical_email(project_slug: str, org_slug: str) -> str:
    """
    Generate the canonical email address for a project.

    Format: {project-slug}.{org-slug}@{domain}
    Example: zoea-dev.team-zoea@zoea.studio

    Args:
        project_slug: The project's slug
        org_slug: The organization's slug

    Returns:
        Full canonical email address
    """
    local_part = f"{project_slug}.{org_slug}"
    # Truncate if exceeding RFC limit (should be rare)
    if len(local_part) > MAX_LOCAL_PART_LENGTH:
        # Keep org_slug intact, truncate project_slug
        max_project_len = MAX_LOCAL_PART_LENGTH - len(org_slug) - 1  # -1 for dot
        local_part = f"{project_slug[:max_project_len]}.{org_slug}"
    return f"{local_part}@{ZOEA_EMAIL_DOMAIN}"


def generate_workspace_canonical_email(
    workspace_slug: str,
    project_slug: str,
    org_slug: str
) -> str:
    """
    Generate the canonical email address for a workspace.

    Format: {workspace-slug}.{project-slug}.{org-slug}@{domain}
    Example: research.zoea-dev.team-zoea@zoea.studio

    Args:
        workspace_slug: The workspace's slug
        project_slug: The parent project's slug
        org_slug: The organization's slug

    Returns:
        Full canonical email address
    """
    local_part = f"{workspace_slug}.{project_slug}.{org_slug}"
    # Truncate if exceeding RFC limit
    if len(local_part) > MAX_LOCAL_PART_LENGTH:
        # Keep org_slug and project_slug, truncate workspace_slug
        suffix = f".{project_slug}.{org_slug}"
        max_ws_len = MAX_LOCAL_PART_LENGTH - len(suffix)
        if max_ws_len > 0:
            local_part = f"{workspace_slug[:max_ws_len]}{suffix}"
        else:
            # Extreme case: truncate project slug too
            local_part = local_part[:MAX_LOCAL_PART_LENGTH]
    return f"{local_part}@{ZOEA_EMAIL_DOMAIN}"


def generate_alias_email(alias: str, org_slug: str) -> str:
    """
    Generate a full email address from an alias.

    Format: {alias}.{org-slug}@{domain}
    Example: bob.team-zoea@zoea.studio

    Args:
        alias: The email alias (local part before org slug)
        org_slug: The organization's slug

    Returns:
        Full alias email address
    """
    return f"{alias}.{org_slug}@{ZOEA_EMAIL_DOMAIN}"


def validate_email_alias(alias: str) -> bool:
    """
    Validate that an email alias follows the required format.

    Rules:
    - Must start with a lowercase letter
    - Can contain lowercase letters, numbers, hyphens, underscores
    - Must be 2-64 characters long

    Args:
        alias: The alias to validate

    Returns:
        True if valid, False otherwise
    """
    if not alias:
        return False
    return bool(EMAIL_ALIAS_PATTERN.match(alias))


def parse_inbound_email(email_address: str) -> ParsedEmail:
    """
    Parse an inbound email address to extract organization, project, and workspace slugs.

    This function determines if the email is a canonical address or an alias:

    Canonical formats:
    - Project: {project-slug}.{org-slug}@domain (2 parts)
    - Workspace: {workspace-slug}.{project-slug}.{org-slug}@domain (3 parts)

    Alias format:
    - {alias}.{org-slug}@domain (2 parts, same as project canonical)

    Note: Cannot distinguish between project canonical and alias just by parsing.
    Caller must check database to determine which it is.

    Args:
        email_address: Full email address to parse

    Returns:
        ParsedEmail with extracted slugs. For 2-part addresses, project_slug
        contains the first part (could be project slug or alias).
    """
    # Validate email format
    if '@' not in email_address:
        return ParsedEmail(
            org_slug=None,
            project_slug=None,
            workspace_slug=None,
            is_alias=False,
            local_part='',
            domain=''
        )

    local_part, domain = email_address.lower().rsplit('@', 1)

    # Split local part by dots
    parts = local_part.split('.')

    if len(parts) == 2:
        # Could be project canonical OR alias - caller must check DB
        # Format: {project-or-alias}.{org-slug}
        return ParsedEmail(
            org_slug=parts[1],
            project_slug=parts[0],  # Could be project slug or alias
            workspace_slug=None,
            is_alias=False,  # Unknown at parse time
            local_part=local_part,
            domain=domain
        )
    elif len(parts) == 3:
        # Workspace canonical: {workspace}.{project}.{org}
        return ParsedEmail(
            org_slug=parts[2],
            project_slug=parts[1],
            workspace_slug=parts[0],
            is_alias=False,
            local_part=local_part,
            domain=domain
        )
    elif len(parts) == 1:
        # Just org slug (unlikely but handle it)
        return ParsedEmail(
            org_slug=parts[0],
            project_slug=None,
            workspace_slug=None,
            is_alias=False,
            local_part=local_part,
            domain=domain
        )
    else:
        # More than 3 parts - malformed or future format
        # Assume last is org, second-to-last is project, rest is workspace
        return ParsedEmail(
            org_slug=parts[-1],
            project_slug=parts[-2],
            workspace_slug='.'.join(parts[:-2]),
            is_alias=False,
            local_part=local_part,
            domain=domain
        )


def get_email_domain() -> str:
    """
    Get the configured email domain.

    Returns:
        The email domain (default: zoea.studio)
    """
    return ZOEA_EMAIL_DOMAIN


class ResolvedRecipient(NamedTuple):
    """Result of resolving an email recipient to project/workspace."""
    project: object | None  # Project model instance
    workspace: object | None  # Workspace model instance
    organization: object | None  # Organization model instance
    resolved_via: str  # How it was resolved: 'project_canonical', 'workspace_canonical', 'project_alias', 'workspace_alias', or 'not_found'


def resolve_email_recipient(email_address: str) -> ResolvedRecipient:
    """
    Resolve an inbound email address to a Project and/or Workspace.

    This function looks up the recipient email address against:
    1. Project canonical emails
    2. Workspace canonical emails
    3. Project alias emails
    4. Workspace alias emails

    Args:
        email_address: The recipient email address to resolve

    Returns:
        ResolvedRecipient with the resolved project, workspace, and organization.
        If not found, all fields will be None and resolved_via will be 'not_found'.
    """
    # Import here to avoid circular imports
    from projects.models import Project
    from workspaces.models import Workspace

    email_lower = email_address.lower()

    # 1. Try project canonical email (exact match)
    project = Project.objects.filter(canonical_email__iexact=email_lower).first()
    if project:
        return ResolvedRecipient(
            project=project,
            workspace=None,
            organization=project.organization,
            resolved_via='project_canonical'
        )

    # 2. Try workspace canonical email (exact match)
    workspace = Workspace.objects.select_related('project', 'project__organization').filter(
        canonical_email__iexact=email_lower
    ).first()
    if workspace:
        return ResolvedRecipient(
            project=workspace.project,
            workspace=workspace,
            organization=workspace.project.organization,
            resolved_via='workspace_canonical'
        )

    # 3. Parse the email to check for alias format
    parsed = parse_inbound_email(email_address)
    if not parsed.org_slug:
        return ResolvedRecipient(
            project=None,
            workspace=None,
            organization=None,
            resolved_via='not_found'
        )

    # For 2-part addresses, check if first part is a project alias
    if parsed.project_slug and not parsed.workspace_slug:
        # Try project alias lookup
        project = Project.objects.filter(
            organization__slug__iexact=parsed.org_slug,
            email_alias__iexact=parsed.project_slug
        ).select_related('organization').first()
        if project:
            return ResolvedRecipient(
                project=project,
                workspace=None,
                organization=project.organization,
                resolved_via='project_alias'
            )

        # Try workspace alias lookup (workspace aliases also use 2-part format)
        workspace = Workspace.objects.filter(
            project__organization__slug__iexact=parsed.org_slug,
            email_alias__iexact=parsed.project_slug
        ).select_related('project', 'project__organization').first()
        if workspace:
            return ResolvedRecipient(
                project=workspace.project,
                workspace=workspace,
                organization=workspace.project.organization,
                resolved_via='workspace_alias'
            )

    # Not found
    return ResolvedRecipient(
        project=None,
        workspace=None,
        organization=None,
        resolved_via='not_found'
    )
