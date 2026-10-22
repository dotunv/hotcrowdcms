"""Store configuration and support tickets."""
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from core.models import (
    Screen,
    Store,
)

from ..forms import TIMEZONE_CHOICES, StoreConfigForm, SupportTicketForm, form_errors

logger = logging.getLogger(__name__)


@login_required
def configuration(request):
    """Manage store profile and system preferences."""
    store, _ = Store.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = StoreConfigForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuration saved successfully.')
        else:
            for message in form_errors(form):
                messages.error(request, message)
        return redirect('configuration')

    screens_qs = list(Screen.objects.filter(owner=request.user))
    context = {
        'store': store,
        'total_screens': len(screens_qs),
        'active_screens': sum(1 for s in screens_qs if s.is_online),
        'plan_limit': settings.PLAN_SCREEN_LIMIT,
        'timezones': [tz for tz, _ in TIMEZONE_CHOICES],
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
        form = SupportTicketForm(request.POST)
        if not form.is_valid():
            for message in form_errors(form):
                messages.error(request, message)
            return redirect('support')

        ticket = form.save(commit=False)
        ticket.user = request.user
        ticket.save()
        if settings.SUPPORT_EMAIL:
            try:
                send_mail(
                    subject=f'[HotCrowd support] [{ticket.urgency.upper()}] {ticket.topic} from {request.user.username}',
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
