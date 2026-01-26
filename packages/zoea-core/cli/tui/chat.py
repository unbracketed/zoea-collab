"""Textual TUI chat interface for project conversations."""

import asyncio
from datetime import datetime

from django.apps import apps
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from chat.agent_service import ChatAgentService


class MessageWidget(Static):
    """A single message in the chat view."""

    def __init__(
        self,
        content: str,
        role: str = "user",
        timestamp: datetime | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.msg_content = content
        self.role = role
        self.timestamp = timestamp or datetime.now()

    def compose(self) -> ComposeResult:
        yield Static(self._render())

    def _render(self) -> str:
        """Render the message with role indicator."""
        time_str = self.timestamp.strftime("%H:%M")
        if self.role == "user":
            return f"[bold green]You[/] [dim]{time_str}[/]\n{self.msg_content}"
        elif self.role == "assistant":
            return f"[bold cyan]Assistant[/] [dim]{time_str}[/]\n{self.msg_content}"
        else:
            return f"[bold yellow]System[/] [dim]{time_str}[/]\n{self.msg_content}"

    def update_content(self, content: str) -> None:
        """Update the message content (for streaming)."""
        self.msg_content = content
        self.query_one(Static).update(self._render())


class StreamingMessage(Static):
    """A message widget that supports streaming updates."""

    DEFAULT_CSS = """
    StreamingMessage {
        padding: 0 1;
        margin: 1 0;
        background: $surface;
    }
    """

    def __init__(self, role: str = "assistant", **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = ""
        self.timestamp = datetime.now()

    def on_mount(self) -> None:
        """Initialize with empty content."""
        self.update(self._render())

    def _render(self) -> str:
        """Render the message with role indicator."""
        time_str = self.timestamp.strftime("%H:%M")
        display_content = self.content or "[dim]...[/]"
        if self.role == "assistant":
            return f"[bold cyan]Assistant[/] [dim]{time_str}[/]\n{display_content}"
        return f"[bold yellow]{self.role.title()}[/] [dim]{time_str}[/]\n{display_content}"

    def append_content(self, chunk: str) -> None:
        """Append a chunk to the message content."""
        self.content += chunk
        self.update(self._render())

    def get_content(self) -> str:
        """Get the full message content."""
        return self.content


class ProjectChatApp(App):
    """Terminal-based chat interface for a project."""

    TITLE = "Zoea Project Chat"
    SUB_TITLE = "Press Ctrl+C to exit"

    CSS = """
    #chat-container {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        scrollbar-gutter: stable;
    }

    .user-message {
        background: $primary 20%;
        margin: 1 0;
        padding: 0 1;
    }

    .assistant-message {
        background: $secondary 20%;
        margin: 1 0;
        padding: 0 1;
    }

    .system-message {
        background: $warning 20%;
        margin: 1 0;
        padding: 0 1;
    }

    #message-input {
        dock: bottom;
        margin: 1 0 0 0;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Exit"),
        ("ctrl+n", "new_conversation", "New Chat"),
    ]

    def __init__(
        self,
        project_id: int,
        project_name: str,
        conversation_id: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_id = project_id
        self.project_name = project_name
        self.conversation_id = conversation_id
        self.conversation = None
        self.chat_service = None
        self.is_processing = False
        self.conversation_messages: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="chat-container")
        yield Static("", id="status-bar")
        yield Input(placeholder="Type your message and press Enter...", id="message-input")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the chat service and load conversation."""
        self.title = f"Chat: {self.project_name}"

        # Get Django models
        Project = apps.get_model("projects", "Project")
        Conversation = apps.get_model("chat", "Conversation")

        # Load project with related organization (to avoid lazy load in async)
        try:
            project = await asyncio.to_thread(
                lambda: Project.objects.select_related("organization").get(id=self.project_id)
            )
        except Project.DoesNotExist:
            self._update_status("[red]Error: Project not found[/]")
            return

        # Store organization_id for later use (avoid lazy load issues)
        self._organization_id = project.organization_id

        # Initialize chat service with project config
        self.chat_service = ChatAgentService(project=project)

        # Load or create conversation
        if self.conversation_id:
            try:
                self.conversation = await asyncio.to_thread(
                    Conversation.objects.select_related("organization", "project").get,
                    id=self.conversation_id,
                )
                # Load existing messages
                messages = await asyncio.to_thread(
                    lambda: list(self.conversation.messages.all().order_by("created_at"))
                )
                for msg in messages:
                    self._add_message_widget(msg.content, msg.role, msg.created_at)
                    if msg.role in ("user", "assistant"):
                        self.conversation_messages.append(
                            {"role": msg.role, "content": msg.content}
                        )
            except Conversation.DoesNotExist:
                self.conversation_id = None

        if not self.conversation_id:
            # Create new conversation
            User = apps.get_model("auth", "User")
            user = await asyncio.to_thread(User.objects.first)

            # Use organization_id to avoid lazy load
            org_id = self._organization_id
            project_id = self.project_id
            agent_name = self.chat_service.agent_name

            self.conversation = await asyncio.to_thread(
                lambda: Conversation.objects.create(
                    organization_id=org_id,
                    project_id=project_id,
                    created_by=user,
                    agent_name=agent_name,
                )
            )
            self.conversation_id = self.conversation.id

            # Add welcome message
            welcome = f"Starting new conversation for project '{self.project_name}'."
            self._add_message_widget(welcome, "system")

        self._update_status(
            f"[green]Connected[/] | Model: {self.chat_service.model_used} | "
            f"Provider: {self.chat_service.provider_name}"
        )

        # Focus the input
        self.query_one("#message-input", Input).focus()

    def _update_status(self, message: str) -> None:
        """Update the status bar."""
        self.query_one("#status-bar", Static).update(message)

    def _add_message_widget(
        self,
        content: str,
        role: str,
        timestamp: datetime | None = None,
    ) -> Static:
        """Add a message widget to the chat view."""
        chat_view = self.query_one("#chat-container", VerticalScroll)

        css_class = f"{role}-message"
        time_str = (timestamp or datetime.now()).strftime("%H:%M")

        if role == "user":
            rendered = f"[bold green]You[/] [dim]{time_str}[/]\n{content}"
        elif role == "assistant":
            rendered = f"[bold cyan]Assistant[/] [dim]{time_str}[/]\n{content}"
        else:
            rendered = f"[bold yellow]System[/] [dim]{time_str}[/]\n{content}"

        widget = Static(rendered, classes=css_class)
        chat_view.mount(widget)
        widget.scroll_visible()
        return widget

    def _add_streaming_message(self) -> StreamingMessage:
        """Add a streaming message widget for the assistant response."""
        chat_view = self.query_one("#chat-container", VerticalScroll)
        widget = StreamingMessage(role="assistant", classes="assistant-message")
        chat_view.mount(widget)
        widget.scroll_visible()
        return widget

    @on(Input.Submitted, "#message-input")
    async def handle_submit(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if not event.value.strip() or self.is_processing:
            return

        user_message = event.value.strip()
        event.input.value = ""

        # Add user message to UI
        self._add_message_widget(user_message, "user")

        # Save user message to database
        await self._save_message(user_message, "user")

        # Add to conversation history
        self.conversation_messages.append({"role": "user", "content": user_message})

        # Get AI response
        self._get_response(user_message)

    @work(exclusive=True)
    async def _get_response(self, user_message: str) -> None:
        """Get streaming response from the AI."""
        self.is_processing = True
        self._update_status("[yellow]Thinking...[/]")

        # Disable input while processing
        input_widget = self.query_one("#message-input", Input)
        input_widget.disabled = True

        try:
            # Create streaming message widget
            streaming_widget = self._add_streaming_message()

            # Stream the response
            full_response = ""
            async for chunk in self.chat_service.chat_stream(
                user_message,
                conversation_messages=self.conversation_messages[:-1],  # Exclude current message
            ):
                full_response += chunk
                streaming_widget.append_content(chunk)
                streaming_widget.scroll_visible()

            # Save assistant message to database
            await self._save_message(
                full_response,
                "assistant",
                model_used=self.chat_service.model_used,
            )

            # Add to conversation history
            self.conversation_messages.append({"role": "assistant", "content": full_response})

            self._update_status(
                f"[green]Ready[/] | Model: {self.chat_service.model_used} | "
                f"Provider: {self.chat_service.provider_name}"
            )

        except Exception as e:
            error_msg = f"Error: {e}"
            self._add_message_widget(error_msg, "system")
            self._update_status(f"[red]Error[/] | {e}")

        finally:
            self.is_processing = False
            input_widget.disabled = False
            input_widget.focus()

    async def _save_message(
        self,
        content: str,
        role: str,
        model_used: str = "",
    ) -> None:
        """Save a message to the database."""
        Message = apps.get_model("chat", "Message")

        await asyncio.to_thread(
            Message.objects.create,
            conversation=self.conversation,
            role=role,
            content=content,
            model_used=model_used,
        )

    def action_new_conversation(self) -> None:
        """Start a new conversation."""
        # Reset conversation state
        self.conversation_id = None
        self.conversation = None
        self.conversation_messages = []

        # Clear chat view
        chat_view = self.query_one("#chat-container", VerticalScroll)
        chat_view.remove_children()

        # Reinitialize
        self.run_worker(self._create_new_conversation())

    async def _create_new_conversation(self) -> None:
        """Create a new conversation."""
        Conversation = apps.get_model("chat", "Conversation")
        User = apps.get_model("auth", "User")

        user = await asyncio.to_thread(User.objects.first)

        # Use stored IDs to avoid lazy load issues
        org_id = self._organization_id
        project_id = self.project_id
        agent_name = self.chat_service.agent_name

        self.conversation = await asyncio.to_thread(
            lambda: Conversation.objects.create(
                organization_id=org_id,
                project_id=project_id,
                created_by=user,
                agent_name=agent_name,
            )
        )
        self.conversation_id = self.conversation.id

        welcome = f"Starting new conversation for project '{self.project_name}'."
        self._add_message_widget(welcome, "system")

        self._update_status(
            f"[green]New conversation[/] | Model: {self.chat_service.model_used} | "
            f"Provider: {self.chat_service.provider_name}"
        )
