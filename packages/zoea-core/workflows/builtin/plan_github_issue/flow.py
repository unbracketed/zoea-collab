"""
Flow definition for plan_github_issue workflow.

Builds a PocketFlow that reads a GitHub issue and generates
an implementation plan using AI.
"""

from pocketflow import Flow

from workflows.builtin.plan_github_issue.nodes import PlanIssue, ReadGithubIssue


def build_flow():
    """
    Build the plan_github_issue workflow flow.

    Flow:
        ReadGithubIssue -> PlanIssue

    Returns:
        Flow instance ready to run
    """
    read_issue = ReadGithubIssue()
    plan_issue = PlanIssue()

    # Chain nodes: read issue data, then generate plan
    read_issue >> plan_issue

    return Flow(start=read_issue)
