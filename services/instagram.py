"""
Instagram Integration Service.
Syncs media from Instagram hashtags and downloads files locally.
"""
import logging
import os

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from core.models import MediaAsset

logger = logging.getLogger(__name__)


class InstagramService:
    """
    Service for syncing media from Instagram.
    
    Uses instagrapi library for Instagram API access.
    Downloads media to local/cloud storage since Instagram URLs expire.
    """
    
    def __init__(self):
        self.cl = None
        self._logged_in = False
    
    def _ensure_logged_in(self):
        """Lazy login - only authenticate when needed."""
        if self._logged_in:
            return True
            
        username = os.environ.get('INSTAGRAM_USERNAME')
        password = os.environ.get('INSTAGRAM_PASSWORD')
        
        if not username or not password:
            logger.warning("Instagram credentials not configured")
            return False
        
        try:
            from instagrapi import Client
            self.cl = Client()
            self.cl.login(username, password)
            self._logged_in = True
            logger.info(f"Instagram login successful for {username}")
            return True
        except ImportError:
            logger.error("instagrapi package not installed")
            return False
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            return False
    
    MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024

    def download_media(self, url: str, user, media_type: str = 'IMAGE') -> tuple[str, str] | None:
        """
        Download media from URL and save to storage.
        Returns (file_url, storage_path) or None if download fails.
        """
        if not url.startswith(('http://', 'https://')):
            logger.warning("Refusing to download non-http(s) URL")
            return None
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            if len(response.content) > self.MAX_DOWNLOAD_BYTES:
                logger.warning("Instagram media too large, skipping")
                return None
            
            # Determine file extension
            content_type = response.headers.get('Content-Type', '')
            if 'video' in content_type:
                ext = '.mp4'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            else:
                ext = '.jpg'  # Default
            
            # Generate unique filename
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"media/{user.id}/instagram/{timestamp}{ext}"
            
            # Save to storage (local or cloud)
            path = default_storage.save(filename, ContentFile(response.content))
            file_url = default_storage.url(path)
            
            logger.info(f"Downloaded Instagram media to {path}")
            return file_url, path

        except Exception as e:
            logger.error(f"Failed to download media from {url}: {e}")
            return None
    
    def sync_hashtag(self, hashtag: str, user, limit: int = 20) -> int:
        """
        Fetches recent media for a hashtag and saves to MediaAsset.
        Downloads media to local storage so URLs don't expire.
        
        Returns the number of new media items synced.
        """
        if not self._ensure_logged_in():
            logger.warning("Cannot sync hashtag - not logged in")
            return 0
        
        try:
            # Remove # if present
            hashtag = hashtag.lstrip('#')
            
            medias = self.cl.hashtag_medias_top(hashtag, amount=limit)
            logger.info(f"Found {len(medias)} media items for #{hashtag}")
            
            synced_count = 0
            for media in medias:
                # Check if already exists
                if MediaAsset.objects.filter(owner=user, instagram_id=str(media.pk)).exists():
                    continue
                
                # Determine type and URL
                if media.media_type == 2:  # Video
                    m_type = 'VIDEO'
                    source_url = str(media.video_url) if media.video_url else None
                elif media.media_type == 8:  # Album/Carousel
                    # Take first item from album
                    if media.resources:
                        first = media.resources[0]
                        m_type = 'VIDEO' if first.video_url else 'IMAGE'
                        source_url = str(first.video_url or first.thumbnail_url)
                    else:
                        continue
                else:  # Image
                    m_type = 'IMAGE'
                    source_url = str(media.thumbnail_url) if media.thumbnail_url else None
                
                if not source_url:
                    continue
                
                # Download to local storage
                downloaded = self.download_media(source_url, user, m_type)
                if not downloaded:
                    logger.warning(f"Skipping media {media.pk} - download failed")
                    continue
                local_url, local_path = downloaded
                
                # Create asset with local URL
                MediaAsset.objects.create(
                    owner=user,
                    media_type=m_type,
                    source='INSTAGRAM',
                    instagram_id=str(media.pk),
                    file_url=local_url,
                    storage_path=local_path,
                    duration=15 if m_type == 'VIDEO' else 10
                )
                synced_count += 1
                logger.info(f"Synced Instagram media {media.pk} as {m_type}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"Failed to sync hashtag #{hashtag}: {e}")
            return 0


def sync_hashtag_media(tag: str, user) -> int:
    """
    Convenience function to sync media from a hashtag.
    Returns the number of new items synced.
    """
    service = InstagramService()
    return service.sync_hashtag(tag, user=user)
