import os
import sys
import django
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import StoreLayout

print("--- Checking StoreLayouts ---")
layouts = StoreLayout.objects.all()
print(f"Total layouts found: {layouts.count()}")

for layout in layouts:
    print(f"\nID: {layout.id}")
    print(f"Name: {layout.name}")
    print(f"Owner: {layout.owner.username}")
    print(f"Status: {layout.status}")
    print(f"Layout Data Type: {type(layout.layout_data)}")
    
    data = layout.layout_data
    print(f"Full Data: {json.dumps(data, indent=2)}")

print("\n--- End Check ---")
