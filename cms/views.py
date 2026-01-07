"""
CMS Views - Handles all CMS-related functionality including dashboard,
playlists, media library, screens, and store CMS.
"""
import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder

from core.models import (
    Screen, Playlist, MediaAsset, PlaylistItem,
    Store, StoreLayout, StoreContent, PairingCode, SupportTicket
)
from services.instagram import sync_hashtag_media


# =============================================================================
# Dashboard & Overview
# =============================================================================

@login_required
def dashboard(request):
    """Dashboard overview with real-time stats and recent activity."""
    screens = Screen.objects.filter(owner=request.user).order_by('-created_at')
    playlists = Playlist.objects.filter(owner=request.user)
    media_assets = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')

    # Calculate stats
    total_screens = screens.count()
    online_screens = sum(1 for s in screens if s.is_online)
    total_playlists = playlists.count()
    total_media = media_assets.count()
    recent_media = media_assets[:5]

    # Calculate estimated impressions
    filter_range = request.GET.get('range', '7D')
    days = 7 if filter_range == '7D' else 30 if filter_range == '30D' else 90

    if filter_range == 'All':
        oldest_screen = screens.order_by('created_at').first()
        if oldest_screen:
            days = max((timezone.now() - oldest_screen.created_at).days, 1)

    estimated_impressions = online_screens * 100 * days
    impressions = f"{estimated_impressions / 1000:.1f}K" if estimated_impressions >= 1000 else str(estimated_impressions)

    trend = f"{min(online_screens * 5, 25)}%" if online_screens > 0 else "0%"
    trend_up = "true"

    # Recently added screens
    week_ago = timezone.now() - timezone.timedelta(days=7)
    new_screens_this_week = screens.filter(created_at__gte=week_ago).count()

    # Instagram sync status
    instagram_media = media_assets.filter(source='INSTAGRAM').order_by('-created_at').first()
    last_sync_time = None
    if instagram_media:
        time_diff = timezone.now() - instagram_media.created_at
        if time_diff.seconds < 60:
            last_sync_time = f"{time_diff.seconds}s ago"
        elif time_diff.seconds < 3600:
            last_sync_time = f"{time_diff.seconds // 60}m ago"
        elif time_diff.days == 0:
            last_sync_time = f"{time_diff.seconds // 3600}h ago"
        else:
            last_sync_time = f"{time_diff.days}d ago"

    context = {
        'screens': screens,
        'total_screens': total_screens,
        'online_screens': online_screens,
        'offline_screens': total_screens - online_screens,
        'total_playlists': total_playlists,
        'total_media': total_media,
        'playlists': playlists,
        'recent_media': recent_media,
        'impressions': impressions,
        'trend': trend,
        'trend_up': trend_up,
        'current_range': filter_range,
        'new_screens_this_week': new_screens_this_week,
        'last_sync_time': last_sync_time,
    }

    if request.htmx:
        return render(request, 'partials/dashboard_stats.html', context)

    return render(request, 'dashboard.html', context)


# =============================================================================
# Screen Management
# =============================================================================

@login_required
def screens(request):
    """List all screens with their status."""
    screens_list = Screen.objects.filter(owner=request.user).order_by('-created_at')

    context = {
        'screens': screens_list,
        'total_screens': screens_list.count(),
        'online_screens': sum(1 for s in screens_list if s.is_online),
        'offline_screens': screens_list.count() - sum(1 for s in screens_list if s.is_online),
    }
    return render(request, 'screens.html', context)


@login_required
def setup_screen(request):
    """Setup a new screen via pairing code."""
    if request.method == "POST":
        code = request.POST.get('pairing_code', '').strip().upper()
        name = request.POST.get('name')
        location = request.POST.get('location', '')

        # Validate pairing code
        try:
            pairing = PairingCode.objects.get(code=code)

            if timezone.now() > pairing.expires_at:
                messages.error(request, 'This pairing code has expired.')
                return render(request, 'setup_screen.html', {'pairing_code': code, 'name': name})

            if Screen.objects.filter(pairing_code=code).exists():
                messages.error(request, 'This code is already linked to another screen.')
                return render(request, 'setup_screen.html', {'pairing_code': code, 'name': name})

        except PairingCode.DoesNotExist:
            messages.error(request, 'Invalid pairing code.')
            return render(request, 'setup_screen.html', {'pairing_code': code, 'name': name})

        # Create screen
        Screen.objects.create(
            name=name,
            pairing_code=code,
            location=location if location else None,
            owner=request.user,
            status='ONLINE'
        )

        messages.success(request, f'Screen "{name}" connected successfully!')
        return redirect('screens')

    return render(request, 'setup_screen.html')


@login_required
def delete_screen(request, screen_id):
    """Delete a screen."""
    if request.method == "POST":
        screen = get_object_or_404(Screen, id=screen_id, owner=request.user)
        screen_name = screen.name
        screen.delete()
        messages.success(request, f'Screen "{screen_name}" deleted successfully')
    return redirect('screens')


@login_required
def assign_playlist(request, screen_id):
    """Assign a playlist to a screen."""
    screen = get_object_or_404(Screen, id=screen_id, owner=request.user)
    playlists = Playlist.objects.filter(owner=request.user)

    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        screen.assigned_playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user) if playlist_id else None
        screen.save()
        return redirect('dashboard')

    return render(request, 'assign_playlist.html', {'screen': screen, 'playlists': playlists})


# =============================================================================
# Playlist Management
# =============================================================================

@login_required
def playlist_builder(request):
    """Drag and drop playlist builder interface."""
    media_items = MediaAsset.objects.filter(owner=request.user)
    playlists = Playlist.objects.filter(owner=request.user)

    # Get current playlist
    playlist_id = request.GET.get('playlist')
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user) if playlist_id else playlists.order_by('-updated_at').first()

    if not playlist:
        playlist = Playlist.objects.create(name="Default Playlist", owner=request.user)

    # Handle settings save
    if request.method == "POST" and 'save_settings' in request.POST:
        playlist.name = request.POST.get('name', playlist.name)
        playlist.status = request.POST.get('status', playlist.status)
        playlist.schedule_type = request.POST.get('schedule_type', playlist.schedule_type)

        for field in ['start_date', 'end_date', 'start_time', 'end_time']:
            value = request.POST.get(field)
            if value:
                setattr(playlist, field, value)

        playlist.transition_effect = request.POST.get('transition_effect', playlist.transition_effect)
        playlist.is_loop = request.POST.get('is_loop') == 'on'
        playlist.save()

        # Handle screen assignments
        assigned_screen_ids = request.POST.getlist('assigned_screens')
        Screen.objects.filter(owner=request.user, assigned_playlist=playlist).exclude(id__in=assigned_screen_ids).update(assigned_playlist=None)
        if assigned_screen_ids:
            Screen.objects.filter(owner=request.user, id__in=assigned_screen_ids).update(assigned_playlist=playlist)

        return redirect(f'{request.path}?playlist={playlist.id}&saved=true')

    # Search media
    search_query = request.GET.get('media_search')
    if search_query:
        media_items = media_items.filter(name__icontains=search_query)

    # Calculate total duration
    total_duration = sum(
        item.custom_duration if item.custom_duration else item.media.duration
        for item in playlist.items.all()
    )

    context = {
        'media_items': media_items,
        'playlist': playlist,
        'playlists': playlists,
        'all_screens': Screen.objects.filter(owner=request.user),
        'saved': request.GET.get('saved') == 'true',
        'total_duration': total_duration
    }

    if request.htmx and request.headers.get('HX-Target') == 'media-grid':
        return render(request, 'cotton/playlist/media_library.html', context)

    return render(request, 'playlist_builder.html', context)


@login_required
def playlist_list(request):
    """List view for all playlists with filtering and sorting."""
    playlists = Playlist.objects.filter(owner=request.user)

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

    # Calculate duration for each playlist
    for playlist in playlists:
        total_seconds = sum(item.custom_duration or item.media.duration for item in playlist.items.all())
        minutes, seconds = divmod(total_seconds, 60)
        playlist.formatted_duration = f"{minutes}m {seconds:02d}s" + (" Loop" if playlist.is_loop else "")
        playlist.item_count = playlist.items.count()

    store, _ = Store.objects.get_or_create(user=request.user)

    return render(request, 'playlists.html', {
        'playlists': playlists,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'store': store,
    })


@login_required
def create_playlist(request):
    """Create a new playlist."""
    if request.method == "POST":
        Playlist.objects.create(
            name=request.POST.get('name', 'New Playlist'),
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


# =============================================================================
# Playlist Items
# =============================================================================

@login_required
def add_to_playlist(request, media_id):
    """Add media to playlist."""
    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user) if playlist_id else Playlist.objects.filter(owner=request.user).first()

        if not playlist:
            playlist = Playlist.objects.create(name="Default", owner=request.user)

        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)

        if not PlaylistItem.objects.filter(playlist=playlist, media=media).exists():
            PlaylistItem.objects.create(
                playlist=playlist,
                media=media,
                position=playlist.items.count()
            )

            try:
                # Calculate total duration
                total_duration = sum(
                    item.custom_duration if item.custom_duration else (item.media.duration if item.media else 15)
                    for item in playlist.items.all()
                )
                return render(request, 'cotton/playlist/sequence_editor.html', {
                    'playlist': playlist,
                    'total_duration': total_duration
                })
            except Exception as e:
                pass

    return redirect('playlist_builder')


@login_required
def add_cms_to_playlist(request, content_id):
    """Add CMS content to playlist."""
    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user) if playlist_id else Playlist.objects.filter(owner=request.user).first()

        if not playlist:
            playlist = Playlist.objects.create(name="Default", owner=request.user)

        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)

        if not PlaylistItem.objects.filter(playlist=playlist, store_content=content).exists():
            PlaylistItem.objects.create(
                playlist=playlist,
                store_content=content,
                position=playlist.items.count(),
                custom_duration=15  # Default duration for CMS content
            )

        if request.htmx:
            # Calculate total duration
            total_duration = sum(
                item.custom_duration if item.custom_duration else (item.media.duration if item.media else 15)
                for item in playlist.items.all()
            )
            return render(request, 'cotton/playlist/sequence_editor.html', {
                'playlist': playlist,
                'total_duration': total_duration
            })

    return redirect('playlist_builder')


@login_required
def remove_from_playlist(request, item_id):
    """Remove item from playlist."""
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        playlist = item.playlist
        item.delete()

        if request.htmx:
            # Calculate total duration
            total_duration = sum(
                item.custom_duration if item.custom_duration else item.media.duration
                for item in playlist.items.all()
            )
            return render(request, 'cotton/playlist/sequence_editor.html', {
                'playlist': playlist,
                'total_duration': total_duration
            })

    return redirect('playlist_builder')


@login_required
def reorder_playlist(request):
    """Reorder playlist items via HTMX."""
    if request.method == "POST":
        item_ids = request.POST.getlist('item')
        playlist_id = request.POST.get('playlist_id')

        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user) if playlist_id else Playlist.objects.filter(owner=request.user).first()

        if playlist and item_ids:
            for idx, item_id in enumerate(item_ids):
                try:
                    PlaylistItem.objects.filter(id=item_id, playlist=playlist).update(position=idx)
                except PlaylistItem.DoesNotExist:
                    continue

        # Calculate total duration
        total_duration = sum(
            item.custom_duration if item.custom_duration else item.media.duration
            for item in playlist.items.all()
        )
        return render(request, 'cotton/playlist/sequence_editor.html', {
            'playlist': playlist,
            'total_duration': total_duration
        })

    return HttpResponse(status=204)


@login_required
def update_playlist_item(request, item_id):
    """Update playlist item duration."""
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        duration = request.POST.get(f'duration_{item.id}')
        if duration:
            item.custom_duration = int(duration)
            item.save()

            if request.htmx:
                playlist = item.playlist
                total_duration = sum(
                    i.custom_duration if i.custom_duration else i.media.duration
                    for i in playlist.items.all()
                )
                return render(request, 'cotton/playlist/sequence_editor.html', {
                    'playlist': playlist,
                    'total_duration': total_duration
                })

    return HttpResponse(status=204)


@login_required
def save_playlist_settings(request):
    """Save global playlist settings."""
    if request.method == "POST":
        store, _ = Store.objects.get_or_create(user=request.user)

        store.default_image_duration = int(request.POST.get('default_duration', 10))
        store.transition_effect = request.POST.get('transition_effect', 'fade')
        store.mute_by_default = request.POST.get('mute_by_default') == 'true'
        store.default_volume = int(request.POST.get('default_volume', 75))
        store.fallback_type = request.POST.get('fallback_type', 'brand_logo')

        fallback_logo = request.POST.get('fallback_logo', '')
        if fallback_logo:
            store.fallback_logo = fallback_logo

        store.save()
        messages.success(request, 'Playlist settings saved successfully.')

        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)

        return redirect('playlists_list')

    return redirect('playlists_list')


# =============================================================================
# Media Library
# =============================================================================

@login_required
def media_library(request):
    """Full media library view with filtering."""
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')

    source = request.GET.get('source')
    if source in ['UPLOAD', 'INSTAGRAM']:
        media_items = media_items.filter(source=source)

    media_type = request.GET.get('type')
    if media_type in ['IMAGE', 'VIDEO']:
        media_items = media_items.filter(media_type=media_type)

    context = {
        'media_items': media_items,
        'total_media': media_items.count(),
        'current_source': source,
        'current_type': media_type,
    }

    if request.htmx and request.GET.get('picker'):
        return render(request, 'partials/media_picker.html', context)

    return render(request, 'media_library.html', context)


@login_required
def cms_content_library(request):
    """Partial view for CMS content picker."""
    contents = StoreContent.objects.filter(owner=request.user, status='PUBLISHED').order_by('-updated_at')
    
    context = {
        'contents': contents,
    }

    if request.htmx:
        return render(request, 'partials/cms_content_picker.html', context)
        
    return HttpResponse(status=400)


@login_required
def upload_media(request):
    """Handle media upload (file or URL)."""
    if request.method == "POST":
        uploaded_file = request.FILES.get('file')
        file_url = request.POST.get('file_url', '').strip()
        media_type = request.POST.get('media_type', 'IMAGE')
        duration = int(request.POST.get('duration', 10))
        name = request.POST.get('name', '').strip()

        try:
            if uploaded_file:
                # Validate file
                if uploaded_file.size > 200 * 1024 * 1024:
                    messages.error(request, 'File size must be less than 200MB.')
                    return redirect('media_library')

                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'video/mp4', 'video/webm']
                if uploaded_file.content_type not in allowed_types:
                    messages.error(request, 'Invalid file type.')
                    return redirect('media_library')

                # Save file
                ext = os.path.splitext(uploaded_file.name)[1]
                filename = f"media/{request.user.id}/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                path = default_storage.save(filename, ContentFile(uploaded_file.read()))
                file_url = default_storage.url(path)

                # Auto-detect media type
                if uploaded_file.content_type.startswith('image/'):
                    media_type = 'IMAGE'
                elif uploaded_file.content_type.startswith('video/'):
                    media_type = 'VIDEO'

            elif file_url:
                if not file_url.startswith(('http://', 'https://')):
                    messages.error(request, 'Please provide a valid URL.')
                    return redirect('media_library')
            else:
                messages.error(request, 'Please provide a file or URL.')
                return redirect('media_library')

            # Create media asset
            MediaAsset.objects.create(
                owner=request.user,
                name=name if name else None,
                file_url=file_url,
                media_type=media_type,
                source='UPLOAD',
                duration=duration
            )
            messages.success(request, 'Media uploaded successfully!')

        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.htmx:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            messages.error(request, f'Upload failed: {str(e)}')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'url': file_url, 'name': name, 'type': media_type})

    return redirect('media_library')


@login_required
def delete_media(request, media_id):
    """Delete a media asset."""
    if request.method == "POST":
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)
        media.delete()
        # messages.success(request, 'Media deleted successfully') # Silenced
    return redirect('media_library')


@login_required
def sync_instagram(request):
    """
    Sync media from Instagram hashtag.
    Downloads media to local storage so URLs don't expire.
    """
    if request.method == "POST":
        tag = request.POST.get('hashtag', '').strip()
        
        if not tag:
            messages.error(request, 'Please provide a hashtag.')
            return redirect('playlist_builder')
        
        try:
            # Use the real Instagram service
            synced_count = sync_hashtag_media(tag, request.user)
            
            if synced_count > 0:
                messages.success(request, f'Successfully synced {synced_count} media items from #{tag}')
            else:
                messages.warning(
                    request, 
                    f'No new media found for #{tag}. This could mean:\n'
                    '• All media is already synced\n'
                    '• Instagram credentials are not configured\n'
                    '• The hashtag has no recent posts'
                )
        except Exception as e:
            messages.error(request, f'Instagram sync failed: {str(e)}')

    return redirect('playlist_builder')


# =============================================================================
# Configuration
# =============================================================================

@login_required
def configuration(request):
    """Manage store profile and system preferences."""
    store, _ = Store.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # Store profile
        store.business_name = request.POST.get('business_name', '')
        store.description = request.POST.get('description', '')
        store.phone_number = request.POST.get('phone_number', '')
        store.timezone = request.POST.get('timezone', 'UTC')
        store.logo_url = request.POST.get('logo_url', '')

        # System preferences
        store.dark_mode = request.POST.get('dark_mode') == 'on'
        store.auto_lock = request.POST.get('auto_lock') == 'on'
        store.enable_beta = request.POST.get('enable_beta') == 'on'

        # Integrations
        if 'toggle_instagram' in request.POST:
            store.instagram_connected = not store.instagram_connected

        store.save()
        messages.success(request, 'Configuration saved successfully.')
        return redirect('configuration')

    total_screens = Screen.objects.filter(owner=request.user).count()
    active_screens = Screen.objects.filter(owner=request.user, status='ONLINE').count()

    context = {
        'store': store,
        'total_screens': total_screens,
        'active_screens': active_screens,
        'plan_limit': 5,
        'timezones': ['UTC', 'US/Pacific', 'US/Eastern', 'Europe/London', 'Europe/Paris', 'Asia/Tokyo'],
    }
    return render(request, 'configuration.html', context)


@login_required
def support(request):
    """
    Support page with help center and ticket submission.
    """
    if request.method == 'POST':
        topic = request.POST.get('topic')
        urgency = request.POST.get('urgency')
        description = request.POST.get('description')
        
        SupportTicket.objects.create(
            user=request.user,
            topic=topic,
            urgency=urgency,
            description=description
        )
        messages.success(request, 'Support ticket submitted successfully. We will contact you soon.')
        return redirect('support')
        
    return render(request, 'support.html')


# =============================================================================
# Store CMS
# =============================================================================

@login_required
def store_cms(request):
    """Main Store CMS page."""
    layouts = StoreLayout.objects.filter(owner=request.user)
    contents = StoreContent.objects.filter(owner=request.user)
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6]

    context = {
        'layouts': layouts,
        'contents': contents,
        'total_active': layouts.filter(status='PUBLISHED').count() + contents.filter(status='PUBLISHED').count(),
        'drafts_count': layouts.filter(status='DRAFT').count() + contents.filter(status='DRAFT').count(),
        'scheduled_count': layouts.filter(status='SCHEDULED').count() + contents.filter(status='SCHEDULED').count(),
        'media_items': media_items,
    }
    return render(request, 'store_cms.html', context)


@login_required
def store_cms_editor(request, layout_id=None):
    """Layout editor with drag-and-drop canvas."""
    if layout_id:
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
    else:
        layout = StoreLayout.objects.create(name="Untitled Layout", owner=request.user)
        return redirect('store_cms_editor_edit', layout_id=layout.id)

    context = {
        'layout': layout,
        'layouts': StoreLayout.objects.filter(owner=request.user),
        'contents': StoreContent.objects.filter(owner=request.user),
        'media_items': MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6],
        'layout_data_json': json.dumps(layout.layout_data, cls=DjangoJSONEncoder)
    }
    return render(request, 'store_cms_layout.html', context)


@login_required
def store_cms_content(request, content_id=None):
    """Content editor for rich text content."""
    if content_id:
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)
    else:
        content = StoreContent.objects.create(title="Untitled Content", owner=request.user)
        return redirect('store_cms_content_edit', content_id=content.id)

    context = {
        'content': content,
        'contents': StoreContent.objects.filter(owner=request.user),
        'media_items': MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6],
    }
    return render(request, 'store_cms_editor.html', context)


@login_required
def save_layout(request, layout_id):
    """Save layout data via HTMX."""
    if request.method == "POST":
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)

        name = request.POST.get('name') or request.POST.get('layout_name')
        if name:
            layout.name = name

        status = request.POST.get('status')
        if status in ['DRAFT', 'PUBLISHED', 'SCHEDULED', 'ARCHIVED']:
            layout.status = status

        layout_data = request.POST.get('layout_data')
        if layout_data:
            try:
                layout.layout_data = json.loads(layout_data)
            except json.JSONDecodeError:
                pass

        canvas_width = request.POST.get('canvas_width')
        if canvas_width:
            layout.canvas_width = int(canvas_width)

        canvas_height = request.POST.get('canvas_height')
        if canvas_height:
            layout.canvas_height = int(canvas_height)

        layout.save()

        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)

        messages.success(request, 'Layout saved successfully.')
        return redirect('store_cms_editor_edit', layout_id=layout.id)

    return redirect('store_cms')


@login_required
def save_content(request, content_id):
    """Save content data via HTMX."""
    if request.method == "POST":
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)

        title = request.POST.get('title')
        if title:
            content.title = title

        content.content_html = request.POST.get('content_html', '')

        status = request.POST.get('status')
        if status in ['DRAFT', 'PUBLISHED', 'SCHEDULED', 'ARCHIVED']:
            content.status = status

        # Scheduling
        duration = request.POST.get('duration')
        if duration:
            content.duration = int(duration)

        start_date = request.POST.get('start_date')
        if start_date:
            content.start_date = start_date
        else:
            content.start_date = None

        end_date = request.POST.get('end_date')
        if end_date:
            content.end_date = end_date
        else:
            content.end_date = None

        target_screen_id = request.POST.get('target_screen')
        if target_screen_id:
             content.target_screen_id = target_screen_id if target_screen_id != 'all' else None
        
        content.save()

        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)

        messages.success(request, 'Content saved successfully.')
        return redirect('store_cms_content_edit', content_id=content.id)

    return redirect('store_cms')


@login_required
def delete_layout(request, layout_id):
    """Delete a layout."""
    if request.method == "POST":
        get_object_or_404(StoreLayout, id=layout_id, owner=request.user).delete()
        messages.success(request, 'Layout deleted.')
    return redirect('store_cms')


@login_required
def delete_content(request, content_id):
    """Delete content."""
    if request.method == "POST":
        get_object_or_404(StoreContent, id=content_id, owner=request.user).delete()
        messages.success(request, 'Content deleted.')
    return redirect('store_cms')


import base64
from django.core.files.base import ContentFile
from datetime import datetime

@login_required
def save_layout_snapshot(request, layout_id):
    if request.method == "POST":
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
        image_data = request.FILES.get('image')
        
        if not image_data:
            return JsonResponse({'status': 'error', 'message': 'No image data provided'})

        try:
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"media/{request.user.id}/snapshots/{layout.id}_{timestamp}.png"
            
            # Save file
            path = default_storage.save(filename, ContentFile(image_data.read()))
            file_url = default_storage.url(path)

            # Create MediaAsset
            media = MediaAsset.objects.create(
                owner=request.user,
                name=f"Snapshot - {layout.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                media_type='IMAGE',
                source='UPLOAD',
                file_url=file_url,
                duration=10 # Default duration for images
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Snapshot saved to Media Library',
                'media_id': str(media.id),
                'url': file_url
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def preview_layout(request, layout_id):
    layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
    
    context = {
        'layout': layout,
        'layout_data_json': json.dumps(layout.layout_data, cls=DjangoJSONEncoder)
    }
    return render(request, 'store_cms_preview.html', context)
