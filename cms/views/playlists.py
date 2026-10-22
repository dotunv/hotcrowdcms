"""Playlists and playlist items."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_time

from core.models import (
    MediaAsset,
    Playlist,
    PlaylistItem,
    Screen,
    Store,
    StoreContent,
)

from ..utils import (
    is_valid_http_url,
    parse_int,
    parse_uuid,
)
from ._helpers import (
    _builder_redirect,
    _next_position,
    _pick_playlist,
    _renumber,
    _sequence_response,
    _user_playlists,
)

logger = logging.getLogger(__name__)


def _assign_screens(request, playlist):
    """Make `playlist` the assigned playlist of exactly the selected (owned) screens."""
    selected = [sid for sid in request.POST.getlist('assigned_screens') if parse_uuid(sid)]
    owned = Screen.objects.filter(owner=request.user)
    owned.filter(assigned_playlist=playlist).exclude(id__in=selected).update(assigned_playlist=None)
    if selected:
        owned.filter(id__in=selected).update(assigned_playlist=playlist)


@login_required
def playlist_builder(request):
    """Drag and drop playlist builder interface."""
    media_items = MediaAsset.objects.filter(owner=request.user)
    playlists = Playlist.objects.filter(owner=request.user)

    # Get current playlist
    playlist_id = request.GET.get('playlist')
    if playlist_id:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    else:
        playlist = playlists.order_by('-updated_at').first()

    if not playlist:
        playlist = Playlist.objects.create(name="Default Playlist", owner=request.user)

    # Handle settings save
    if request.method == "POST" and 'save_settings' in request.POST:
        name = request.POST.get('name', '').strip()
        if name:
            playlist.name = name[:255]

        status = request.POST.get('status', playlist.status)
        if status in dict(Playlist.STATUS_CHOICES):
            playlist.status = status

        schedule_type = request.POST.get('schedule_type', playlist.schedule_type)
        if schedule_type in dict(Playlist.SCHEDULE_TYPES):
            playlist.schedule_type = schedule_type

        # Blank clears the value; unparseable input is ignored.
        for field, parser in (('start_date', parse_date), ('end_date', parse_date),
                              ('start_time', parse_time), ('end_time', parse_time)):
            if field in request.POST:
                raw = request.POST.get(field, '').strip()
                if not raw:
                    setattr(playlist, field, None)
                else:
                    try:
                        parsed = parser(raw)
                    except ValueError:
                        parsed = None
                    if parsed is not None:
                        setattr(playlist, field, parsed)

        transition = request.POST.get('transition_effect', '').upper()
        if transition in dict(Playlist.TRANSITION_EFFECTS):
            playlist.transition_effect = transition
        playlist.is_loop = request.POST.get('is_loop') == 'on'
        playlist.save()

        _assign_screens(request, playlist)

        return redirect(f'{request.path}?playlist={playlist.id}&saved=true')

    # Search media
    search_query = request.GET.get('media_search')
    if search_query:
        media_items = media_items.filter(name__icontains=search_query)

    playlist = _user_playlists(request.user).get(pk=playlist.pk)

    context = {
        'media_items': media_items,
        'playlist': playlist,
        'playlists': playlists,
        'all_screens': Screen.objects.filter(owner=request.user),
        'saved': request.GET.get('saved') == 'true',
        'total_duration': playlist.total_duration,
    }

    if request.htmx and request.headers.get('HX-Target') == 'media-grid':
        return render(request, 'cotton/playlist/media_library.html', context)

    return render(request, 'playlist_builder.html', context)


@login_required
def playlist_list(request):
    """List view for all playlists with filtering and sorting."""
    playlists = _user_playlists(request.user).prefetch_related('assigned_screens')

    # Search and filter
    search_query = request.GET.get('search')
    if search_query:
        playlists = playlists.filter(name__icontains=search_query)

    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'All':
        playlists = playlists.filter(status=status_filter)

    # Sorting
    sort_by = request.GET.get('sort', '-updated_at')
    if sort_by in ['created_at', 'Oldest']:
        playlists = playlists.order_by('created_at')
    elif sort_by in ['name', 'Name']:
        playlists = playlists.order_by('name')
    else:
        playlists = playlists.order_by('-updated_at')

    playlists = list(playlists)
    for playlist in playlists:
        minutes, seconds = divmod(playlist.total_duration, 60)
        playlist.formatted_duration = f"{minutes}m {seconds:02d}s" + (" Loop" if playlist.is_loop else "")
        playlist.item_count = len(playlist.items.all())
        # Assigned screen IDs as strings for JS compatibility
        playlist.assigned_screen_ids = [str(s.id) for s in playlist.assigned_screens.all()]

    store, _ = Store.objects.get_or_create(user=request.user)

    return render(request, 'playlists.html', {
        'playlists': playlists,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'store': store,
        'all_screens': Screen.objects.filter(owner=request.user),
    })


@login_required
def create_playlist(request):
    """Create a new playlist."""
    if request.method == "POST":
        Playlist.objects.create(
            name=(request.POST.get('name') or 'New Playlist').strip()[:255],
            description=request.POST.get('description', ''),
            owner=request.user
        )
    return redirect('playlist_builder')


@login_required
def delete_playlist(request, playlist_id):
    """Delete a playlist."""
    if request.method == "POST":
        get_object_or_404(Playlist, id=playlist_id, owner=request.user).delete()
    return redirect('playlist_builder')





@login_required
def assign_playlist_screens(request):
    """Assign screens to a playlist from the modal."""
    if request.method == "POST":
        playlist = get_object_or_404(Playlist, id=request.POST.get('playlist_id'), owner=request.user)
        _assign_screens(request, playlist)
        messages.success(request, f'Screens assigned to {playlist.name} successfully.')

    return redirect('playlists_list')


@login_required
def add_to_playlist(request, media_id):
    """Add media to playlist."""
    if request.method == "POST":
        playlist = _pick_playlist(request, request.POST.get('playlist_id'))
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)

        if not PlaylistItem.objects.filter(playlist=playlist, media=media).exists():
            PlaylistItem.objects.create(playlist=playlist, media=media, position=_next_position(playlist))

        if request.htmx:
            return _sequence_response(request, playlist)
        return _builder_redirect(playlist)

    return redirect('playlist_builder')


@login_required
def add_cms_to_playlist(request, content_id):
    """Add CMS content to playlist."""
    if request.method == "POST":
        playlist = _pick_playlist(request, request.POST.get('playlist_id'))
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)

        if not PlaylistItem.objects.filter(playlist=playlist, store_content=content).exists():
            PlaylistItem.objects.create(
                playlist=playlist,
                store_content=content,
                position=_next_position(playlist),
                custom_duration=content.duration,
            )

        if request.htmx:
            return _sequence_response(request, playlist)
        return _builder_redirect(playlist)

    return redirect('playlist_builder')


@login_required
def remove_from_playlist(request, item_id):
    """Remove item from playlist."""
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        playlist = item.playlist
        item.delete()
        _renumber(playlist)

        if request.htmx:
            return _sequence_response(request, playlist)

    return redirect('playlist_builder')


@login_required
def reorder_playlist(request):
    """Reorder playlist items via HTMX."""
    if request.method != "POST":
        return HttpResponse(status=204)

    playlist_id = request.POST.get('playlist_id')
    if playlist_id:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    else:
        playlist = Playlist.objects.filter(owner=request.user).first()
    if playlist is None:
        return HttpResponse(status=204)

    item_ids = [i for i in request.POST.getlist('item') if i.isdigit()]
    with transaction.atomic():
        for idx, item_id in enumerate(item_ids):
            PlaylistItem.objects.filter(id=item_id, playlist=playlist).update(position=idx)
        _renumber(playlist)

    return _sequence_response(request, playlist)


@login_required
def update_playlist_item(request, item_id):
    """Update playlist item duration."""
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        duration = parse_int(request.POST.get(f'duration_{item.id}'), None, 1, 3600)
        if duration is not None:
            item.custom_duration = duration
            item.save(update_fields=['custom_duration'])

            if request.htmx:
                return _sequence_response(request, item.playlist)

    return HttpResponse(status=204)


@login_required
def save_playlist_settings(request):
    """Save global playlist settings."""
    if request.method == "POST":
        store, _ = Store.objects.get_or_create(user=request.user)

        store.default_image_duration = parse_int(request.POST.get('default_duration'), 10, 1, 3600)
        transition = request.POST.get('transition_effect', 'fade')
        if transition in dict(Store.TRANSITION_EFFECTS):
            store.transition_effect = transition
        store.mute_by_default = request.POST.get('mute_by_default') == 'true'
        store.default_volume = parse_int(request.POST.get('default_volume'), 75, 0, 100)
        fallback_type = request.POST.get('fallback_type', 'brand_logo')
        if fallback_type in dict(Store.FALLBACK_TYPES):
            store.fallback_type = fallback_type

        fallback_logo = request.POST.get('fallback_logo', '').strip()
        if fallback_logo:
            if is_valid_http_url(fallback_logo):
                store.fallback_logo = fallback_logo[:1024]
            else:
                messages.warning(request, 'Fallback logo must be a valid http(s) URL; it was not changed.')

        store.save()
        messages.success(request, 'Playlist settings saved successfully.')

        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)

    return redirect('playlists_list')
