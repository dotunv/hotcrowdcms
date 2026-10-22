"""Screen management and pairing."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import (
    PairingCode,
    Playlist,
    Screen,
)

logger = logging.getLogger(__name__)


@login_required
def screens(request):
    """List all screens with their status."""
    screens_list = list(Screen.objects.filter(owner=request.user).select_related('assigned_playlist'))
    online = sum(1 for s in screens_list if s.is_online)

    context = {
        'screens': screens_list,
        'total_screens': len(screens_list),
        'online_screens': online,
        'offline_screens': len(screens_list) - online,
    }
    return render(request, 'screens.html', context)


@login_required
@require_GET
def validate_pairing_code(request):
    """Validate a pairing code via AJAX."""
    code = request.GET.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'valid': False, 'message': 'Please enter a code.'})

    pairing = PairingCode.objects.filter(code=code).first()
    if pairing is None:
        return JsonResponse({'valid': False, 'message': 'Invalid pairing code.'})
    if timezone.now() > pairing.expires_at:
        return JsonResponse({'valid': False, 'message': 'This code has expired.'})
    if Screen.objects.filter(pairing_code=code).exists():
        return JsonResponse({'valid': False, 'message': 'This code is already in use.'})
    return JsonResponse({'valid': True})


@login_required
def setup_screen(request):
    """Handle screen creation (POST only). Redirects to the screens page on success/error."""
    if request.method != "POST":
        return redirect('screens')

    code = request.POST.get('pairing_code', '').strip().upper()
    name = request.POST.get('name', '').strip()[:255]
    location = request.POST.get('location', '').strip()[:255]

    if not name:
        messages.error(request, 'Please give the screen a name.')
        return redirect('screens')

    if Screen.objects.filter(owner=request.user).count() >= settings.PLAN_SCREEN_LIMIT:
        messages.error(request, f'Your plan allows up to {settings.PLAN_SCREEN_LIMIT} screens.')
        return redirect('screens')

    try:
        with transaction.atomic():
            # Lock the code row so two simultaneous claims can't both succeed.
            pairing = PairingCode.objects.select_for_update().filter(code=code).first()
            if pairing is None:
                messages.error(request, 'Invalid pairing code.')
                return redirect('screens')
            if timezone.now() > pairing.expires_at:
                messages.error(request, 'This pairing code has expired.')
                return redirect('screens')
            if Screen.objects.filter(pairing_code=code).exists():
                messages.error(request, 'This code is already linked.')
                return redirect('screens')

            Screen.objects.create(
                name=name,
                pairing_code=code,
                location=location,
                owner=request.user,
                status='OFFLINE',  # becomes ONLINE with the first heartbeat
            )
    except IntegrityError:
        messages.error(request, 'This code is already linked.')
        return redirect('screens')

    messages.success(request, f'Screen "{name}" connected successfully!')
    return redirect('screens')


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
        screen.save(update_fields=['assigned_playlist'])
        return redirect('dashboard')

    return render(request, 'assign_playlist.html', {'screen': screen, 'playlists': playlists})
