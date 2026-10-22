from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PairingCode, Screen


class Command(BaseCommand):
    help = "Mark screens without a recent heartbeat OFFLINE and purge expired pairing codes. Run every minute or so."

    def handle(self, *args, **options):
        stale = Screen.objects.filter(status='ONLINE').exclude(last_heartbeat__gte=Screen.online_cutoff())
        marked = stale.update(status='OFFLINE')
        purged, _ = PairingCode.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f"Marked {marked} screen(s) offline, purged {purged} expired pairing code(s).")
