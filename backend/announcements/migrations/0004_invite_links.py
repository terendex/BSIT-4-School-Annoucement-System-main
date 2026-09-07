"""Invites become links instead of temporary passwords.

Nobody - not the admin who sends it, not the mail server, not a chat log -
ever holds the publisher's password. The link carries a single-use token; the
publisher opens it and chooses their own credential.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("announcements", "0003_announcement_category_announcement_year_level_and_more"),
    ]

    operations = [
        # A rename rather than drop-and-add, so any invite already in flight
        # keeps its expiry.
        migrations.RenameField(
            model_name="profile",
            old_name="temp_password_expires_at",
            new_name="invite_expires_at",
        ),
        migrations.AddField(
            model_name="profile",
            name="invite_token_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
