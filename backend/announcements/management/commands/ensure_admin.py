"""Create or refresh the single admin account from environment variables.

Safe to run on every deploy: it is a no-op unless ADMIN_PASSWORD is set.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from announcements.models import Profile, profile_for

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update the hardcoded admin account from ADMIN_* env vars."

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_USERNAME", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")
        email = os.getenv("ADMIN_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write(
                "ADMIN_USERNAME / ADMIN_PASSWORD not set - skipping admin bootstrap."
            )
            return

        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email}
        )
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        # set_password hashes with Argon2 (first entry in PASSWORD_HASHERS).
        user.set_password(password)
        user.save()

        # The bootstrap account is an admin, and its password came from the
        # environment rather than an invite - so it is never mid-invite.
        profile = profile_for(user)
        profile.role = Profile.Role.ADMIN
        profile.must_change_password = False
        profile.temp_password_expires_at = None
        if profile.password_changed_at is None:
            profile.password_changed_at = timezone.now()
        profile.save(
            update_fields=[
                "role",
                "must_change_password",
                "temp_password_expires_at",
                "password_changed_at",
            ]
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS("{} admin user '{}'.".format(verb, username)))
