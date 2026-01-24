"""
Nodes for summarize_content workflow.

This workflow reads content from various sources (document, folder)
and generates a summary using AI.
"""

from typing import Any

from workflows.base_nodes import AsyncWorkflowNode, WorkflowNode


class ReadContentNode(WorkflowNode):
    """
    Read content from the specified source.

    Retrieves content based on source_type (document, folder)
    and source_id, then stores it in the workflow state for subsequent nodes.

    Supported source types:
    - document: Fetches a single document by ID from documents.models.Document
    - folder: Aggregates content from all documents in a folder
    """

    def prep(self, shared):
        """Get source parameters from inputs."""
        ctx = self.ctx(shared)
        return {
            "source_type": ctx.inputs.source_type,
            "source_id": ctx.inputs.source_id,
        }

    def _fetch_document_content(self, document_id: str, ctx) -> dict[str, Any]:
        """
        Fetch content from a single document.

        Args:
            document_id: The document ID to fetch
            ctx: WorkflowContext for organization scoping

        Returns:
            Dict with 'content' string and 'metadata' dict
        """
        from documents.models import Document, TextDocument

        scope = self._document_scope(ctx)
        qs = Document.objects.select_subclasses().filter(id=document_id, **scope)
        doc = qs.get()

        content_parts = []
        metadata = {
            "document_id": str(doc.id),
            "document_name": doc.name,
            "document_type": doc.get_type_name(),
        }

        # TextDocument and its subclasses have a content field
        if isinstance(doc, TextDocument):
            content_parts.append(f"## {doc.name}\n\n{doc.content}")
        else:
            # For non-text documents (Image, PDF), include metadata only
            content_parts.append(
                f"## {doc.name}\n\n"
                f"[{doc.get_type_name()} document - content not available for summarization]"
            )

        return {
            "content": "\n\n".join(content_parts),
            "metadata": metadata,
        }

    def _fetch_folder_content(self, folder_id: str, ctx) -> dict[str, Any]:
        """
        Fetch and aggregate content from all documents in a folder.

        Args:
            folder_id: The folder ID to fetch documents from
            ctx: WorkflowContext for organization scoping

        Returns:
            Dict with 'content' string and 'metadata' dict
        """
        from documents.models import Document, Folder, TextDocument

        scope = self._folder_scope(ctx)
        folder = Folder.objects.get(id=folder_id, **scope)
        documents = Document.objects.select_subclasses().filter(folder=folder)

        content_parts = []
        document_names: list[str] = []

        for doc in documents:
            document_names.append(doc.name)
            if isinstance(doc, TextDocument):
                content_parts.append(f"## {doc.name}\n\n{doc.content}")
            else:
                content_parts.append(
                    f"## {doc.name}\n\n"
                    f"[{doc.get_type_name()} document - content not available for summarization]"
                )

        metadata = {
            "folder_id": str(folder.id),
            "folder_name": folder.name,
            "folder_path": folder.get_path(),
            "document_count": len(document_names),
            "document_names": document_names,
        }

        if not content_parts:
            content_parts.append(f"[No documents found in folder: {folder.name}]")

        return {
            "content": "\n\n---\n\n".join(content_parts),
            "metadata": metadata,
        }

    def _document_scope(self, ctx) -> dict[str, Any]:
        scope: dict[str, Any] = {}
        if ctx.organization:
            scope["organization_id"] = ctx.organization.id
        if ctx.project:
            scope["project_id"] = ctx.project.id
        return scope

    def _folder_scope(self, ctx) -> dict[str, Any]:
        scope: dict[str, Any] = {}
        if ctx.organization:
            scope["organization_id"] = ctx.organization.id
        if ctx.project:
            scope["project_id"] = ctx.project.id
        return scope

    def post(self, shared, prep_res, _):
        """Fetch content based on source type and store in state."""
        ctx = self.ctx(shared)
        source_type = prep_res["source_type"]
        source_id = prep_res["source_id"]

        # Store source info in state
        ctx.state["source_type"] = source_type
        ctx.state["source_id"] = source_id

        # Fetch content based on source type
        if source_type == "document":
            result = self._fetch_document_content(source_id, ctx)
        elif source_type == "folder":
            result = self._fetch_folder_content(source_id, ctx)
        else:
            raise ValueError(
                f"Unsupported source_type: {source_type}. "
                "Must be one of: document, folder"
            )

        ctx.state["content"] = result["content"]
        ctx.state["content_metadata"] = result["metadata"]

        return "default"


class SummarizeNode(AsyncWorkflowNode):
    """
    Generate summary using AI.

    Takes the content from state and uses the AI service to
    generate a summary based on the specified style (brief or detailed).

    Prompts are tailored to the summary style:
    - brief: Concise 2-3 paragraph summary focusing on essential information
    - detailed: Comprehensive summary with key points, themes, and details
    """

    # Prompt templates for different summary styles
    BRIEF_INSTRUCTION = (
        "Summarize the following content concisely in 2-3 paragraphs. "
        "Focus on the essential information, main themes, and key takeaways. "
        "Be clear and direct."
    )

    DETAILED_INSTRUCTION = (
        "Provide a comprehensive summary with key points, themes, and details. "
        "Structure your summary with:\n"
        "1. **Overview** - A brief introduction to what the content covers\n"
        "2. **Key Points** - The main ideas and arguments presented\n"
        "3. **Supporting Details** - Important examples, data, or evidence\n"
        "4. **Conclusions** - Any conclusions, recommendations, or next steps mentioned\n\n"
        "Maintain the structure of the original content where appropriate and "
        "include specific examples when relevant."
    )

    def _prep(self, shared):
        """Build the prompt from content and style."""
        ctx = self.ctx(shared)
        content = ctx.state.get("content", "")
        content_metadata = ctx.state.get("content_metadata", {})
        summary_style = ctx.inputs.get("summary_style", "brief")

        # Select instruction based on style
        if summary_style == "detailed":
            style_instruction = self.DETAILED_INSTRUCTION
        else:
            style_instruction = self.BRIEF_INSTRUCTION

        # Build context about the source
        source_context = ""
        if "document_name" in content_metadata:
            source_context = f"Source: Document '{content_metadata['document_name']}'"
        elif "folder_name" in content_metadata:
            doc_count = content_metadata.get("document_count", 0)
            source_context = (
                f"Source: Folder '{content_metadata['folder_name']}' "
                f"containing {doc_count} document(s)"
            )
        elif "clipboard_name" in content_metadata:
            item_count = content_metadata.get("item_count", 0)
            source_context = (
                f"Source: Clipboard '{content_metadata['clipboard_name']}' "
                f"with {item_count} item(s)"
            )

        prompt = f"""You are an expert content summarizer.

## Instructions
{style_instruction}

{f"## Context\n{source_context}\n" if source_context else ""}
## Content to Summarize

{content}

---

Provide the summary in Markdown format."""

        return prompt

    async def async_run(self, prompt):
        """Call AI service to generate the summary."""
        ai = self.async_service("ai")
        ai.configure_agent(
            name="ContentSummarizer",
            instructions=(
                "You are an expert at summarizing content. Create clear, "
                "well-structured summaries that capture the essential information. "
                "Always output in Markdown format."
            ),
        )
        return await ai.achat(prompt)

    def post(self, shared, prep_res, run_res):
        """Store the generated summary as output."""
        ctx = self.ctx(shared)

        # Set output with name matching output spec in config
        source_type = ctx.state.get("source_type", "content")
        output_name = f"{source_type} Summary"
        ctx.outputs.set(output_name, run_res)

        # Also store in state for debugging/inspection
        ctx.state["summary"] = run_res

        return "default"
