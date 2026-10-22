"""Dashboard overview."""
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from core.models import (
    MediaAsset,
    Playlist,
    Screen,
)

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Dashboard overview with real-time stats and recent activity."""
    screens = list(Screen.objects.filter(owner=request.user))
    media_assets = MediaAsset.objects.filter(owner=request.user)

    total_screens = len(screens)
    online_screens = sum(1 for s in screens if s.is_online)

    week_ago = timezone.now() - timezone.timedelta(days=7)
    new_screens_this_week = sum(1 for s in screens if s.created_at >= week_ago)

    # Instagram sync status
    instagram_media = media_assets.filter(source='INSTAGRAM').order_by('-created_at').first()
    last_sync_time = None
    if instagram_media:
        seconds = int((timezone.now() - instagram_media.created_at).total_seconds())
        if seconds < 60:
            last_sync_time = f"{seconds}s ago"
        elif seconds < 3600:
            last_sync_time = f"{seconds // 60}m ago"
        elif seconds < 86400:
            last_sync_time = f"{seconds // 3600}h ago"
        else:
            last_sync_time = f"{seconds // 86400}d ago"

    context = {
        'screens': screens,
        'total_screens': total_screens,
        'online_screens': online_screens,
        'offline_screens': total_screens - online_screens,
        'total_playlists': Playlist.objects.filter(owner=request.user).count(),
        'total_media': media_assets.count(),
        'recent_media': media_assets.order_by('-created_at')[:5],
        'playlists': Playlist.objects.filter(owner=request.user),
        'new_screens_this_week': new_screens_this_week,
        'last_sync_time': last_sync_time,
    }

    if request.htmx:
        return render(request, 'partials/dashboard_stats.html', context)

    return render(request, 'dashboard.html', context)
