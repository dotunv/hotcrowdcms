from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),
    path('screens/', views.screens, name='screens'),
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
    # Playlist Management
    path('playlists/', views.playlist_list, name='playlists_list'),
    path('playlist/create/', views.create_playlist, name='create_playlist'),
    path('playlist/delete/<uuid:playlist_id>/', views.delete_playlist, name='delete_playlist'),
    # Screen Management
    path('screen/<uuid:screen_id>/assign/', views.assign_playlist, name='assign_playlist'),
]
