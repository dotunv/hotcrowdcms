"""Store CMS: layouts and rich-text content."""
import json
import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    MediaAsset,
    Screen,
    StoreContent,
    StoreLayout,
)
from services.sanitize import sanitize_html

from ..utils import (
    parse_aware_datetime,
    parse_int,
    parse_uuid,
    sniff_media_type,
)

logger = logging.getLogger(__name__)


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
        'scheduled_count': contents.filter(status='SCHEDULED').count(),
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
        'screens': Screen.objects.filter(owner=request.user),
    }
    return render(request, 'store_cms_editor.html', context)


@login_required
def save_layout(request, layout_id):
    """Save layout data via HTMX."""
    if request.method != "POST":
        return redirect('store_cms')

    layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)

    name = request.POST.get('name') or request.POST.get('layout_name')
    if name:
        layout.name = name.strip()[:255]

    status = request.POST.get('status')
    if status in dict(StoreLayout.STATUS_CHOICES):
        layout.status = status

    layout_data = request.POST.get('layout_data')
    if layout_data:
        try:
            parsed = json.loads(layout_data)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'layout_data is not valid JSON'}, status=400)
        if not isinstance(parsed, (dict, list)):
            return JsonResponse({'status': 'error', 'message': 'layout_data must be an object or list'}, status=400)
        layout.layout_data = parsed

    layout.canvas_width = parse_int(request.POST.get('canvas_width'), layout.canvas_width, 100, 8192)
    layout.canvas_height = parse_int(request.POST.get('canvas_height'), layout.canvas_height, 100, 8192)

    layout.save()

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)

    messages.success(request, 'Layout saved successfully.')
    return redirect('store_cms_editor_edit', layout_id=layout.id)


@login_required
def save_content(request, content_id):
    """Save content data via HTMX."""
    if request.method != "POST":
        return redirect('store_cms')

    content = get_object_or_404(StoreContent, id=content_id, owner=request.user)

    title = request.POST.get('title')
    if title:
        content.title = title.strip()[:255]

    # Rich text comes from a contenteditable element: never store it unsanitized.
    content.content_html = sanitize_html(request.POST.get('content_html', ''))

    status = request.POST.get('status')
    if status in dict(StoreContent.STATUS_CHOICES):
        content.status = status

    # Scheduling
    content.duration = parse_int(request.POST.get('duration'), content.duration, 1, 3600)
    content.start_date = parse_aware_datetime(request.POST.get('start_date'))
    content.end_date = parse_aware_datetime(request.POST.get('end_date'))

    target = request.POST.get('target_screen')
    if target:
        if target == 'all':
            content.target_screen = None
        else:
            target_uuid = parse_uuid(target)
            if target_uuid is None:
                return JsonResponse({'status': 'error', 'message': 'Invalid target screen'}, status=400)
            # Only screens the user owns may be targeted.
            content.target_screen = get_object_or_404(Screen, id=target_uuid, owner=request.user)

    content.save()

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)

    messages.success(request, 'Content saved successfully.')
    return redirect('store_cms_content_edit', content_id=content.id)


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


MAX_SNAPSHOT_SIZE = 20 * 1024 * 1024


@login_required
def save_layout_snapshot(request, layout_id):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)
    image_data = request.FILES.get('image')

    if not image_data:
        return JsonResponse({'status': 'error', 'message': 'No image data provided'}, status=400)
    if image_data.size > MAX_SNAPSHOT_SIZE:
        return JsonResponse({'status': 'error', 'message': 'Snapshot is too large'}, status=400)
    sniffed = sniff_media_type(image_data.read(16))
    image_data.seek(0)
    if sniffed is None or sniffed[1] != 'IMAGE':
        return JsonResponse({'status': 'error', 'message': 'Snapshot must be an image'}, status=400)

    now = datetime.now()
    ext = {'image/jpeg': 'jpg', 'image/gif': 'gif'}.get(sniffed[0], 'png')
    filename = f"media/{request.user.id}/snapshots/{layout.id}_{now.strftime('%Y%m%d_%H%M%S')}.{ext}"

    try:
        path = default_storage.save(filename, image_data)
        file_url = default_storage.url(path)
        media = MediaAsset.objects.create(
            owner=request.user,
            name=f"Snapshot - {layout.name} - {now.strftime('%Y-%m-%d %H:%M')}"[:255],
            media_type='IMAGE',
            source='UPLOAD',
            file_url=file_url,
            storage_path=path,
            duration=10,
        )
    except Exception:
        logger.exception("Layout snapshot failed for layout %s", layout.id)
        return JsonResponse({'status': 'error', 'message': 'Could not save snapshot'}, status=500)

    return JsonResponse({
        'status': 'success',
        'message': 'Snapshot saved to Media Library',
        'media_id': str(media.id),
        'url': file_url,
    })


@login_required
def preview_layout(request, layout_id):
    layout = get_object_or_404(StoreLayout, id=layout_id, owner=request.user)

    context = {
        'layout': layout,
        'layout_data_json': json.dumps(layout.layout_data, cls=DjangoJSONEncoder)
    }
    return render(request, 'store_cms_preview.html', context)
