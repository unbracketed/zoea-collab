"""
Management command to clean up expired RAG sessions.

Usage:
    python manage.py cleanup_rag_sessions
    python manage.py cleanup_rag_sessions --dry-run

Can be scheduled via cron:
    */15 * * * * cd /path/to/backend && uv run python manage.py cleanup_rag_sessions
"""

import asyncio

from django.core.management.base import BaseCommand

from document_rag.session_manager import RAGSessionManager


class Command(BaseCommand):
    help = "Clean up expired RAG sessions and their Gemini stores"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned up without actually deleting",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            count = asyncio.run(self._count_expired())
            self.stdout.write(f"Would clean up {count} expired session(s)")
        else:
            count = asyncio.run(self._cleanup())
            self.stdout.write(self.style.SUCCESS(f"Cleaned up {count} expired session(s)"))

    async def _cleanup(self) -> int:
        manager = RAGSessionManager()
        return await manager.cleanup_expired_sessions()

    async def _count_expired(self) -> int:
        from django.utils import timezone

        from document_rag.models import RAGSession

        return await RAGSession.objects.filter(
            status__in=[RAGSession.Status.ACTIVE, RAGSession.Status.INITIALIZING],
            expires_at__lt=timezone.now(),
        ).acount()
