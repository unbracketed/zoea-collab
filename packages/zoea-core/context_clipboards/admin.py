"""Admin registrations for the clipboard models."""

from django.contrib import admin

from . import models


@admin.register(models.Clipboard)
class ClipboardAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "workspace",
        "owner",
        "is_active",
        "is_recent",
        "activated_at",
    )
    list_filter = ("is_active", "is_recent", "workspace")
    search_fields = ("name", "description", "owner__email", "workspace__name")
    ordering = ("-activated_at", "-updated_at")


@admin.register(models.ClipboardItem)
class ClipboardItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "clipboard",
        "direction_added",
        "position",
        "is_pinned",
        "created_at",
    )
    list_filter = ("direction_added", "is_pinned")
    search_fields = ("clipboard__name", "source_channel")
    autocomplete_fields = ("clipboard", "added_by")


@admin.register(models.VirtualClipboardNode)
class VirtualClipboardNodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "workspace",
        "node_type",
        "expires_at",
        "created_at",
    )
    list_filter = ("node_type",)
    search_fields = ("node_type", "origin_reference")
    autocomplete_fields = ("workspace", "created_by")
