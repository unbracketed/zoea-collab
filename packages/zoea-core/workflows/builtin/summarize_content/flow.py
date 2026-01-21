"""
Flow definition for summarize_content workflow.

Builds a PocketFlow that reads content from various sources
and generates a summary using AI.
"""

from pocketflow import Flow

from workflows.builtin.summarize_content.nodes import ReadContentNode, SummarizeNode


def build_flow():
    """
    Build the summarize_content workflow flow.

    Flow:
        ReadContentNode -> SummarizeNode

    The flow reads content from the specified source (document, folder, or clipboard)
    and then generates a summary using AI based on the selected summary style.

    Returns:
        Flow instance ready to run
    """
    read_content = ReadContentNode()
    summarize = SummarizeNode()

    # Chain nodes: read content from source, then generate summary
    read_content >> summarize

    return Flow(start=read_content)
