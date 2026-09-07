"""Export announcements to a JSON file, from this database or a live service.

    python manage.py export_announcements --out backup.json
    python manage.py export_announcements --api https://your-service/ --out backup.json

The --api form reads over the public API, which is the only way to reach posts
held by a running container whose database is not shared - exactly the case
when a service has been running on container-local SQLite.

Pairs with import_announcements.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from announcements.models import Announcement
from announcements.serializers import AnnouncementDetailSerializer

TIMEOUT = 60


class Command(BaseCommand):
    help = "Write every announcement, with its attachments, to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="announcements-backup.json")
        parser.add_argument(
            "--api",
            default="",
            help="Base URL of a running service to read from instead of this database.",
        )

    def handle(self, *args, **options):
        source = options["api"].rstrip("/")
        records = self.from_api(source) if source else self.from_database()

        out = Path(options["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "exported_at": datetime.now().isoformat(),
                    "source": source or "local database",
                    "count": len(records),
                    "announcements": records,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Exported {} announcement(s) to {}".format(len(records), out)
            )
        )

    def from_database(self):
        queryset = Announcement.objects.with_attachments().order_by("id")
        return AnnouncementDetailSerializer(queryset, many=True).data

    def from_api(self, base):
        def get(path):
            try:
                with urllib.request.urlopen(base + path, timeout=TIMEOUT) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, ValueError) as error:
                raise CommandError("Could not read {}{}: {}".format(base, path, error))

        listing = get("/api/announcements/?page_size=100")
        records = []
        for row in listing.get("results", []):
            # Only the detail endpoint carries the body and the attachments.
            records.append(get("/api/announcements/{}/".format(row["slug"])))
            self.stdout.write("  read {}".format(row["slug"]))

        if listing.get("next"):
            self.stderr.write(
                self.style.WARNING(
                    "More than 100 announcements: only the first page was exported."
                )
            )
        return records
