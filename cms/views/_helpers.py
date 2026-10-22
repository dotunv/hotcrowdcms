"""Shared helpers for the CMS views."""
import logging

from django.db.models import Max, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.models import (
    Playlist,
    PlaylistItem,
)

logger = logging.getLogger(__name__)


def _user_playlists(user):
    """Playlists with everything needed to compute durations without extra queries."""
    return Playlist.objects.filter(owner=user).prefetch_related(
        Prefetch('items', queryset=PlaylistItem.objects.select_related('media', 'store_content'))
    )


def _sequence_response(request, playlist):
    """Render the playlist sequence partial with fresh totals."""
    playlist = _user_playlists(request.user).get(pk=playlist.pk)
    return render(request, 'cotton/playlist/sequence_editor.html', {
        'playlist': playlist,
        'total_duration': playlist.total_duration,
    })


def _next_position(playlist):
    last = playlist.items.aggregate(m=Max('position'))['m']
    return 0 if last is None else last + 1


def _renumber(playlist):
    """Close gaps / duplicates in item positions so ordering stays stable."""
    for idx, item in enumerate(playlist.items.order_by('position', 'id')):
        if item.position != idx:
            PlaylistItem.objects.filter(pk=item.pk).update(position=idx)


def _pick_playlist(request, playlist_id):
    """The requested playlist, else the user's first one, creating a default if none exist."""
    if playlist_id:
        return get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    playlist = Playlist.objects.filter(owner=request.user).first()
    return playlist or Playlist.objects.create(name="Default", owner=request.user)


def _builder_redirect(playlist):
    return redirect(f"{reverse('playlist_builder')}?playlist={playlist.id}")


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or bool(request.htmx)
