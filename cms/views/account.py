"""Store configuration and support tickets."""
import logging
import os
import zoneinfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from core.models import (
    Screen,
    Store,
    SupportTicket,
)

from ..utils import (
    is_valid_http_url,
)

logger = logging.getLogger(__name__)


def _timezone_choices():
    return sorted(zoneinfo.available_timezones()) or ['UTC']


@login_required
def configuration(request):
    """Manage store profile and system preferences."""
    store, _ = Store.objects.get_or_create(user=request.user)
    timezones = _timezone_choices()

    if request.method == "POST":
        # Store profile
        store.business_name = request.POST.get('business_name', '').strip()[:255]
        store.description = request.POST.get('description', '')
        store.phone_number = request.POST.get('phone_number', '').strip()[:20]

        tz = request.POST.get('timezone', 'UTC')
        store.timezone = tz if tz in timezones else 'UTC'

        logo_url = request.POST.get('logo_url', '').strip()
        if not logo_url:
            store.logo_url = ''
        elif is_valid_http_url(logo_url):
            store.logo_url = logo_url[:1024]
        else:
            messages.warning(request, 'Logo URL must be a valid http(s) URL; it was not changed.')

        # System preferences
        store.dark_mode = request.POST.get('dark_mode') == 'on'
        store.auto_lock = request.POST.get('auto_lock') == 'on'
        store.enable_beta = request.POST.get('enable_beta') == 'on'

        store.save()
        messages.success(request, 'Configuration saved successfully.')
        return redirect('configuration')

    screens_qs = list(Screen.objects.filter(owner=request.user))
    context = {
        'store': store,
        'total_screens': len(screens_qs),
        'active_screens': sum(1 for s in screens_qs if s.is_online),
        'plan_limit': settings.PLAN_SCREEN_LIMIT,
        'timezones': timezones,
        # Instagram sync uses one server-side account, so "connected" means it is configured.
        'instagram_configured': bool(os.environ.get('INSTAGRAM_USERNAME') and os.environ.get('INSTAGRAM_PASSWORD')),
    }
    return render(request, 'configuration.html', context)


@login_required
def support(request):
    """
    Support page with help center and ticket submission.
    """
    if request.method == 'POST':
        topic = request.POST.get('topic', 'other')
        urgency = request.POST.get('urgency', 'low')
        description = request.POST.get('description', '').strip()

        if topic not in dict(SupportTicket.TOPIC_CHOICES):
            topic = 'other'
        if urgency not in dict(SupportTicket.URGENCY_CHOICES):
            urgency = 'low'
        if not description:
            messages.error(request, 'Please describe your issue.')
            return redirect('support')

        ticket = SupportTicket.objects.create(
            user=request.user,
            topic=topic,
            urgency=urgency,
            description=description[:5000],
        )
        if settings.SUPPORT_EMAIL:
            try:
                send_mail(
                    subject=f'[HotCrowd support] [{urgency.upper()}] {topic} from {request.user.username}',
                    message=f'Ticket {ticket.id}\nUser: {request.user.username} <{request.user.email}>\n\n{ticket.description}',
                    from_email=None,
                    recipient_list=[settings.SUPPORT_EMAIL],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Failed to send support ticket email for %s", ticket.id)
        messages.success(request, 'Support ticket submitted successfully. We will contact you soon.')
        return redirect('support')

    return render(request, 'support.html')
