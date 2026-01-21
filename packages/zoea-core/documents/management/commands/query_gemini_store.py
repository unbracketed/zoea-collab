"""
Django management command to query Gemini File Search stores.

This command allows testing semantic search and RAG capabilities by querying
a project's File Search store with natural language questions.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from organizations.models import Organization

from documents.gemini_service import GeminiFileSearchService
from projects.models import Project


class Command(BaseCommand):
    help = (
        'Query a Gemini File Search store with a question. '
        'Uses semantic search and RAG to answer based on project documents.'
    )

    def add_arguments(self, parser):
        # Store identification
        parser.add_argument(
            '--project',
            type=str,
            help='Query File Search store for this project (by name or ID)'
        )
        parser.add_argument(
            '--store-id',
            type=str,
            help='Query specific File Search store by ID (e.g., fileSearchStores/abc123)'
        )

        # Query
        parser.add_argument(
            'query',
            type=str,
            help='The question or query to search for'
        )

        # Model configuration
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            help='Gemini model to use (default: from settings)'
        )

        # Filtering
        parser.add_argument(
            '--metadata-filter',
            type=str,
            help='Metadata filter expression (e.g., "document_type=Markdown")'
        )

        # Output options
        parser.add_argument(
            '--show-citations',
            action='store_true',
            help='Show detailed citation information from grounding metadata'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show verbose output including full grounding metadata'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Gemini File Search Query'))
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # Initialize service
        try:
            service = GeminiFileSearchService()
        except ValueError as e:
            raise CommandError(str(e))

        # Get store ID
        store_id = self.get_store_id(options)

        # Display query info
        self.stdout.write(self.style.HTTP_INFO('Query Configuration:'))
        self.stdout.write(f"  Store ID: {store_id}")
        self.stdout.write(f"  Query: {options['query']}")

        if options['metadata_filter']:
            self.stdout.write(f"  Metadata Filter: {options['metadata_filter']}")

        model_id = options['model'] or settings.GEMINI_MODEL_ID
        self.stdout.write(f"  Model: {model_id}")
        self.stdout.write('')
        self.stdout.write('-' * 70)
        self.stdout.write('')

        # Execute query
        try:
            result = self.query_store(
                service,
                store_id,
                options['query'],
                model_id=model_id,
                metadata_filter=options.get('metadata_filter')
            )
        except Exception as e:
            raise CommandError(f"Query failed: {e}")

        # Display results
        self.display_response(result, options)

    def get_store_id(self, options):
        """Get File Search store ID from options."""
        if options['store_id']:
            return options['store_id']
        elif options['project']:
            # Find project and get its store ID
            try:
                # Try by ID first
                if options['project'].isdigit():
                    project = Project.objects.get(id=int(options['project']))
                else:
                    # Try by name
                    project = Project.objects.get(name=options['project'])

                if not project.gemini_store_id:
                    raise CommandError(
                        f"Project '{project.name}' does not have a File Search store. "
                        f"Run 'sync_gemini_file_search --project \"{project.name}\"' first."
                    )

                self.stdout.write(
                    f"  Project: {self.style.SUCCESS(project.name)} "
                    f"({project.organization.name})"
                )

                return project.gemini_store_id

            except Project.DoesNotExist:
                raise CommandError(f"Project '{options['project']}' not found")
        else:
            raise CommandError(
                "Either --project or --store-id must be specified"
            )

    def query_store(self, service, store_id, query, model_id, metadata_filter=None):
        """
        Query a File Search store using Gemini.

        Args:
            service: GeminiFileSearchService instance
            store_id: File Search store ID
            query: Query string
            model_id: Gemini model ID
            metadata_filter: Optional metadata filter expression

        Returns:
            Response object from Gemini
        """
        from google import genai
        from google.genai import types

        # Build File Search configuration
        file_search_config = {
            'file_search_store_names': [store_id]
        }

        if metadata_filter:
            file_search_config['metadata_filter'] = metadata_filter

        # Generate content with File Search tool
        response = service.client.models.generate_content(
            model=model_id,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(**file_search_config)
                    )
                ]
            )
        )

        return response

    def display_response(self, response, options):
        """Display the query response."""
        # Main response text
        self.stdout.write(self.style.HTTP_INFO('Response:'))
        self.stdout.write('')

        if hasattr(response, 'text') and response.text:
            # Word wrap the response for better readability
            import textwrap
            wrapped_text = textwrap.fill(
                response.text,
                width=68,
                initial_indent='  ',
                subsequent_indent='  '
            )
            self.stdout.write(wrapped_text)
        else:
            self.stdout.write(self.style.WARNING('  No text response generated'))

        self.stdout.write('')
        self.stdout.write('-' * 70)
        self.stdout.write('')

        # Show citations if requested
        if options['show_citations'] or options['verbose']:
            self.display_citations(response)

        # Show verbose metadata if requested
        if options['verbose']:
            self.display_grounding_metadata(response)

    def display_citations(self, response):
        """Display citation information from grounding metadata."""
        self.stdout.write(self.style.HTTP_INFO('Citations:'))
        self.stdout.write('')

        if not hasattr(response, 'candidates') or not response.candidates:
            self.stdout.write(self.style.WARNING('  No candidates in response'))
            return

        candidate = response.candidates[0]

        if not hasattr(candidate, 'grounding_metadata') or not candidate.grounding_metadata:
            self.stdout.write(self.style.WARNING('  No grounding metadata available'))
            return

        grounding = candidate.grounding_metadata

        # Display grounding chunks (document references)
        if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
            self.stdout.write(f"  Found {len(grounding.grounding_chunks)} source(s):")
            self.stdout.write('')

            for idx, chunk in enumerate(grounding.grounding_chunks, 1):
                self.stdout.write(f"  [{idx}] Source:")

                # Display retrieved context
                if hasattr(chunk, 'retrieved_context') and chunk.retrieved_context:
                    context = chunk.retrieved_context

                    # Title or file name
                    if hasattr(context, 'title') and context.title:
                        self.stdout.write(f"      Title: {context.title}")

                    # URI if available
                    if hasattr(context, 'uri') and context.uri:
                        self.stdout.write(f"      URI: {context.uri}")

                    # Text snippet
                    if hasattr(context, 'text') and context.text:
                        import textwrap
                        snippet = context.text[:200] + ('...' if len(context.text) > 200 else '')
                        wrapped = textwrap.fill(
                            snippet,
                            width=62,
                            initial_indent='      Snippet: ',
                            subsequent_indent='               '
                        )
                        self.stdout.write(wrapped)

                self.stdout.write('')

        # Display grounding support info
        if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
            self.stdout.write(f"  Grounding supports: {len(grounding.grounding_supports)}")
            for support in grounding.grounding_supports[:3]:  # Show first 3
                if hasattr(support, 'segment'):
                    segment = support.segment
                    if hasattr(segment, 'text'):
                        self.stdout.write(f"    - {segment.text[:100]}...")

        self.stdout.write('')
        self.stdout.write('-' * 70)
        self.stdout.write('')

    def display_grounding_metadata(self, response):
        """Display full grounding metadata in verbose mode."""
        self.stdout.write(self.style.HTTP_INFO('Grounding Metadata (Verbose):'))
        self.stdout.write('')

        if not hasattr(response, 'candidates') or not response.candidates:
            self.stdout.write(self.style.WARNING('  No candidates in response'))
            return

        candidate = response.candidates[0]

        if hasattr(candidate, 'grounding_metadata'):
            import json
            # Convert to dict for display
            try:
                # Try to access as dict or convert to JSON
                metadata_str = str(candidate.grounding_metadata)
                self.stdout.write(f"  {metadata_str}")
            except Exception as e:
                self.stdout.write(f"  Could not display metadata: {e}")

        self.stdout.write('')
        self.stdout.write('=' * 70)
