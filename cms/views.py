from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from core.models import Screen, Playlist, MediaAsset, PlaylistItem, Store, StoreLayout, StoreContent
from django.utils import timezone
from services.instagram import sync_hashtag_media



@login_required
def dashboard(request):
    """
    Shows list of screens and their status.
    """
    screens = Screen.objects.filter(owner=request.user).order_by('-created_at')
    all_screens = Screen.objects.filter(owner=request.user) # Used for assigning playlists
    playlists = Playlist.objects.filter(owner=request.user)
    media_assets = MediaAsset.objects.filter(owner=request.user)
    
    # Calculate stats
    total_screens = screens.count()
    online_screens = sum(1 for s in screens if s.is_online)
    total_playlists = playlists.count()
    total_media = media_assets.count()
    
    # Mock data changes based on filter
    filter_range = request.GET.get('range', '7D')
    impressions = "12.5K"
    trend = "12%"
    
    if filter_range == '30D':
        impressions = "45.2K"
        trend = "8%"
    elif filter_range == 'All':
        impressions = "128K"
        trend = "24%"

    context = {
        'screens': screens,
        'total_screens': total_screens,
        'online_screens': online_screens,
        'offline_screens': total_screens - online_screens,
        'total_playlists': total_playlists,
        'total_media': total_media,
        'playlists': playlists,
        'impressions': impressions,
        'trend': trend,
        'trend_up': 'true',
        'current_range': filter_range,
    }
    
    if request.htmx:
        return render(request, 'partials/dashboard_stats.html', context)
        
    return render(request, 'dashboard.html', context)


@login_required
def screens(request):
    """
    Shows list of screens and their status (Device Management).
    """
    screens_list = Screen.objects.filter(owner=request.user).order_by('-created_at')
    
    # Calculate stats
    total_screens = screens_list.count()
    online_screens = sum(1 for s in screens_list if s.is_online)
    
    context = {
        'screens': screens_list,
        'total_screens': total_screens,
        'online_screens': online_screens,
        'offline_screens': total_screens - online_screens,
    }
    return render(request, 'screens.html', context)


@login_required
def setup_screen(request):
    """
    Form to manually add a screen via pairing code entered by Store Owner.
    """
    if request.method == "POST":
        code = request.POST.get('pairing_code')
        name = request.POST.get('name')
        location = request.POST.get('location', '')

        # Create screen with the authenticated user as owner
        screen = Screen.objects.create(
            name=name,
            pairing_code=code,
            location=location if location else None,
            owner=request.user
        )
        messages.success(request, f'Screen "{name}" connected successfully!')
        return redirect('screens')

    return render(request, 'setup_screen.html')


@login_required
def playlist_builder(request):
    """
    Drag and drop interface.
    """
    media_items = MediaAsset.objects.filter(owner=request.user)
    playlists = Playlist.objects.filter(owner=request.user)
    
    # Get the current playlist (from query param or default to first)
    playlist_id = request.GET.get('playlist')
    if playlist_id:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    else:
        # Default to the most recently updated playlist or create a dummy one if none exist
        playlist = playlists.order_by('-updated_at').first()
    
    # Create a default playlist if none exists
    if not playlist:
        playlist = Playlist.objects.create(name="Default Playlist", owner=request.user)

    # Handle Settings Save
    if request.method == "POST" and 'save_settings' in request.POST:
        playlist.name = request.POST.get('name', playlist.name)
        playlist.status = request.POST.get('status', playlist.status)
        playlist.schedule_type = request.POST.get('schedule_type', playlist.schedule_type)
        
        # Date/Time handling (simplistic for now)
        start_date = request.POST.get('start_date')
        if start_date: playlist.start_date = start_date
        
        end_date = request.POST.get('end_date')
        if end_date: playlist.end_date = end_date
        
        start_time = request.POST.get('start_time')
        if start_time: playlist.start_time = start_time
        
        end_time = request.POST.get('end_time')
        if end_time: playlist.end_time = end_time

        playlist.transition_effect = request.POST.get('transition_effect', playlist.transition_effect)
        playlist.is_loop = request.POST.get('is_loop') == 'on'
        
        playlist.save()
        
        # Handle Screen Assignments
        assigned_screen_ids = request.POST.getlist('assigned_screens')
        
        # 1. Clear playlist from screens that are NOT in the list but currently have this playlist
        Screen.objects.filter(owner=request.user, assigned_playlist=playlist).exclude(id__in=assigned_screen_ids).update(assigned_playlist=None)
        
        # 2. Set playlist for screens in the list
        if assigned_screen_ids:
            Screen.objects.filter(owner=request.user, id__in=assigned_screen_ids).update(assigned_playlist=playlist)

        return redirect(f'{request.path}?playlist={playlist.id}&saved=true')
    
    # Search Media
    search_query = request.GET.get('media_search')
    if search_query:
        media_items = media_items.filter(name__icontains=search_query) 
    
    # Get all user screens for the settings panel
    all_screens = Screen.objects.filter(owner=request.user)

    context = {
        'media_items': media_items,
        'playlist': playlist,
        'playlists': playlists,
        'all_screens': all_screens,
        'saved': request.GET.get('saved') == 'true'
    }

    if request.htmx:
        target = request.headers.get('HX-Target')
        if target == 'media-grid':
            return render(request, 'components/playlist/media_library.html', context)

    return render(request, 'playlist_builder.html', context)


@login_required
def playlist_list(request):
    """
    List view for all playlists with filtering and sorting.
    """
    playlists = Playlist.objects.filter(owner=request.user)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        playlists = playlists.filter(name__icontains=search_query)

    # Filtering
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'All':
        playlists = playlists.filter(status=status_filter)

    # Sorting
    sort_by = request.GET.get('sort', '-updated_at')
    if sort_by in ['created_at', 'Oldest']:
        playlists = playlists.order_by('created_at')
    elif sort_by in ['name', 'Name']:
        playlists = playlists.order_by('name')
    else:  # Recent (-updated_at is default)
        playlists = playlists.order_by('-updated_at')

    # Calculate duration and prepare formatted data
    for playlist in playlists:
        total_seconds = 0
        item_count = 0
        for item in playlist.items.all():
            total_seconds += item.custom_duration or item.media.duration
            item_count += 1
        
        # Format duration (e.g., "12m 30s Loop" or "4m 00s")
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        playlist.formatted_duration = f"{minutes}m {seconds:02d}s"
        if playlist.is_loop:
             playlist.formatted_duration += " Loop"
        
        playlist.item_count = item_count

    # Get store settings for the settings modal
    store, _ = Store.objects.get_or_create(user=request.user)

    return render(request, 'playlists.html', {
        'playlists': playlists,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'store': store,
    })


@login_required
def sync_instagram(request):
    """
    Trigger sync.
    If real sync fails (no auth), creates mock data for demonstration.
    """
    if request.method == "POST":
        tag = request.POST.get('hashtag')
        try:
            # Try real sync (will fail without credentials in settings)
            # count = sync_hashtag_media(tag, request.user)
            raise Exception("No IG Credentials configured")
        except Exception as e:
            # Mock data for demo
            playlist = Playlist.objects.filter(owner=request.user).first()
            if not playlist:
                playlist = Playlist.objects.create(name="Default", owner=request.user)
            
            # Create a mock media with authenticated user as owner
            MediaAsset.objects.create(
                owner=request.user,
                media_type='IMAGE',
                source='INSTAGRAM',
                file_url='https://via.placeholder.com/600x800?text=IG+Media',
                instagram_id=f"mock_{timezone.now().timestamp()}",
                duration=10
            )
            
    return redirect('playlist_builder')


@login_required
def reorder_playlist(request):
    """
    HTMX endpoint to save order.
    Expects 'item' list from SortableJS.
    """
    if request.method == "POST":
        item_ids = request.POST.getlist('item')
        playlist_id = request.POST.get('playlist_id')
        
        if playlist_id:
            playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        else:
            playlist = Playlist.objects.filter(owner=request.user).first()
        
        if playlist and item_ids:
            for idx, item_id in enumerate(item_ids):
                try:
                    item = PlaylistItem.objects.get(id=item_id, playlist=playlist)
                    item.position = idx
                    item.save()
                except PlaylistItem.DoesNotExist:
                    continue
        
        # Return updated playlist items partial
        # Return updated playlist items
        context = {'playlist': playlist}
        # If we had a partial for items list, we'd use it. 
        # Using sequence_editor component creates full re-render of sequence column.
        return render(request, 'components/playlist/sequence_editor.html', context)

    return HttpResponse(status=204)


@login_required
def add_to_playlist(request, media_id):
    """
    Adds media to the default playlist.
    """
    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        
        if playlist_id:
            playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        else:
            playlist = Playlist.objects.filter(owner=request.user).first()
            
        if not playlist:
            playlist = Playlist.objects.create(name="Default", owner=request.user)
            
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)
        
        # Check if already in playlist
        if not PlaylistItem.objects.filter(playlist=playlist, media=media).exists():
            # Add to end
            count = playlist.items.count()
            PlaylistItem.objects.create(
                playlist=playlist,
                media=media,
                position=count
            )
        
        
        if request.htmx:
            context = {'playlist': playlist}
            return render(request, 'components/playlist/sequence_editor.html', context)
        
    return redirect('playlist_builder')


@login_required
def remove_from_playlist(request, item_id):
    """
    Removes a media item from a playlist.
    """
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        item.delete()
        
    if request.htmx:
        # Get playlist to render updated sequence
        playlist = item.playlist
        context = {'playlist': playlist}
        return render(request, 'components/playlist/sequence_editor.html', context)
        
    return redirect('playlist_builder')


@login_required
def update_playlist_item(request, item_id):
    """
    Update individual item (e.g. duration).
    """
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        # HTMX sends name="duration_<id>" value="<val>" typically, or if we used hx-vals, just duration
        # Our input name is "duration_{{ item.id }}"
        duration = request.POST.get(f'duration_{item.id}')
        if duration:
            item.custom_duration = int(duration)
            item.save()
            
    return HttpResponse(status=204)


@login_required
def media_library(request):
    """
    Full media library view.
    """
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')
    
    # Filter by source if specified
    source = request.GET.get('source')
    if source in ['UPLOAD', 'INSTAGRAM']:
        media_items = media_items.filter(source=source)
    
    # Filter by type if specified
    media_type = request.GET.get('type')
    if media_type in ['IMAGE', 'VIDEO']:
        media_items = media_items.filter(media_type=media_type)
    
    context = {
        'media_items': media_items,
        'total_media': media_items.count(),
        'current_source': source,
        'current_type': media_type,
    }
    return render(request, 'media_library.html', context)


@login_required
def upload_media(request):
    """
    Handle media upload (file or URL).
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get('file')
        file_url = request.POST.get('file_url', '').strip()
        media_type = request.POST.get('media_type', 'IMAGE')
        duration = int(request.POST.get('duration', 10))
        name = request.POST.get('name', '').strip()

        try:
            if uploaded_file:
                # Handle file upload
                from django.core.files.storage import default_storage
                from django.core.files.base import ContentFile
                import os

                # Validate file size (50MB limit)
                if uploaded_file.size > 50 * 1024 * 1024:
                    messages.error(request, 'File size must be less than 50MB.')
                    return redirect('media_library')

                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'video/mp4', 'video/webm']
                if uploaded_file.content_type not in allowed_types:
                    messages.error(request, 'Invalid file type. Supported formats: JPG, PNG, GIF, MP4, WebM')
                    return redirect('media_library')

                # Generate unique filename
                ext = os.path.splitext(uploaded_file.name)[1]
                filename = f"media/{request.user.id}/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"

                # Save file
                path = default_storage.save(filename, ContentFile(uploaded_file.read()))
                file_url = default_storage.url(path)

                # Auto-detect media type if not specified
                if uploaded_file.content_type.startswith('image/'):
                    media_type = 'IMAGE'
                elif uploaded_file.content_type.startswith('video/'):
                    media_type = 'VIDEO'

            elif file_url:
                # Handle URL upload (existing functionality)
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
            messages.error(request, f'Upload failed: {str(e)}')

    return redirect('media_library')


@login_required
def delete_media(request, media_id):
    """
    Delete a media asset.
    """
    if request.method == "POST":
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)
        media.delete()
        messages.success(request, 'Media deleted successfully')

    return redirect('media_library')


@login_required
def delete_screen(request, screen_id):
    """
    Delete a screen.
    """
    if request.method == "POST":
        screen = get_object_or_404(Screen, id=screen_id, owner=request.user)
        screen_name = screen.name
        screen.delete()
        messages.success(request, f'Screen "{screen_name}" deleted successfully')

    return redirect('screens')


@login_required
def assign_playlist(request, screen_id):
    """
    Assign a playlist to a screen.
    """
    screen = get_object_or_404(Screen, id=screen_id, owner=request.user)
    playlists = Playlist.objects.filter(owner=request.user)
    
    if request.method == "POST":
        playlist_id = request.POST.get('playlist_id')
        if playlist_id:
            playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
            screen.assigned_playlist = playlist
        else:
            screen.assigned_playlist = None
        screen.save()
        return redirect('dashboard')
    
    context = {
        'screen': screen,
        'playlists': playlists,
    }
    return render(request, 'assign_playlist.html', context)


@login_required
def create_playlist(request):
    """
    Create a new playlist.
    """
    if request.method == "POST":
        name = request.POST.get('name', 'New Playlist')
        description = request.POST.get('description', '')
        
        Playlist.objects.create(
            name=name,
            description=description,
            owner=request.user
        )
        
    return redirect('playlist_builder')


@login_required
def delete_playlist(request, playlist_id):
    """
    Delete a playlist.
    """
    if request.method == "POST":
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        playlist.delete()
        
    return redirect('playlist_builder')


@login_required
def save_playlist_settings(request):
    """
    Save global playlist settings for the user's store.
    """
    if request.method == "POST":
        # Get or create store profile for the user
        store, created = Store.objects.get_or_create(user=request.user)

        # Playback Defaults
        default_duration = request.POST.get('default_duration', 10)
        transition_effect = request.POST.get('transition_effect', 'fade')

        # Audio Configuration
        mute_by_default = request.POST.get('mute_by_default') == 'true'
        default_volume = request.POST.get('default_volume', 75)

        # Fallback Behavior
        fallback_type = request.POST.get('fallback_type', 'brand_logo')
        fallback_logo = request.POST.get('fallback_logo', '')

        # Update store settings
        store.default_image_duration = int(default_duration)
        store.transition_effect = transition_effect
        store.mute_by_default = mute_by_default
        store.default_volume = int(default_volume)
        store.fallback_type = fallback_type
        if fallback_logo:
            store.fallback_logo = fallback_logo
        store.save()

        messages.success(request, 'Playlist settings saved successfully.')

        # Return JSON for HTMX/JS or redirect for form submission
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)  # No content, just success

        return redirect('playlists_list')

    return redirect('playlists_list')


# =============================================================================
# Store CMS Views
# =============================================================================

@login_required
def store_cms(request):
    """
    Main Store CMS page listing all layouts and content.
    """
    layouts = StoreLayout.objects.filter(owner=request.user)
    contents = StoreContent.objects.filter(owner=request.user)
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6]
    
    context = {
        'layouts': layouts,
        'contents': contents,
        'media_items': media_items,
    }
    return render(request, 'store_cms.html', context)


@login_required
def store_cms_editor(request, layout_id=None):
    """
    Layout editor with drag-and-drop canvas.
    """
    if layout_id:
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
    else:
        # Create a new layout
        layout = StoreLayout.objects.create(
            name="Untitled Layout",
            owner=request.user
        )
        return redirect('store_cms_editor_edit', layout_id=layout.id)
    
    # Get all layouts for the "existing content" sidebar
    layouts = StoreLayout.objects.filter(owner=request.user)
    contents = StoreContent.objects.filter(owner=request.user)
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6]
    
    context = {
        'layout': layout,
        'layouts': layouts,
        'contents': contents,
        'media_items': media_items,
    }
    return render(request, 'store_cms.html', context)


@login_required
def store_cms_content(request, content_id=None):
    """
    Content editor for rich text content.
    """
    if content_id:
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)
    else:
        # Create new content
        content = StoreContent.objects.create(
            title="Untitled Content",
            owner=request.user
        )
        return redirect('store_cms_content_edit', content_id=content.id)
    
    # Get all content for the sidebar
    contents = StoreContent.objects.filter(owner=request.user)
    media_items = MediaAsset.objects.filter(owner=request.user).order_by('-created_at')[:6]
    
    context = {
        'content': content,
        'contents': contents,
        'media_items': media_items,
    }
    return render(request, 'store_cms_editor.html', context)


@login_required
def save_layout(request, layout_id):
    """
    HTMX endpoint to save layout data.
    """
    if request.method == "POST":
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
        
        # Update layout fields
        name = request.POST.get('name')
        if name:
            layout.name = name
        
        status = request.POST.get('status')
        if status in ['DRAFT', 'PUBLISHED', 'ARCHIVED']:
            layout.status = status
        
        # Save canvas data if provided (JSON)
        import json
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
    """
    HTMX endpoint to save content data.
    """
    if request.method == "POST":
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)
        
        # Update content fields
        title = request.POST.get('title')
        if title:
            content.title = title
        
        content_html = request.POST.get('content_html', '')
        content.content_html = content_html
        
        status = request.POST.get('status')
        if status in ['DRAFT', 'PUBLISHED', 'SCHEDULED', 'ARCHIVED']:
            content.status = status
        
        content.save()
        
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)
        
        messages.success(request, 'Content saved successfully.')
        return redirect('store_cms_content_edit', content_id=content.id)
    
    return redirect('store_cms')


@login_required
def delete_layout(request, layout_id):
    """
    Delete a layout.
    """
    if request.method == "POST":
        layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
        layout.delete()
        messages.success(request, 'Layout deleted.')
    
    return redirect('store_cms')


@login_required
def delete_content(request, content_id):
    """
    Delete content.
    """
    if request.method == "POST":
        content = get_object_or_404(StoreContent, id=content_id, owner=request.user)
        content.delete()
        messages.success(request, 'Content deleted.')
    
    return redirect('store_cms')
