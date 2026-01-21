"""
GitHub API service for workflow nodes.

Provides access to GitHub repositories, issues, and other resources
via the PyGithub library.
"""

import logging
import os
from typing import Any, Dict, Optional

from github import Auth, Github

logger = logging.getLogger(__name__)


class PyGithubInterface:
    """
    GitHub API service for workflow nodes.

    Can be configured with a specific repository via constructor or
    defaults to environment variable.

    Example config in flow-config.yaml:
        SERVICES:
          - name: PyGithubInterface
            ctxref: gh
            config:
              repo: owner/repository
    """

    def __init__(
        self,
        repo: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """
        Initialize GitHub interface.

        Args:
            repo: Repository in "owner/name" format. Falls back to GITHUB_REPO env var.
            token: GitHub access token. Falls back to ZOEA_STUDIO_GITHUB_API_TOKEN env var.
        """
        self._token = token or os.environ.get("ZOEA_STUDIO_GITHUB_API_TOKEN")
        if not self._token:
            raise ValueError(
                "GitHub token required. Set ZOEA_STUDIO_GITHUB_API_TOKEN environment variable "
                "or pass token parameter."
            )

        self._repo_name = repo or os.environ.get("GITHUB_REPO")
        if not self._repo_name:
            raise ValueError(
                "GitHub repository required. Pass repo parameter in config "
                "or set GITHUB_REPO environment variable."
            )

        auth = Auth.Token(self._token)
        self._gh = Github(auth=auth)
        self._repo = None

        logger.debug(f"Initialized PyGithubInterface for repo: {self._repo_name}")

    @property
    def repo(self):
        """Lazily load the repository object."""
        if self._repo is None:
            self._repo = self._gh.get_repo(self._repo_name)
        return self._repo

    def read_issue(self, issue_number: int) -> Dict[str, Any]:
        """
        Read issue data from GitHub.

        Args:
            issue_number: The issue number to read

        Returns:
            Dictionary with issue data including:
            - number, title, body, state
            - labels, assignees
            - created_at, updated_at
            - comments_count
        """
        issue = self.repo.get_issue(number=issue_number)

        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body or "",
            "state": issue.state,
            "labels": [label.name for label in issue.labels],
            "assignees": [assignee.login for assignee in issue.assignees],
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
            "comments_count": issue.comments,
            "url": issue.html_url,
        }

    def list_issues(
        self,
        state: str = "open",
        labels: Optional[list[str]] = None,
        limit: int = 30,
    ) -> list[Dict[str, Any]]:
        """
        List issues from the repository.

        Args:
            state: Issue state filter ("open", "closed", "all")
            labels: Optional list of label names to filter by
            limit: Maximum number of issues to return

        Returns:
            List of issue dictionaries
        """
        kwargs = {"state": state}
        if labels:
            kwargs["labels"] = labels

        issues = self.repo.get_issues(**kwargs)
        result = []

        for issue in issues[:limit]:
            result.append(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "labels": [label.name for label in issue.labels],
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "url": issue.html_url,
                }
            )

        return result
