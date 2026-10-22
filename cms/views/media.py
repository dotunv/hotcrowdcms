"""Media library, uploads and Instagram sync."""
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    MediaAsset,
    StoreContent,
)
from services.instagram import sync_hashtag_media

from ..utils import (
    HASHTAG_RE,
    is_valid_http_url,
    parse_int,
    safe_filename,
    sniff_media_type,
)
from ._helpers import (
    _is_ajax,
)

logger = logging.getLogger(__name__)


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

    if request.htmx:
        return render(request, 'partials/cms_content_picker.html', {'contents': contents})

    return HttpResponse(status=400)


def _upload_error(request, message, status=400):
    if _is_ajax(request):
        return JsonResponse({'status': 'error', 'message': message}, status=status)
    messages.error(request, message)
    return redirect('media_library')


@login_required
def upload_media(request):
    """Handle media upload (file or URL)."""
    if request.method != "POST":
        return redirect('media_library')

    uploaded_file = request.FILES.get('file')
    file_url = request.POST.get('file_url', '').strip()
    media_type = request.POST.get('media_type', 'IMAGE')
    if media_type not in ('IMAGE', 'VIDEO'):
        media_type = 'IMAGE'
    duration = parse_int(request.POST.get('duration'), 10, 1, 3600)
    name = request.POST.get('name', '').strip()[:255]
    storage_path = ''

    if uploaded_file:
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            return _upload_error(request, 'File size must be less than 200MB.')

        # Trust the file signature, not the client-supplied Content-Type.
        header = uploaded_file.read(16)
        uploaded_file.seek(0)
        sniffed = sniff_media_type(header)
        if sniffed is None:
            return _upload_error(request, 'Invalid file type. Use JPEG, PNG, GIF, MP4 or WebM.')
        media_type = sniffed[1]

        filename = (
            f"media/{request.user.id}/{timezone.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}_{safe_filename(uploaded_file.name)}"
        )
        try:
            # Passing the UploadedFile streams it to storage instead of loading it into memory.
            storage_path = default_storage.save(filename, uploaded_file)
            file_url = default_storage.url(storage_path)
        except Exception:
            logger.exception("Media upload failed for user %s", request.user.pk)
            return _upload_error(request, 'Upload failed. Please try again.', status=500)

    elif file_url:
        if not is_valid_http_url(file_url):
            return _upload_error(request, 'Please provide a valid http(s) URL.')
    else:
        return _upload_error(request, 'Please provide a file or URL.')

    MediaAsset.objects.create(
        owner=request.user,
        name=name or None,
        file_url=file_url,
        storage_path=storage_path,
        media_type=media_type,
        source='UPLOAD',
        duration=duration,
    )

    if _is_ajax(request):
        return JsonResponse({'status': 'success', 'url': file_url, 'name': name, 'type': media_type})

    messages.success(request, 'Media uploaded successfully!')
    return redirect('media_library')


@login_required
def delete_media(request, media_id):
    """Delete a media asset and the file we host for it."""
    if request.method == "POST":
        media = get_object_or_404(MediaAsset, id=media_id, owner=request.user)
        media.delete_stored_file()
        media.delete()
    return redirect('media_library')


@login_required
def sync_instagram(request):
    """
    Sync media from Instagram hashtag.
    Downloads media to local storage so URLs don't expire.
    """
    if request.method == "POST":
        tag = request.POST.get('hashtag', '').strip().lstrip('#')

        if not tag:
            messages.error(request, 'Please provide a hashtag.')
            return redirect('playlist_builder')
        if not HASHTAG_RE.match(tag):
            messages.error(request, 'Hashtags can only contain letters, numbers and underscores.')
            return redirect('playlist_builder')

        try:
            synced_count = sync_hashtag_media(tag, request.user)

            if synced_count > 0:
                messages.success(request, f'Successfully synced {synced_count} media items from #{tag}')
            else:
                messages.warning(
                    request,
                    f'No new media found for #{tag}. All media may already be synced, '
                    'Instagram credentials may not be configured, or the hashtag has no recent posts.'
                )
        except Exception:
            logger.exception("Instagram sync failed for #%s", tag)
            messages.error(request, 'Instagram sync failed. Please try again later.')

    return redirect('playlist_builder')
