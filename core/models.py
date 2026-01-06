from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

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
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    source = models.CharField(max_length=10, choices=SOURCES)

    # Instagram specific
    instagram_id = models.CharField(max_length=255, blank=True, null=True, unique=True, help_text="Instagram Media ID to prevent duplicates")

    # Metadata
    duration = models.IntegerField(default=10, help_text="Duration in seconds. Default 10s for images.")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.media_type} ({self.source}) - {self.created_at.strftime('%Y-%m-%d')}"

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

class PlaylistItem(models.Model):
    """
    Through-model linking Playlist to MediaAsset with an order.
    """
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='items')
    media = models.ForeignKey(MediaAsset, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)
    
    # Override constraints
    custom_duration = models.IntegerField(blank=True, null=True, help_text="Override media default duration")

    class Meta:
        ordering = ['position']

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
    api_token = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="Token for player API authentication")
    
    # Content
    assigned_playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_screens')
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_online(self):
        if not self.last_heartbeat:
            return False
        # Consider offline if no heartbeat in last 60 seconds
        return (timezone.now() - self.last_heartbeat).total_seconds() < 60

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
    scheduled_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'Store contents'
    
    
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
        return f"{self.user.username}'s Store"


class Notification(models.Model):
    TYPES = [
        ('INFO', 'Info'),
        ('SUCCESS', 'Success'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=TYPES, default='INFO')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"
