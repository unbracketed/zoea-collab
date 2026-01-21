"""
Nodes for summarize_content workflow.

This workflow reads content from various sources (document, folder, clipboard)
and generates a summary using AI.
"""

from typing import Any

from workflows.base_nodes import AsyncWorkflowNode, WorkflowNode


class ReadContentNode(WorkflowNode):
    """
    Read content from the specified source.

    Retrieves content based on source_type (document, folder, clipboard)
    and source_id, then stores it in the workflow state for subsequent nodes.

    Supported source types:
    - document: Fetches a single document by ID from documents.models.Document
    - folder: Aggregates content from all documents in a folder
    - clipboard: Retrieves clipboard items and their content
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

        # Fetch document with subclass resolution
        doc = Document.objects.select_subclasses().get(id=document_id)

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

        folder = Folder.objects.get(id=folder_id)
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

    def _fetch_clipboard_content(self, clipboard_id: str, ctx) -> dict[str, Any]:
        """
        Fetch content from clipboard items.

        Args:
            clipboard_id: The clipboard ID to fetch items from
            ctx: WorkflowContext for organization scoping

        Returns:
            Dict with 'content' string and 'metadata' dict
        """
        from context_clipboards.models import Clipboard
        from documents.models import TextDocument

        clipboard = Clipboard.objects.get(id=clipboard_id)
        items = clipboard.items.all().order_by("position")

        content_parts = []
        item_count = 0

        for item in items:
            item_count += 1

            # Try to get content from the content_object
            content_obj = item.content_object
            if content_obj is not None:
                if isinstance(content_obj, TextDocument):
                    content_parts.append(
                        f"## Item {item_count}: {content_obj.name}\n\n{content_obj.content}"
                    )
                elif hasattr(content_obj, "name"):
                    content_parts.append(
                        f"## Item {item_count}: {content_obj.name}\n\n"
                        f"[{type(content_obj).__name__} - content not available for summarization]"
                    )
                else:
                    content_parts.append(
                        f"## Item {item_count}\n\n"
                        f"[{type(content_obj).__name__} - content not available for summarization]"
                    )
            elif item.virtual_node is not None:
                # Handle virtual clipboard nodes
                vnode = item.virtual_node
                if vnode.preview_text:
                    content_parts.append(
                        f"## Item {item_count}: {vnode.node_type}\n\n{vnode.preview_text}"
                    )
                elif vnode.payload:
                    # Include payload as JSON-like content
                    import json

                    payload_str = json.dumps(vnode.payload, indent=2)
                    content_parts.append(
                        f"## Item {item_count}: {vnode.node_type}\n\n```json\n{payload_str}\n```"
                    )
                else:
                    content_parts.append(
                        f"## Item {item_count}: {vnode.node_type}\n\n[No content available]"
                    )
            else:
                # Item has no content object or virtual node
                content_parts.append(f"## Item {item_count}\n\n[Empty clipboard item]")

        metadata = {
            "clipboard_id": str(clipboard.id),
            "clipboard_name": clipboard.name,
            "item_count": item_count,
        }

        if not content_parts:
            content_parts.append(f"[No items found in clipboard: {clipboard.name}]")

        return {
            "content": "\n\n---\n\n".join(content_parts),
            "metadata": metadata,
        }

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
        elif source_type == "clipboard":
            result = self._fetch_clipboard_content(source_id, ctx)
        else:
            raise ValueError(
                f"Unsupported source_type: {source_type}. "
                "Must be one of: document, folder, clipboard"
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
