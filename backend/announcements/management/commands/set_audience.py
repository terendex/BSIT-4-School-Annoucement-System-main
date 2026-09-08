"""Set the year and section on announcements in bulk.

Every post made before sections existed is filed as "all sections", which is
right for a campus-wide notice and wrong for the ones that were only ever for
one class. Rather than opening each post in turn, this sets them together:

    python manage.py set_audience --year 4 --section a --exclude notice

It prints what it would change and stops there. Add --apply to write.
"""

from django.core.management.base import BaseCommand, CommandError

from announcements.models import Announcement
from announcements.taxonomy import (
    SECTION_SLUGS,
    YEAR_LEVEL_SLUGS,
    audience_name,
)


class Command(BaseCommand):
    help = "Set the year level and section on existing announcements."

    def add_arguments(self, parser):
        parser.add_argument("--year", help=f"One of: {', '.join(sorted(YEAR_LEVEL_SLUGS))}")
        parser.add_argument("--section", help=f"One of: {', '.join(sorted(SECTION_SLUGS))}")
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            metavar="TEXT",
            help="Skip posts whose title contains this, case-insensitively. Repeatable.",
        )
        parser.add_argument(
            "--only",
            action="append",
            default=[],
            metavar="TEXT",
            help="Only touch posts whose title contains this. Repeatable.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write the change. Without it, nothing is saved.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        section = options["section"]

        if not year and not section:
            raise CommandError("Give --year, --section, or both.")
        if year and year not in YEAR_LEVEL_SLUGS:
            raise CommandError(f"{year!r} is not a year level.")
        if section and section not in SECTION_SLUGS:
            raise CommandError(f"{section!r} is not a section.")

        queryset = Announcement.objects.all().order_by("created_at")
        for text in options["only"]:
            queryset = queryset.filter(title__icontains=text)
        for text in options["exclude"]:
            queryset = queryset.exclude(title__icontains=text)

        changed = []
        for announcement in queryset:
            before = audience_name(announcement.year_level, announcement.section)
            if year:
                announcement.year_level = year
            if section:
                announcement.section = section
            after = audience_name(announcement.year_level, announcement.section)
            if before != after:
                changed.append((announcement, before, after))

        if not changed:
            self.stdout.write("Nothing to change.")
            return

        for announcement, before, after in changed:
            self.stdout.write(
                f"  {announcement.title[:60]:62} {before or 'everyone':>12} -> {after}"
            )

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(changed)} would change. Nothing was saved - add --apply."
                )
            )
            return

        # update_fields, so a bulk retag cannot disturb anything else on the row.
        for announcement, _, _ in changed:
            announcement.save(update_fields=["year_level", "section"])

        self.stdout.write(self.style.SUCCESS(f"\n{len(changed)} updated."))
