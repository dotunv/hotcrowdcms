from django import template
from django.utils.safestring import mark_safe

from services.sanitize import sanitize_html

register = template.Library()


@register.filter
def clean_html(value):
    """Sanitize user-authored rich text before marking it safe for output."""
    return mark_safe(sanitize_html(value))


# (label, url name, material icon, url names that mark the item active)
_NAV = [
    ('Main', [
        ('Dashboard', 'dashboard', 'dashboard', {'dashboard', 'dashboard_alt'}),
        ('Screens & Devices', 'screens', 'monitor', {'screens'}),
        ('Playlists', 'playlists_list', 'featured_play_list', {'playlists_list', 'playlist_builder'}),
    ]),
    ('Content', [
        ('Media Library', 'media_library', 'cloud_upload', {'media_library'}),
        ('Store CMS', 'store_cms', 'storefront', None),  # active for any store_cms* url
    ]),
    ('Settings', [
        ('Configuration', 'configuration', 'settings', {'configuration'}),
        ('Support', 'support', 'help', {'support'}),
    ]),
]


@register.simple_tag(takes_context=True)
def sidebar_nav(context):
    """Navigation sections for the sidebar with the active item resolved once, here, not in the template."""
    request = context.get('request')
    current = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    sections = []
    for title, items in _NAV:
        rows = []
        for label, url_name, icon, active_names in items:
            active = current.startswith('store_cms') if active_names is None else current in active_names
            rows.append({'label': label, 'url_name': url_name, 'icon': icon, 'active': active})
        sections.append({'title': title, 'items': rows})
    return sections
