from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),
    path('screens/', views.screens, name='screens'),
    path('configuration/', views.configuration, name='configuration'),
    path('support/', views.support, name='support'),
    path('setup-screen/', views.setup_screen, name='setup_screen'),
    path('builder/', views.playlist_builder, name='playlist_builder'),
    path('sync-ig/', views.sync_instagram, name='sync_instagram'),
    path('add-media/<uuid:media_id>/', views.add_to_playlist, name='add_to_playlist'),
    path('remove-item/<int:item_id>/', views.remove_from_playlist, name='remove_from_playlist'),
    path('update-item/<int:item_id>/', views.update_playlist_item, name='update_playlist_item'),
    path('api/reorder/', views.reorder_playlist, name='reorder_playlist'),
    # Media Library
    path('media/', views.media_library, name='media_library'),
    path('media/upload/', views.upload_media, name='upload_media'),
    path('media/delete/<uuid:media_id>/', views.delete_media, name='delete_media'),
    path('media/cms-content/', views.cms_content_library, name='cms_content_library'),
    path('add-cms/<uuid:content_id>/', views.add_cms_to_playlist, name='add_cms_to_playlist'),
    # Playlist Management
    path('playlists/', views.playlist_list, name='playlists_list'),
    path('playlist/create/', views.create_playlist, name='create_playlist'),
    path('playlist/delete/<uuid:playlist_id>/', views.delete_playlist, name='delete_playlist'),
    path('playlist/settings/', views.save_playlist_settings, name='save_playlist_settings'),
    # Screen Management
    path('screen/<uuid:screen_id>/assign/', views.assign_playlist, name='assign_playlist'),
    path('screen/<uuid:screen_id>/delete/', views.delete_screen, name='delete_screen'),
    # Store CMS
    path('store-cms/', views.store_cms, name='store_cms'),
    path('store-cms/layout/', views.store_cms_editor, name='store_cms_editor'),
    path('store-cms/layout/<uuid:layout_id>/', views.store_cms_editor, name='store_cms_editor_edit'),
    path('store-cms/layout/<uuid:layout_id>/preview/', views.preview_layout, name='preview_layout'),
    path('store-cms/layout/<uuid:layout_id>/snapshot/', views.save_layout_snapshot, name='save_layout_snapshot'),
    path('store-cms/layout/<uuid:layout_id>/save/', views.save_layout, name='save_layout'),
    path('store-cms/layout/<uuid:layout_id>/delete/', views.delete_layout, name='delete_layout'),
    path('store-cms/content/', views.store_cms_content, name='store_cms_content'),
    path('store-cms/content/<uuid:content_id>/', views.store_cms_content, name='store_cms_content_edit'),
    path('store-cms/content/<uuid:content_id>/save/', views.save_content, name='save_content'),
    path('store-cms/content/<uuid:content_id>/delete/', views.delete_content, name='delete_content'),
]

