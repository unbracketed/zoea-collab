"""
Nodes for plan_github_issue workflow.

This workflow reads a GitHub issue and generates an implementation plan
using AI assistance.
"""

from workflows.base_nodes import AsyncWorkflowNode, WorkflowNode


class ReadGithubIssue(WorkflowNode):
    """
    Read issue data from GitHub.

    Retrieves issue details using the PyGithubInterface service
    and stores them in the workflow state for subsequent nodes.
    """

    def prep(self, shared):
        """Get issue number from inputs."""
        ctx = self.ctx(shared)
        return ctx.inputs.issue_number

    def post(self, shared, prep_res, _):
        """Fetch issue data and store in state."""
        ctx = self.ctx(shared)
        gh = ctx.services.gh
        issue_data = gh.read_issue(prep_res)
        ctx.state["issue_data"] = issue_data
        return "default"


class PlanIssue(AsyncWorkflowNode):
    """
    Generate implementation plan using AI.

    Takes the issue data from state and uses the AI service to
    generate a comprehensive implementation plan.
    """

    def _prep(self, shared):
        """Build the prompt from issue data."""
        ctx = self.ctx(shared)
        issue = ctx.state["issue_data"]

        prompt = f"""
You are a senior software architect. Analyze this GitHub issue and create a detailed implementation plan.

## GitHub Issue #{issue['number']}: {issue['title']}

{issue['body']}

**Labels:** {', '.join(issue.get('labels', [])) or 'None'}
**State:** {issue.get('state', 'unknown')}
**URL:** {issue.get('url', 'N/A')}

---

Create a comprehensive implementation plan in Markdown format. Include:

1. **Summary** - Brief overview of what this issue is asking for
2. **Technical Approach** - High-level technical strategy
3. **Files to Modify/Create** - List specific files that need changes
4. **Implementation Steps** - Detailed step-by-step tasks
5. **Testing Strategy** - How to test the implementation
6. **Potential Risks** - Any blockers or concerns

Be specific and actionable. The plan should be detailed enough for a developer to follow.
"""
        return prompt

    async def async_run(self, prompt):
        """Call AI service to generate the plan."""
        ai = self.async_service("ai")
        ai.configure_agent(
            name="ImplementationPlanner",
            instructions=(
                "You are a senior software architect who creates detailed, "
                "actionable implementation plans. Be thorough but concise."
            ),
        )
        return await ai.achat(prompt)

    def post(self, shared, prep_res, run_res):
        """Store the generated plan as output."""
        ctx = self.ctx(shared)

        # Set output with name matching output spec in config
        output_name = f"Issue {ctx.inputs.issue_number} Implementation Spec"
        ctx.outputs.set(output_name, run_res)

        # Also store in state for debugging/inspection
        ctx.state["implementation_spec"] = run_res

        return "default"
