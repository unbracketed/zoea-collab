from django.contrib import admin

from .models import Channel, ChannelMessage


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "adapter_type", "display_name", "external_id", "organization")
    list_filter = ("adapter_type", "organization")
    search_fields = ("display_name", "external_id")


@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "role", "sender_name", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "sender_name", "sender_id")
