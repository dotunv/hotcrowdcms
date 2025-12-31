from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from core.models import Screen, Playlist, MediaAsset, PlaylistItem
from django.utils import timezone
from services.instagram import sync_hashtag_media


@login_required
def dashboard(request):
    """
    Shows list of screens and their status.
    """
    screens = Screen.objects.filter(owner=request.user).order_by('-created_at')
    playlists = Playlist.objects.filter(owner=request.user)
    media_assets = MediaAsset.objects.filter(owner=request.user)
    
    # Calculate stats
    total_screens = screens.count()
    online_screens = sum(1 for s in screens if s.is_online)
    total_playlists = playlists.count()
    total_media = media_assets.count()
    
    context = {
        'screens': screens,
        'total_screens': total_screens,
        'online_screens': online_screens,
        'offline_screens': total_screens - online_screens,
        'total_playlists': total_playlists,
        'total_media': total_media,
        'playlists': playlists,
    }
    return render(request, 'dashboard.html', context)


@login_required
def setup_screen(request):
    """
    Form to manually add a screen via pairing code entered by Store Owner.
    """
    if request.method == "POST":
        code = request.POST.get('pairing_code')
        name = request.POST.get('name')
        
        # Create screen with the authenticated user as owner
        Screen.objects.create(
            name=name,
            pairing_code=code,
            owner=request.user
        )
        return redirect('dashboard')
        
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
        playlist = playlists.first()
    
    # Create a default playlist if none exists
    if not playlist:
        playlist = Playlist.objects.create(name="Default Playlist", owner=request.user)
    
    context = {
        'media_items': media_items,
        'playlist': playlist,
        'playlists': playlists,
    }
    return render(request, 'playlist_builder.html', context)


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
        context = {'playlist': playlist}
        return render(request, 'partials/playlist_items.html', context)

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
        
    return redirect('playlist_builder')


@login_required
def remove_from_playlist(request, item_id):
    """
    Removes a media item from a playlist.
    """
    if request.method == "POST":
        item = get_object_or_404(PlaylistItem, id=item_id, playlist__owner=request.user)
        item.delete()
        
    return redirect('playlist_builder')


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
    Handle media upload.
    """
    if request.method == "POST":
        file_url = request.POST.get('file_url')
        media_type = request.POST.get('media_type', 'IMAGE')
        duration = int(request.POST.get('duration', 10))
        
        if file_url:
            MediaAsset.objects.create(
                owner=request.user,
                file_url=file_url,
                media_type=media_type,
                source='UPLOAD',
                duration=duration
            )
            
    return redirect('media_library')


@login_required
def delete_media(request, media_id):
    """
    Delete a media asset.
    """
    if request.method == "POST":
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)
        media.delete()
        
    return redirect('media_library')


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
