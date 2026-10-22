from django.contrib import admin

from .models import (
    MediaAsset,
    PairingCode,
    Playlist,
    PlaylistItem,
    Screen,
    Store,
    StoreContent,
    StoreLayout,
    SupportTicket,
)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'topic', 'urgency', 'status')
    list_filter = ('status', 'urgency', 'topic')
    search_fields = ('user__username', 'user__email', 'description')
    list_editable = ('status',)
    readonly_fields = ('id', 'user', 'created_at')


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'last_heartbeat', 'assigned_playlist')
    list_filter = ('status',)
    search_fields = ('name', 'owner__username')
    exclude = ('api_token',)  # only a hash is stored; never expose it
    readonly_fields = ('id', 'created_at', 'last_heartbeat')


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'schedule_type', 'updated_at')
    list_filter = ('status', 'schedule_type')
    search_fields = ('name', 'owner__username')


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'media_type', 'source', 'created_at')
    list_filter = ('media_type', 'source')
    search_fields = ('name', 'owner__username', 'file_url')


admin.site.register(Store)
admin.site.register(PlaylistItem)
admin.site.register(PairingCode)
admin.site.register(StoreLayout)
admin.site.register(StoreContent)
