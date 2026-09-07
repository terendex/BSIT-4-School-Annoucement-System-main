"""Restore announcements exported from a running service.

Written for one specific job: the service ran on container-local SQLite before
a real database was attached, so the posts live only in the old container and
are reachable only through its public API. Export them with

    python manage.py export_announcements --api https://your-service/ --out backup.json

then, once DATABASE_URL points at Postgres, put them back with

    python manage.py import_announcements backup.json

Images are not re-uploaded. They are already on Cloudinary and stay there; only
the rows that point at them are rebuilt. Re-running is safe - an announcement
whose slug already exists is skipped, not duplicated.
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from announcements.models import Announcement, Attachment

# https://res.cloudinary.com/<cloud>/image/upload/v123/<public_id>.<ext>
# The public id is what a later delete needs to remove the file from Cloudinary,
# and it is not part of the exported JSON - so recover it from the URL.
_CLOUDINARY_URL = re.compile(r"/upload/(?:v\d+/)?(?P<public_id>.+?)(?:\.[a-zA-Z0-9]+)?$")


def public_id_from(url: str) -> str:
    if "res.cloudinary.com" not in url:
        return ""
    match = _CLOUDINARY_URL.search(url)
    return match.group("public_id") if match else ""


class Command(BaseCommand):
    help = "Restore announcements and their attachments from an export file."

    def add_arguments(self, parser):
        parser.add_argument("path", help="The JSON file written by export_announcements.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be restored without writing anything.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError("No such file: {}".format(path))

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise CommandError("{} is not valid JSON: {}".format(path, error))

        records = payload.get("announcements")
        if not isinstance(records, list):
            raise CommandError("Expected an 'announcements' list in {}.".format(path))

        restored = skipped = attachments = 0

        for record in records:
            slug = (record.get("slug") or "").strip()
            title = (record.get("title") or "").strip()
            if not title:
                self.stderr.write("Skipping a record with no title.")
                continue

            if slug and Announcement.objects.filter(slug=slug).exists():
                skipped += 1
                self.stdout.write("  = already here: {}".format(slug))
                continue

            if options["dry_run"]:
                restored += 1
                attachments += len(record.get("images", [])) + len(record.get("files", []))
                self.stdout.write("  + would restore: {}".format(slug or title))
                continue

            with transaction.atomic():
                announcement = Announcement(
                    title=title,
                    slug=slug,
                    body=record.get("body", ""),
                    published=bool(record.get("published", True)),
                    category=record.get("category") or "general",
                    year_level=record.get("year_level") or "all",
                    source_page=record.get("source_page", "") or "",
                    source_url=record.get("source_url", "") or "",
                )
                announcement.save()

                # save() stamps published_at with "now"; put the real dates back
                # so the board keeps its original order.
                published_at = parse_datetime(record.get("published_at") or "") or None
                created_at = parse_datetime(record.get("created_at") or "") or None
                Announcement.objects.filter(pk=announcement.pk).update(
                    published_at=published_at,
                    **({"created_at": created_at} if created_at else {}),
                )

                for kind, key in (("image", "images"), ("file", "files")):
                    for item in record.get(key, []):
                        url = item.get("url", "")
                        if not url:
                            continue
                        Attachment.objects.create(
                            announcement=announcement,
                            kind=kind,
                            url=url,
                            public_id=public_id_from(url),
                            resource_type="image" if kind == "image" else "raw",
                            storage_backend=(
                                Attachment.Backend.CLOUDINARY
                                if "res.cloudinary.com" in url
                                else Attachment.Backend.LOCAL
                            ),
                            original_filename=item.get("original_filename", "")[:255],
                            content_type=item.get("content_type", "")[:100],
                            size=item.get("size") or 0,
                            width=item.get("width"),
                            height=item.get("height"),
                            caption=item.get("caption", "")[:255],
                            order=item.get("order") or 0,
                        )
                        attachments += 1

            restored += 1
            self.stdout.write("  + restored: {}".format(announcement.slug))

        verb = "Would restore" if options["dry_run"] else "Restored"
        self.stdout.write(
            self.style.SUCCESS(
                "{} {} announcement(s) and {} attachment(s); {} already present.".format(
                    verb, restored, attachments, skipped
                )
            )
        )
