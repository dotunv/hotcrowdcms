from instagrapi import Client
from django.conf import settings
from core.models import MediaAsset
from django.core.files.base import ContentFile
import requests
from urllib.parse import urlparse
import os

class InstagramService:
    def __init__(self):
        self.cl = Client()
        # Login logic - for now we might use session or delay login
        # self.cl.login(settings.INSTALLED_APPS_..., ...)
        pass

    def login(self, username, password):
        self.cl.login(username, password)

    def sync_hashtag(self, hashtag: str, limit: int = 20, user=None):
        """
        Fetches recent media for a hashtag and saves to MediaAsset.
        """
        medias = self.cl.hashtag_medias_top(hashtag, amount=limit)
        
        synced_count = 0
        for media in medias:
            # Check if exists
            if MediaAsset.objects.filter(instagram_id=media.pk).exists():
                continue
                
            # Determine type
            m_type = 'IMAGE'
            if media.media_type == 2: # Video
                m_type = 'VIDEO'
            elif media.media_type == 8: # Album
                # Simplify: take first item or ignore
                pass
                
            # Get URL
            url = media.thumbnail_url if m_type == 'IMAGE' else media.video_url
            if not url:
                continue

            # In production, we should download the file to local storage 
            # because IG links expire. For MVP, we'll store the direct link 
            # OR download it.
            # Let's download for robustness if "Manual Upload" logic exists, 
            # but for "Auto-Sync" usually we want to host it.
            
            # Create Asset
            asset = MediaAsset(
                owner=user, # Assign to store owner
                media_type=m_type,
                source='INSTAGRAM',
                instagram_id=media.pk,
                duration=15 if m_type == 'VIDEO' else 10,
                file_url=str(url) # Temporary: direct link
            )
            asset.save()
            synced_count += 1
            
        return synced_count

def sync_hashtag_media(tag: str, user):
    service = InstagramService()
    # Ensure login elsewhere or pass credentials
    # service.login(settings.IG_USER, settings.IG_PASS) 
    return service.sync_hashtag(tag, user=user)
