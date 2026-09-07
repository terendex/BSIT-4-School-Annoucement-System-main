"""Guided restore of the announcement backup into the Railway Postgres database.

Run it from the backend/ directory:

    .venv\\Scripts\\python.exe restore_to_railway.py

It asks for the database URL rather than taking it on the command line, so the
password never lands in your shell history. Nothing is written until it has
shown you what it is about to do and you have said yes.
"""
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP = BASE_DIR.parent / "backup" / "announcements-backup.json"


def say(message=""):
    """Print and flush - output is fully buffered when this is piped."""
    print(message, flush=True)


def fail(message):
    say("\n  [x] {}\n".format(message))
    sys.exit(1)


def read_line(prompt, hidden=False):
    """Read one line, hiding it only when there is a real terminal.

    getpass reads the console directly on Windows and ignores piped input,
    which hangs anything non-interactive - including a quick check that the
    guards below actually fire.
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            fail("No input.")
        return line.strip()
    if hidden:
        return getpass.getpass(prompt).strip()
    return input(prompt).strip()


def main():
    say("=" * 68)
    say("  Restore announcements into the Railway Postgres database")
    say("=" * 68)

    backup = DEFAULT_BACKUP
    if not backup.exists():
        fail("No backup file at {}".format(backup))
    say("\n  Backup file : {}".format(backup))

    say("\n  Paste the DATABASE_PUBLIC_URL from Railway.")
    say("  (Railway -> your Postgres service -> Variables -> DATABASE_PUBLIC_URL)")
    if sys.stdin.isatty():
        say("  It stays hidden as you paste; press Enter when done.")
    say("")

    url = read_line("  DATABASE_PUBLIC_URL: ", hidden=True)

    if not url:
        fail("Nothing pasted.")
    if url.startswith("<") or "SomeLongPassword" in url:
        fail("That is the placeholder from the instructions, not your real URL.")

    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        fail("That is not a Postgres URL (it starts with '{}').".format(parsed.scheme))
    if parsed.hostname and parsed.hostname.endswith(".railway.internal"):
        fail(
            "That is the internal URL, which only resolves inside Railway.\n"
            "      Use DATABASE_PUBLIC_URL from the Postgres service instead."
        )

    say("\n  Connecting to {}:{} ...".format(parsed.hostname, parsed.port or 5432))

    os.environ["DATABASE_URL"] = url
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ.setdefault("DJANGO_SECRET_KEY", "restore-script-only")

    import django

    django.setup()

    from django.core.management import call_command
    from django.db import connection

    try:
        connection.ensure_connection()
    except Exception as error:
        fail(
            "Could not connect: {}\n"
            "      Check you copied DATABASE_PUBLIC_URL, and that the Postgres "
            "service is running.".format(error)
        )
    say("  [ok] Connected.")

    if "announcements_announcement" not in connection.introspection.table_names():
        fail(
            "Connected, but the tables do not exist yet.\n"
            "      Deploy the service first so `migrate` can create them, then "
            "run this again."
        )
    say("  [ok] Tables are there.")

    from announcements.models import Announcement

    say("  [i]  Announcements already in that database: {}".format(
        Announcement.objects.count()
    ))

    say("\n" + "-" * 68)
    say("  Dry run - nothing written yet")
    say("-" * 68)
    call_command("import_announcements", str(backup), dry_run=True)

    answer = read_line("\n  Write these to the database? [y/N]: ").lower()
    if answer not in {"y", "yes"}:
        say("\n  Nothing was written.\n")
        return

    say("\n" + "-" * 68)
    call_command("import_announcements", str(backup))
    say("-" * 68)

    say("\n  Done. The database now holds:")
    for announcement in Announcement.objects.order_by("id"):
        say(
            "    #{}  {}  [{} / {}]  {} image(s)".format(
                announcement.id,
                announcement.title[:44],
                announcement.category,
                announcement.year_level,
                announcement.attachments.count(),
            )
        )
    say(
        "\n  Next: open the dashboard and set the real category on each post -\n"
        "  they come back as General because they predate that field.\n"
    )


if __name__ == "__main__":
    main()
