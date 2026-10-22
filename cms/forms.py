"""Forms that own validation for the CMS settings pages (views just call is_valid())."""
import zoneinfo

from django import forms
from django.core.exceptions import ValidationError

from core.models import Store, SupportTicket

from .utils import is_valid_http_url

TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(zoneinfo.available_timezones())] or [('UTC', 'UTC')]


def form_errors(form):
    """Flatten a form's errors into short human-readable messages."""
    messages = []
    for field, errors in form.errors.items():
        label = form.fields[field].label or field.replace('_', ' ').capitalize() if field in form.fields else ''
        for error in errors:
            messages.append(f'{label}: {error}' if label else str(error))
    return messages


class SupportTicketForm(forms.ModelForm):
    description = forms.CharField(
        max_length=5000, strip=True, error_messages={'required': 'Please describe your issue.'},
    )

    class Meta:
        model = SupportTicket
        fields = ['topic', 'urgency', 'description']


class StoreConfigForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)
    logo_url = forms.URLField(required=False, max_length=1024, assume_scheme='https')

    class Meta:
        model = Store
        fields = [
            'business_name', 'description', 'phone_number', 'timezone', 'logo_url',
            'dark_mode', 'auto_lock', 'enable_beta',
        ]

    def clean_logo_url(self):
        url = self.cleaned_data.get('logo_url') or ''
        if url and not is_valid_http_url(url):
            raise ValidationError('Enter a valid http(s) URL.')
        return url
