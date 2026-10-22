import hashlib
import secrets
import uuid
import zoneinfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

DEFAULT_CONTENT_DURATION = 15  # seconds, for items without any duration set

class Store(models.Model):
    """
    Profile for the Store Owner (User). 
    We extend the built-in User model using a OneToOneField.
    """
    TRANSITION_EFFECTS = [
        ('fade', 'Fade'),
        ('slide', 'Slide'),
        ('zoom', 'Zoom'),
        ('none', 'None'),
    ]

    FALLBACK_TYPES = [
        ('brand_logo', 'Brand Logo'),
        ('custom_media', 'Custom Media'),
        ('black_screen', 'Black Screen'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='store_profile')
    business_name = models.CharField(max_length=255, blank=True)
    branding_color = models.CharField(max_length=7, default='#22c55e')  # Hex code
    
    # Extended Profile
    description = models.TextField(blank=True, help_text="Internal description of the store")
    phone_number = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    logo_url = models.URLField(max_length=1024, blank=True, null=True, help_text="URL to store logo")

    # System Preferences
    dark_mode = models.BooleanField(default=False)
    auto_lock = models.BooleanField(default=False)
    enable_beta = models.BooleanField(default=False)

    # Integrations
    instagram_connected = models.BooleanField(default=False)
    facebook_connected = models.BooleanField(default=False)
    tiktok_connected = models.BooleanField(default=False)

    # Playlist Settings - Playback Defaults
    default_image_duration = models.PositiveIntegerField(default=10, help_text="Default duration for images in seconds")
    transition_effect = models.CharField(max_length=10, choices=TRANSITION_EFFECTS, default='fade')

    # Playlist Settings - Audio Configuration
    mute_by_default = models.BooleanField(default=False)
    default_volume = models.PositiveIntegerField(default=75, help_text="Default volume percentage (0-100)")

    # Playlist Settings - Fallback Behavior
    fallback_type = models.CharField(max_length=20, choices=FALLBACK_TYPES, default='brand_logo')
    fallback_logo = models.URLField(max_length=1024, blank=True, null=True, help_text="URL to fallback logo image")

    def __str__(self):
        return self.business_name or self.user.username

    @property
    def initials(self):
        """Returns initials for the store logo placeholder."""
        name = self.business_name or self.user.username
        if not name:
            return "LM"
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper()

class MediaAsset(models.Model):
    MEDIA_TYPES = [
        ('VIDEO', 'Video'),
        ('IMAGE', 'Image'),
    ]
    SOURCES = [
        ('UPLOAD', 'Manual Upload'),
        ('INSTAGRAM', 'Instagram'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='media_assets')
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional name for the media")
    file_url = models.URLField(max_length=1024, help_text="Direct URL to the file or Instagram media")
    storage_path = models.CharField(
        max_length=1024, blank=True, default='',
        help_text="Path in default storage for files we host; used to delete the file with the asset",
    )
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    source = models.CharField(max_length=10, choices=SOURCES)

    # Instagram specific
    instagram_id = models.CharField(max_length=255, blank=True, null=True, help_text="Instagram Media ID to prevent duplicates (per owner)")

    # Metadata
    duration = models.IntegerField(default=10, help_text="Duration in seconds. Default 10s for images.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['owner', '-created_at'])]
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'instagram_id'],
                name='mediaasset_unique_instagram_id_per_owner',
            )
        ]

    def __str__(self):
        return f"{self.media_type} ({self.source}) - {self.created_at.strftime('%Y-%m-%d')}"

    def delete_stored_file(self):
        """Remove the hosted file (if we host it) from storage."""
        if self.storage_path:
            from django.core.files.storage import default_storage
            try:
                default_storage.delete(self.storage_path)
            except Exception:  # storage errors must not block DB cleanup
                import logging
                logging.getLogger(__name__).exception("Failed to delete %s", self.storage_path)

class Playlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('SCHEDULED', 'Scheduled'),
        ('ARCHIVED', 'Archived'),
    ]

    SCHEDULE_TYPES = [
        ('ALWAYS', 'Always On'),
        ('SCHEDULED', 'Scheduled'),
    ]

    TRANSITION_EFFECTS = [
        ('NONE', 'None'),
        ('FADE', 'Fade'),
        ('SLIDE', 'Slide'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    
    # Settings
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    schedule_type = models.CharField(max_length=10, choices=SCHEDULE_TYPES, default='ALWAYS')
    
    # Schedule details (only used if schedule_type is SCHEDULED)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    
    # Playback settings
    transition_effect = models.CharField(max_length=10, choices=TRANSITION_EFFECTS, default='FADE')
    is_loop = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def total_duration(self):
        """Total running time in seconds. Uses prefetched items when available."""
        return sum(item.effective_duration for item in self.items.all())

    def is_scheduled_now(self, now=None, tz_name='UTC'):
        """
        Whether the playlist should be playing at `now`.
        Archived playlists never play; ALWAYS playlists always do;
        SCHEDULED playlists play inside their date/time window (evaluated in the store's timezone).
        """
        if self.status == 'ARCHIVED':
            return False
        if self.schedule_type != 'SCHEDULED':
            return True
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            tz = zoneinfo.ZoneInfo('UTC')
        local = (now or timezone.now()).astimezone(tz)
        if self.start_date and local.date() < self.start_date:
            return False
        if self.end_date and local.date() > self.end_date:
            return False
        if self.start_time and self.end_time:
            t = local.time()
            if self.start_time <= self.end_time:
                return self.start_time <= t <= self.end_time
            return t >= self.start_time or t <= self.end_time  # window crosses midnight
        if self.start_time and local.time() < self.start_time:
            return False
        if self.end_time and local.time() > self.end_time:
            return False
        return True


class PlaylistItem(models.Model):
    """
    Through-model linking Playlist to MediaAsset with an order.
    """
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='items')
    media = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, null=True, blank=True)
    store_content = models.ForeignKey('StoreContent', on_delete=models.CASCADE, null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    # Override constraints
    custom_duration = models.IntegerField(blank=True, null=True, help_text="Override media default duration")

    @property
    def effective_duration(self):
        if self.custom_duration:
            return self.custom_duration
        if self.media is not None:
            return self.media.duration
        if self.store_content is not None:
            return self.store_content.duration
        return DEFAULT_CONTENT_DURATION

    def clean(self):
        if self.media is None and self.store_content is None:
            raise ValidationError("A PlaylistItem must have either a media asset or store content.")
        if self.media is not None and self.store_content is not None:
            raise ValidationError("A PlaylistItem cannot have both a media asset and store content.")

    class Meta:
        ordering = ['position']
        constraints = [
            models.CheckConstraint(
                name="playlistitem_has_exactly_one_content",
                condition=(
                    models.Q(media__isnull=False, store_content__isnull=True) |
                    models.Q(media__isnull=True, store_content__isnull=False)
                ),
            )
        ]

    def __str__(self):
        return f"{self.playlist.name} - Item {self.position}"

class Screen(models.Model):
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='screens')
    
    # Device pairing
    pairing_code = models.CharField(max_length=6, blank=True, null=True, unique=True)
    location = models.CharField(max_length=255, blank=True, help_text="Physical location of the screen")
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OFFLINE')
    last_heartbeat = models.DateTimeField(blank=True, null=True)
    
    # API Authentication
    api_token = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="SHA-256 hash of the player API token (the raw token is never stored)")
    
    # Content
    assigned_playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_screens')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    ONLINE_TIMEOUT_SECONDS = 60

    @classmethod
    def online_cutoff(cls):
        return timezone.now() - timezone.timedelta(seconds=cls.ONLINE_TIMEOUT_SECONDS)

    @property
    def is_online(self):
        if not self.last_heartbeat:
            return False
        # Consider offline if no heartbeat in the last ONLINE_TIMEOUT_SECONDS
        return (timezone.now() - self.last_heartbeat).total_seconds() < self.ONLINE_TIMEOUT_SECONDS

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def issue_api_token(self):
        """
        Create a new API token, store only its hash, and return the raw token.
        The raw token is shown to the device once and cannot be recovered afterwards.
        """
        raw = secrets.token_hex(32)
        self.api_token = self.hash_token(raw)
        self.save(update_fields=['api_token'])
        return raw

    def __str__(self):
        return self.name

class PairingCode(models.Model):
    """
    Temporary codes generated by the Screen (Player App) to show on screen.
    The User enters this code in the CMS to 'claim' the screen.
    """
    code = models.CharField(max_length=6, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optionally link to a pre-created screen entry if we went that route, 
    # but usually the Screen is created upon successful pairing.
    # For this architecture: Player generates code -> Sends to API -> API stores PairingCode.
    # User inputs Code -> API finds PairingCode -> Creates Screen(owner=User).
    
    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return self.code


class StoreLayout(models.Model):
    """
    Visual layout for digital signage displays.
    Stores canvas elements as JSON for drag-and-drop editor.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_layouts')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    
    # Canvas settings
    layout_data = models.JSONField(default=dict, help_text="JSON data for canvas elements")
    canvas_width = models.IntegerField(default=1920)
    canvas_height = models.IntegerField(default=1080)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class StoreContent(models.Model):
    """
    Rich text content for store displays.
    Used in the Content Editor for creating promotional messages.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('SCHEDULED', 'Scheduled'),
        ('ARCHIVED', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_contents')
    content_html = models.TextField(blank=True, help_text="Rich text HTML content")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    
    # Scheduling
    duration = models.IntegerField(default=15, help_text="Duration in seconds")
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    target_screen = models.ForeignKey('Screen', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_contents')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'Store contents'

    def is_live_for(self, screen, now=None):
        """Published, inside its date window and targeted at this screen (or all screens)."""
        now = now or timezone.now()
        if self.status != 'PUBLISHED':
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return self.target_screen_id is None or self.target_screen_id == screen.id

    def __str__(self):
        return self.title

class SupportTicket(models.Model):
    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    TOPIC_CHOICES = [
        ('technical', 'Technical Issue'),
        ('billing', 'Billing'),
        ('account', 'Account Management'),
        ('feature', 'Feature Request'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    topic = models.CharField(max_length=20, choices=TOPIC_CHOICES, default='other')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='low')
    description = models.TextField()
    status = models.CharField(max_length=20, default='OPEN') # OPEN, CLOSED, PENDING
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.urgency.upper()}] {self.topic} - {self.user.username}"



