"""
CMS views, grouped by feature. URLconf code keeps using `from . import views`
and `views.<name>`, so everything public is re-exported here.
"""
from .account import configuration, support
from .dashboard import dashboard
from .media import (
    cms_content_library,
    delete_media,
    media_library,
    sync_instagram,
    upload_media,
)
from .playlists import (
    add_cms_to_playlist,
    add_to_playlist,
    assign_playlist_screens,
    create_playlist,
    delete_playlist,
    playlist_builder,
    playlist_list,
    remove_from_playlist,
    reorder_playlist,
    save_playlist_settings,
    update_playlist_item,
)
from .screens import (
    assign_playlist,
    delete_screen,
    screens,
    setup_screen,
    validate_pairing_code,
)
from .store_cms import (
    delete_content,
    delete_layout,
    preview_layout,
    save_content,
    save_layout,
    save_layout_snapshot,
    store_cms,
    store_cms_content,
    store_cms_editor,
)

__all__ = [
    'add_cms_to_playlist', 'add_to_playlist', 'assign_playlist', 'assign_playlist_screens',
    'cms_content_library', 'configuration', 'create_playlist', 'dashboard', 'delete_content',
    'delete_layout', 'delete_media', 'delete_playlist', 'delete_screen', 'media_library',
    'playlist_builder', 'playlist_list', 'preview_layout', 'remove_from_playlist',
    'reorder_playlist', 'save_content', 'save_layout', 'save_layout_snapshot',
    'save_playlist_settings', 'screens', 'setup_screen', 'store_cms', 'store_cms_content',
    'store_cms_editor', 'support', 'sync_instagram', 'update_playlist_item',
    'upload_media', 'validate_pairing_code',
]
