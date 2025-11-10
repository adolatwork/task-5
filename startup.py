import os
import django
from django.core.management import call_command
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# Run migrations
call_command("migrate", interactive=False)
print("✅ Migrations applied successfully!")

# Collect static files
call_command("collectstatic", verbosity=0, clear=True, no_input=True)
print("✅ Static files collected successfully!")


# Create superuser if not exists
USERNAME = os.environ.get("USERNAME", "test_user")
SUPERUSER_PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "password")

User = get_user_model()
if not User.objects.filter(username=USERNAME).exists():
    User.objects.create_superuser(
        username=USERNAME,
        password=SUPERUSER_PASSWORD
    )
    print("✅ Superuser created successfully!")
else:
    print("ℹ️ Superuser already exists.")
