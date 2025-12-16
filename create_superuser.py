import os
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus_core.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'MYBOSS')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'regarwrecks@gmail.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Nandini')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser: {username}")
    User.objects.create_superuser(username, email, password)
    print("Superuser created successfully!")
else:
    print(f"Superuser '{username}' already exists. Skipping.")