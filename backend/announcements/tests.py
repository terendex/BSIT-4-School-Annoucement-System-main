import io
import json
import pathlib
import re
import sys
import tempfile
from unittest import mock

import dj_database_url

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import checks, mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from .checks import database_is_persistent_in_production
from .management.commands.import_announcements import public_id_from
from .models import Announcement, Attachment, Profile, unique_slug
from .passwords import generate_invite_token, hash_invite_token, tokens_match

User = get_user_model()

ADMIN_PASSWORD = "correct-horse-battery-1"


def make_image_bytes(fmt="PNG", size=(40, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (31, 42, 107)).save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


class SlugTests(TestCase):
    def test_slug_is_generated_from_title(self):
        a = Announcement.objects.create(title="Exam Schedule")
        self.assertEqual(a.slug, "exam-schedule")

    def test_slug_collisions_get_a_numeric_suffix(self):
        Announcement.objects.create(title="Exam Schedule")
        second = Announcement.objects.create(title="Exam Schedule")
        third = Announcement.objects.create(title="Exam Schedule")
        self.assertEqual(second.slug, "exam-schedule-2")
        self.assertEqual(third.slug, "exam-schedule-3")

    def test_untitled_slug_falls_back(self):
        self.assertEqual(unique_slug("!!!", Announcement.objects.all()), "announcement")

    def test_excerpt_flattens_tables(self):
        # Excerpts double as the Messenger preview text, so a schedule table
        # must not arrive as a wall of pipes.
        a = Announcement.objects.create(
            title="T",
            body="| Item | Amount |\n|---|---|\n| Individual | PHP 50 |",
        )
        self.assertEqual(a.excerpt, "Item - Amount Individual - PHP 50")

    def test_excerpt_keeps_pipes_that_are_not_a_table(self):
        a = Announcement.objects.create(
            title="T", body="SUNDAY STARLIGHT || September Mass"
        )
        self.assertEqual(a.excerpt, "SUNDAY STARLIGHT || September Mass")

    def test_excerpt_strips_markdown(self):
        a = Announcement.objects.create(
            title="T", body="# Heading\n\nSee **this** [link](http://x.test) now."
        )
        self.assertEqual(a.excerpt, "Heading See this link now.")


class FeedStateTests(TestCase):
    """The polling endpoint the auto-refresh banner uses."""

    def test_reports_count_and_latest_change(self):
        a = Announcement.objects.create(title="One")
        Announcement.objects.create(title="Two", published=False)
        response = self.client.get(reverse("feed-state"))
        self.assertEqual(response.status_code, 200)
        # Drafts must not leak into the count classmates see.
        self.assertEqual(response.data["count"], 1)
        # Must match the format the announcement serializer emits, or the
        # frontend compares "+00:00" against "+08:00" and refreshes forever.
        listed = self.client.get(reverse("public-announcement-list"))
        self.assertEqual(
            response.data["last_modified"], listed.data["results"][0]["updated_at"]
        )

    def test_signature_moves_when_a_post_is_edited(self):
        a = Announcement.objects.create(title="One")
        before = self.client.get(reverse("feed-state")).data["last_modified"]
        a.title = "One (edited)"
        a.save()
        after = self.client.get(reverse("feed-state")).data["last_modified"]
        self.assertNotEqual(before, after)

    def test_empty_feed(self):
        response = self.client.get(reverse("feed-state"))
        self.assertEqual(response.data, {"count": 0, "last_modified": None})


class HealthCheckTests(TestCase):
    """The deploy healthcheck must answer whatever the platform throws at it."""

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_answers_for_a_host_not_in_allowed_hosts(self):
        # Railway probes with Host: healthcheck.railway.app. Anything that
        # calls request.get_host() would 400 first, failing the deploy.
        for host in ["healthcheck.railway.app", "10.0.0.5:8080", "anything"]:
            response = self.client.get("/healthz/", HTTP_HOST=host)
            self.assertEqual(response.status_code, 200, host)
            self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_answers_without_the_trailing_slash(self):
        response = self.client.get("/healthz", HTTP_HOST="healthcheck.railway.app")
        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["example.com"])
    def test_is_not_redirected_to_https(self):
        # Probes arrive over plain HTTP; a 301 would read as unhealthy.
        response = self.client.get("/healthz/", HTTP_HOST="healthcheck.railway.app")
        self.assertEqual(response.status_code, 200)

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_other_paths_still_reject_unknown_hosts(self):
        response = self.client.get("/api/announcements/", HTTP_HOST="evil.example.com")
        self.assertEqual(response.status_code, 400)


class PublicApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.live = Announcement.objects.create(title="Field Trip", body="Bring forms.")
        self.draft = Announcement.objects.create(title="Secret Draft", published=False)

    def test_list_returns_only_published(self):
        response = self.client.get(reverse("public-announcement-list"))
        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["field-trip"])

    def test_detail_by_slug(self):
        url = reverse("public-announcement-detail", kwargs={"slug": "field-trip"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body"], "Bring forms.")

    def test_draft_detail_is_404(self):
        url = reverse("public-announcement-detail", kwargs={"slug": "secret-draft"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_admin_endpoints_require_auth(self):
        response = self.client.get(reverse("admin-announcement-list"))
        self.assertEqual(response.status_code, 401)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="announcement-test-media-"))
class AdminApiTests(TestCase):
    def setUp(self):
        # Throttle history lives in the cache; reset it so the 5/min login
        # limit does not leak between tests.
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", password=ADMIN_PASSWORD, is_staff=True, is_superuser=True
        )
        self.access = self._login()

    def _login(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["access"]

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.access)

    def test_login_rejects_bad_password(self):
        client = APIClient()
        response = client.post(
            reverse("login"), {"username": "admin", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_login_rejects_non_staff(self):
        User.objects.create_user(username="classmate", password=ADMIN_PASSWORD)
        client = APIClient()
        response = client.post(
            reverse("login"),
            {"username": "classmate", "password": ADMIN_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_edit_and_delete(self):
        self._auth()
        created = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Exam Schedule", "body": "Room 204", "published": True},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["slug"], "exam-schedule")
        pk = created.data["id"]

        edited = self.client.patch(
            reverse("admin-announcement-detail", kwargs={"pk": pk}),
            {"title": "Exam Schedule (final)"},
            format="json",
        )
        self.assertEqual(edited.status_code, 200)
        # Editing the title must not move the shareable link.
        self.assertEqual(edited.data["slug"], "exam-schedule")

        deleted = self.client.delete(
            reverse("admin-announcement-detail", kwargs={"pk": pk})
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Announcement.objects.filter(pk=pk).exists())

    def test_admin_sees_drafts(self):
        Announcement.objects.create(title="Draft One", published=False)
        self._auth()
        response = self.client.get(reverse("admin-announcement-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_image_upload_creates_attachment(self):
        announcement = Announcement.objects.create(title="Field Trip")
        self._auth()
        upload = make_image_bytes()
        upload.name = "photo.png"
        response = self.client.post(
            "/api/admin/announcements/{}/attachments/".format(announcement.pk),
            {"file": upload, "kind": "image", "caption": "Bus"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["kind"], "image")
        self.assertEqual(announcement.attachments.count(), 1)
        self.assertEqual(announcement.cover_image.caption, "Bus")

    def test_upload_rejects_disallowed_extension(self):
        announcement = Announcement.objects.create(title="Field Trip")
        self._auth()
        bad = io.BytesIO(b"MZ executable")
        bad.name = "virus.exe"
        response = self.client.post(
            "/api/admin/announcements/{}/attachments/".format(announcement.pk),
            {"file": bad, "kind": "file"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_image_that_is_not_an_image(self):
        announcement = Announcement.objects.create(title="Field Trip")
        self._auth()
        fake = io.BytesIO(b"not really a png")
        fake.name = "fake.png"
        response = self.client.post(
            "/api/admin/announcements/{}/attachments/".format(announcement.pk),
            {"file": fake, "kind": "image"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_filename_is_sanitized(self):
        announcement = Announcement.objects.create(title="Field Trip")
        self._auth()
        upload = make_image_bytes()
        upload.name = "../../etc/pass wd;rm -rf.png"
        response = self.client.post(
            "/api/admin/announcements/{}/attachments/".format(announcement.pk),
            {"file": upload, "kind": "image"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        stored = response.data["original_filename"]
        self.assertNotIn("/", stored)
        self.assertNotIn("..", stored)
        self.assertTrue(stored.endswith(".png"))


class SourcePageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", password=ADMIN_PASSWORD, is_staff=True, is_superuser=True
        )
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])

    def test_source_pages_are_listed_publicly(self):
        response = APIClient().get(reverse("source-pages"))
        self.assertEqual(response.status_code, 200)
        slugs = [page["slug"] for page in response.data["results"]]
        self.assertIn("sits.slclu", slugs)
        self.assertEqual(len(slugs), 6)

    def test_announcement_records_its_source(self):
        response = self.client.post(
            reverse("admin-announcement-list"),
            {
                "title": "SITS Mass Sponsorship",
                "body": "September Mass Sponsorship.",
                "published": True,
                "source_page": "sits.slclu",
                "source_url": "https://www.facebook.com/sits.slclu/posts/123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["source_page"], "sits.slclu")
        self.assertEqual(
            response.data["source_page_name"],
            "Society of Information Technology Students - SLC La Union",
        )

    def test_unknown_source_page_is_rejected(self):
        response = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Nope", "published": True, "source_page": "some-random-page"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_source_url_must_be_http(self):
        response = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Nope", "published": True, "source_url": "javascript:alert(1)"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_source_is_optional(self):
        response = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Plain post", "published": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["source_page"], "")


class AttachmentModelTests(TestCase):
    def test_cover_image_prefers_first_image(self):
        announcement = Announcement.objects.create(title="Mixed")
        Attachment.objects.create(
            announcement=announcement, kind="file", url="http://x.test/a.pdf",
            original_filename="a.pdf", order=0,
        )
        Attachment.objects.create(
            announcement=announcement, kind="image", url="http://x.test/b.png",
            original_filename="b.png", order=1,
        )
        self.assertEqual(announcement.cover_image.original_filename, "b.png")


class DatabasePersistenceCheckTests(TestCase):
    """A production deploy must never come up on a throwaway SQLite file.

    The check is what keeps announcements alive across deploys: it has to be an
    ERROR, because `manage.py migrate` aborts on one and the start command runs
    gunicorn behind it, so the bad deploy fails and the old one keeps serving.

    Every test pins sys.argv, since the check deliberately stands down for
    commands that are not a live deployment - including the test runner itself.
    """

    SQLITE = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }
    POSTGRES = {
        "default": {"ENGINE": "django.db.backends.postgresql", "NAME": "announcements"}
    }

    def run_check(self, argv=("manage.py", "migrate", "--no-input")):
        with mock.patch.object(sys, "argv", list(argv)):
            return database_is_persistent_in_production(None)

    @override_settings(DEBUG=False, DATABASES=SQLITE)
    def test_sqlite_in_production_is_a_hard_error(self):
        issues = self.run_check()
        self.assertEqual([issue.id for issue in issues], ["announcements.E002"])
        self.assertEqual(issues[0].level, checks.ERROR)

    @override_settings(DEBUG=False, DATABASES=POSTGRES)
    def test_postgres_in_production_passes(self):
        self.assertEqual(self.run_check(), [])

    @override_settings(DEBUG=True, DATABASES=SQLITE)
    def test_local_development_on_sqlite_is_left_alone(self):
        self.assertEqual(self.run_check(), [])

    @override_settings(DEBUG=False, DATABASES=SQLITE)
    def test_image_build_step_is_left_alone(self):
        # The Dockerfile runs collectstatic with DJANGO_DEBUG=False and no
        # database; firing here would break the build, not a bad deploy.
        self.assertEqual(self.run_check(("manage.py", "collectstatic")), [])

    @override_settings(DEBUG=False, DATABASES=SQLITE)
    def test_the_test_runner_is_left_alone(self):
        self.assertEqual(self.run_check(("manage.py", "test")), [])


# --------------------------------------------------------------------------
# Roles, invites and password rules
# --------------------------------------------------------------------------
PUBLISHER_PASSWORD = "Publisher-9!pass"
LOCMEM_EMAIL = "django.core.mail.backends.locmem.EmailBackend"


class RoleTestCase(TestCase):
    """Shared setup: one admin, one publisher, both past their first login."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()

        self.admin = User.objects.create_user(
            username="admin", email="admin@slc.test",
            password=ADMIN_PASSWORD, is_staff=True, is_superuser=True,
        )
        Profile.objects.create(user=self.admin, role=Profile.Role.ADMIN)

        self.publisher = User.objects.create_user(
            username="juan@gmail.test", email="juan@gmail.test",
            password=PUBLISHER_PASSWORD, is_staff=True, is_superuser=False,
        )
        Profile.objects.create(
            user=self.publisher, role=Profile.Role.PUBLISHER, full_name="Juan Dela Cruz"
        )

    def sign_in(self, identifier, password):
        return self.client.post(
            reverse("login"), {"username": identifier, "password": password},
            format="json",
        )

    def as_user(self, identifier, password):
        response = self.sign_in(identifier, password)
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        return response.data

    def logout(self):
        self.client.credentials()


class LoginIdentityTests(RoleTestCase):
    def test_publisher_signs_in_with_their_email(self):
        data = self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        self.assertEqual(data["user"]["role"], "publisher")
        self.assertEqual(data["user"]["full_name"], "Juan Dela Cruz")

    def test_email_is_case_insensitive(self):
        self.assertEqual(self.sign_in("JUAN@GMAIL.TEST", PUBLISHER_PASSWORD).status_code, 200)

    def test_bootstrap_admin_can_still_use_its_username(self):
        # The original admin may have been created before invites existed.
        response = self.sign_in("admin", ADMIN_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "admin")

    def test_admin_can_also_use_their_email(self):
        self.assertEqual(self.sign_in("admin@slc.test", ADMIN_PASSWORD).status_code, 200)

    def test_unknown_email_and_wrong_password_look_identical(self):
        unknown = self.sign_in("nobody@gmail.test", "whatever-1A!")
        wrong = self.sign_in("juan@gmail.test", "wrong-password-1A!")
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.data["detail"], wrong.data["detail"])

    def test_deactivated_publisher_cannot_sign_in(self):
        self.publisher.is_active = False
        self.publisher.save(update_fields=["is_active"])
        self.assertEqual(self.sign_in("juan@gmail.test", PUBLISHER_PASSWORD).status_code, 401)


class PublisherPermissionTests(RoleTestCase):
    def setUp(self):
        super().setUp()
        self.own = Announcement.objects.create(title="Mine", author=self.publisher)
        self.other = Announcement.objects.create(title="Theirs", author=self.admin)

    def test_publisher_can_create(self):
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        response = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Org meeting", "body": "Later today.", "published": True,
             "category": "event", "year_level": "4"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            Announcement.objects.get(pk=response.data["id"]).author, self.publisher
        )

    def test_publisher_can_edit_their_own(self):
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        response = self.client.patch(
            reverse("admin-announcement-detail", args=[self.own.pk]),
            {"title": "Mine, fixed"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_publisher_cannot_edit_someone_elses(self):
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        response = self.client.patch(
            reverse("admin-announcement-detail", args=[self.other.pk]),
            {"title": "Hijacked"}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.other.refresh_from_db()
        self.assertEqual(self.other.title, "Theirs")

    def test_publisher_cannot_delete_even_their_own(self):
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        response = self.client.delete(
            reverse("admin-announcement-detail", args=[self.own.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Announcement.objects.filter(pk=self.own.pk).exists())

    def test_admin_can_edit_and_delete_anyones(self):
        self.as_user("admin", ADMIN_PASSWORD)
        edit = self.client.patch(
            reverse("admin-announcement-detail", args=[self.own.pk]),
            {"title": "Edited by admin"}, format="json",
        )
        self.assertEqual(edit.status_code, 200, edit.data)
        delete = self.client.delete(reverse("admin-announcement-detail", args=[self.own.pk]))
        self.assertEqual(delete.status_code, 204)

    def test_publisher_sees_the_whole_board(self):
        # They need to know what has been posted before adding to it.
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        response = self.client.get(reverse("admin-announcement-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_publisher_cannot_manage_publishers(self):
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        self.assertEqual(self.client.get(reverse("publisher-list")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("publisher-list"), {"email": "x@y.test"}, format="json"
            ).status_code,
            403,
        )


@override_settings(EMAIL_BACKEND=LOCMEM_EMAIL)
class InviteFlowTests(RoleTestCase):
    """Invites are links, not passwords.

    The point of the whole design: the publisher's password is chosen by the
    publisher and known to nobody else. Not the admin who sent the invite, not
    the mail server, not whatever chat window the link was pasted into.
    """

    def invite(self, email="maria@gmail.test", full_name="Maria Santos"):
        self.as_user("admin", ADMIN_PASSWORD)
        return self.client.post(
            reverse("publisher-list"), {"email": email, "full_name": full_name},
            format="json",
        )

    def token_from(self, response):
        return response.data["invite_url"].rstrip("/").rsplit("/", 1)[-1]

    def test_inviting_sends_a_link_and_creates_no_password(self):
        response = self.invite()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["invite_email_sent"])
        self.assertIn("/invite/", response.data["invite_url"])

        user = User.objects.get(email="maria@gmail.test")
        self.assertFalse(user.has_usable_password())

    def test_no_password_is_ever_returned_to_the_admin(self):
        response = self.invite()
        self.assertNotIn("temporary_password", json.dumps(response.data))
        self.assertNotIn("password", {key.lower() for key in response.data})

    def test_the_email_carries_the_link_and_no_credential(self):
        response = self.invite()
        body = mail.outbox[0].body
        self.assertIn(response.data["invite_url"], body)
        self.assertNotIn("Temporary password", body)

    def test_the_raw_token_is_never_stored(self):
        response = self.invite()
        token = self.token_from(response)
        profile = Profile.objects.get(user__email="maria@gmail.test")
        self.assertNotEqual(profile.invite_token_hash, token)
        self.assertEqual(len(profile.invite_token_hash), 64)

    def test_the_link_says_who_it_is_for(self):
        token = self.token_from(self.invite())
        self.logout()
        response = self.client.get(reverse("invite-detail", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "maria@gmail.test")
        self.assertEqual(response.data["full_name"], "Maria Santos")

    def test_accepting_the_invite_signs_them_straight_in(self):
        token = self.token_from(self.invite())
        self.logout()
        response = self.client.post(
            reverse("accept-invite"),
            {"token": token, "new_password": "Maria-Sept-2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["user"]["must_change_password"])
        self.assertEqual(response.data["user"]["role"], "publisher")

        cache.clear()
        self.assertEqual(
            self.sign_in("maria@gmail.test", "Maria-Sept-2026!").status_code, 200
        )

    def test_a_link_cannot_be_used_twice(self):
        token = self.token_from(self.invite())
        self.logout()
        self.client.post(
            reverse("accept-invite"),
            {"token": token, "new_password": "Maria-Sept-2026!"}, format="json",
        )
        again = self.client.post(
            reverse("accept-invite"),
            {"token": token, "new_password": "Different-Pass-99!"}, format="json",
        )
        self.assertEqual(again.status_code, 400)
        cache.clear()
        self.assertEqual(
            self.sign_in("maria@gmail.test", "Maria-Sept-2026!").status_code, 200
        )

    def test_a_made_up_token_is_refused(self):
        self.invite()
        self.logout()
        response = self.client.post(
            reverse("accept-invite"),
            {"token": "not-a-real-token", "new_password": "Maria-Sept-2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_an_expired_link_is_refused_with_an_explanation(self):
        token = self.token_from(self.invite())
        profile = Profile.objects.get(user__email="maria@gmail.test")
        profile.invite_expires_at = timezone.now() - timezone.timedelta(minutes=1)
        profile.save(update_fields=["invite_expires_at"])
        self.logout()

        response = self.client.post(
            reverse("accept-invite"),
            {"token": token, "new_password": "Maria-Sept-2026!"}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.data["detail"].lower())

    def test_the_password_rules_apply_to_the_invite_screen_too(self):
        token = self.token_from(self.invite())
        self.logout()
        for weak in ("short1!A", "Password123!", "nocapitals-2026!"):
            with self.subTest(password=weak):
                response = self.client.post(
                    reverse("accept-invite"),
                    {"token": token, "new_password": weak}, format="json",
                )
                self.assertEqual(response.status_code, 400)

    def test_an_account_mid_invite_cannot_be_signed_into(self):
        # There is no password to guess; the link is the only way in.
        self.invite()
        self.logout()
        cache.clear()
        self.assertEqual(
            self.sign_in("maria@gmail.test", "anything-1A!").status_code, 401
        )

    def test_resending_invalidates_the_previous_link(self):
        first = self.token_from(self.invite())
        user = User.objects.get(email="maria@gmail.test")
        second = self.token_from(
            self.client.post(reverse("publisher-resend-invite", args=[user.pk]))
        )
        self.assertNotEqual(first, second)
        self.logout()

        stale = self.client.post(
            reverse("accept-invite"),
            {"token": first, "new_password": "Maria-Sept-2026!"}, format="json",
        )
        self.assertEqual(stale.status_code, 400)
        fresh = self.client.post(
            reverse("accept-invite"),
            {"token": second, "new_password": "Maria-Sept-2026!"}, format="json",
        )
        self.assertEqual(fresh.status_code, 200)

    def test_the_same_email_cannot_be_invited_twice(self):
        self.invite()
        again = self.client.post(
            reverse("publisher-list"), {"email": "maria@gmail.test"}, format="json"
        )
        self.assertEqual(again.status_code, 400)

    def test_admin_cannot_delete_their_own_account(self):
        self.as_user("admin", ADMIN_PASSWORD)
        response = self.client.delete(reverse("publisher-detail", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 403)

    def test_deleting_a_publisher_leaves_their_announcements_up(self):
        notice = Announcement.objects.create(
            title="No classes tomorrow", author=self.publisher, category="suspension"
        )
        self.as_user("admin", ADMIN_PASSWORD)
        response = self.client.delete(
            reverse("publisher-detail", args=[self.publisher.pk])
        )
        self.assertEqual(response.status_code, 204)

        notice.refresh_from_db()
        self.assertIsNone(notice.author)
        self.assertTrue(Announcement.objects.filter(pk=notice.pk).exists())

    def test_deactivating_keeps_the_account_and_its_posts(self):
        self.as_user("admin", ADMIN_PASSWORD)
        response = self.client.patch(
            reverse("publisher-detail", args=[self.publisher.pk]),
            {"is_active": False}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.publisher.refresh_from_db()
        self.assertFalse(self.publisher.is_active)


class PasswordRuleTests(RoleTestCase):
    def change_to(self, new_password, current=PUBLISHER_PASSWORD):
        cache.clear()
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        return self.client.post(
            reverse("change-password"),
            {"current_password": current, "new_password": new_password},
            format="json",
        )

    def test_a_strong_password_is_accepted(self):
        self.assertEqual(self.change_to("Tinta-Sept-2026!").status_code, 200)

    def test_too_short_is_rejected(self):
        self.assertEqual(self.change_to("Ab1!xy").status_code, 400)

    def test_no_symbol_is_rejected(self):
        self.assertEqual(self.change_to("Announcement2026").status_code, 400)

    def test_no_uppercase_is_rejected(self):
        self.assertEqual(self.change_to("announcement-2026!").status_code, 400)

    def test_no_digit_is_rejected(self):
        self.assertEqual(self.change_to("Announcements!!").status_code, 400)

    def test_all_numeric_is_rejected(self):
        self.assertEqual(self.change_to("09171234567").status_code, 400)

    def test_a_common_password_in_disguise_is_rejected(self):
        # Each of these clears length and the character mix, and each is one of
        # the first guesses an attacker makes.
        for candidate in ("Password123!", "Welcome123!", "Qwerty2026!"):
            with self.subTest(password=candidate):
                self.assertEqual(self.change_to(candidate).status_code, 400)

    def test_reusing_the_current_password_is_rejected(self):
        self.assertEqual(self.change_to(PUBLISHER_PASSWORD).status_code, 400)

    def test_the_wrong_current_password_is_rejected(self):
        response = self.change_to("Tinta-Sept-2026!", current="not-my-password-1A!")
        self.assertEqual(response.status_code, 400)

    def test_invite_tokens_are_unique_and_verify_only_against_themselves(self):
        seen = set()
        for _unused in range(50):
            token = generate_invite_token()
            self.assertNotIn(token, seen)
            seen.add(token)
            self.assertTrue(tokens_match(token, hash_invite_token(token)))
            self.assertFalse(tokens_match(token, hash_invite_token(token + "x")))

    def test_an_empty_token_never_matches(self):
        self.assertFalse(tokens_match("", hash_invite_token("something")))
        self.assertFalse(tokens_match("something", ""))


class TaxonomyFilterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.suspension = Announcement.objects.create(
            title="No classes", category="suspension", year_level="all"
        )
        self.exam_4th = Announcement.objects.create(
            title="Prelims for 4th year", category="exam", year_level="4"
        )
        self.exam_1st = Announcement.objects.create(
            title="Prelims for 1st year", category="exam", year_level="1"
        )
        self.section_a = Announcement.objects.create(
            title="4A system checking", category="general", year_level="4", section="a"
        )
        self.section_b = Announcement.objects.create(
            title="4B system checking", category="general", year_level="4", section="b"
        )
        self.draft = Announcement.objects.create(
            title="Draft holiday", category="holiday", published=False
        )

    def titles(self, query=""):
        response = self.client.get(reverse("public-announcement-list") + query)
        self.assertEqual(response.status_code, 200)
        return {item["title"] for item in response.data["results"]}

    def test_defaults_are_applied(self):
        fresh = Announcement.objects.create(title="Plain")
        self.assertEqual(fresh.category, "general")
        self.assertEqual(fresh.year_level, "all")
        self.assertEqual(fresh.section, "all")

    def test_filtering_by_category(self):
        self.assertEqual(
            self.titles("?category=exam"),
            {"Prelims for 4th year", "Prelims for 1st year"},
        )

    def test_filtering_by_year_keeps_all_year_posts(self):
        # A 4th year student must still see a campus-wide suspension, and both
        # sections of their own year.
        self.assertEqual(
            self.titles("?year=4"),
            {"Prelims for 4th year", "No classes", "4A system checking", "4B system checking"},
        )

    def test_the_two_filters_combine(self):
        self.assertEqual(self.titles("?category=exam&year=1"), {"Prelims for 1st year"})

    def test_year_all_means_no_narrowing(self):
        self.assertEqual(len(self.titles("?year=all")), 5)

    def test_filtering_by_section_keeps_the_posts_for_every_section(self):
        # Section A must still see what was addressed to the whole school.
        self.assertEqual(
            self.titles("?section=a"),
            {"4A system checking", "No classes", "Prelims for 4th year", "Prelims for 1st year"},
        )

    def test_filtering_by_section_hides_the_other_sections(self):
        self.assertNotIn("4B system checking", self.titles("?section=a"))

    def test_year_and_section_combine_to_one_class(self):
        self.assertEqual(
            self.titles("?year=4&section=a"),
            {"4A system checking", "No classes", "Prelims for 4th year"},
        )

    def test_section_all_means_no_narrowing(self):
        self.assertEqual(len(self.titles("?section=all")), 5)

    def test_an_unknown_section_falls_back_to_the_posts_for_everybody(self):
        # Same as an unknown year: the value matches no section, so what is
        # left is what was addressed to every section. Nothing is revealed
        # that a reader could not already see, and nothing 500s.
        self.assertEqual(self.titles("?section=zzz"), self.titles("?section=all&year=all") - {
            "4A system checking",
            "4B system checking",
        })

    def test_the_audience_label_reads_as_the_class_is_called(self):
        self.assertEqual(self.section_a.audience_name, "4A")
        self.assertEqual(self.exam_4th.audience_name, "4th year")
        self.assertEqual(self.suspension.audience_name, "")

    def test_filters_never_reveal_drafts(self):
        self.assertNotIn("Draft holiday", self.titles("?category=holiday"))

    def test_an_unknown_filter_value_returns_nothing_rather_than_everything(self):
        self.assertEqual(self.titles("?category=nonsense"), set())

    def test_feed_state_follows_the_same_filters(self):
        response = self.client.get(reverse("feed-state") + "?category=exam")
        self.assertEqual(response.data["count"], 2)

    def test_feed_state_follows_the_section_filter_too(self):
        # If it did not, a reader filtered to one section would be told to
        # reload every time any other section was posted to.
        response = self.client.get(reverse("feed-state") + "?section=b")
        self.assertEqual(
            response.data["count"],
            len(self.titles("?section=b")),
        )

    def test_taxonomy_endpoint_lists_every_axis(self):
        response = self.client.get(reverse("taxonomy"))
        self.assertEqual(response.status_code, 200)
        categories = {item["slug"] for item in response.data["categories"]}
        self.assertIn("suspension", categories)
        self.assertIn("holiday", categories)
        self.assertEqual(
            [item["slug"] for item in response.data["year_levels"]],
            ["all", "1", "2", "3", "4"],
        )
        self.assertEqual(
            [item["slug"] for item in response.data["sections"]],
            ["all", "a", "b", "c", "d"],
        )

    def test_the_editor_rejects_a_category_that_is_not_ours(self):
        admin = User.objects.create_user(
            username="boss", password=ADMIN_PASSWORD, is_staff=True, is_superuser=True
        )
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            reverse("admin-announcement-list"),
            {"title": "Bad filing", "category": "made-up"}, format="json",
        )
        self.assertEqual(response.status_code, 400)


class FeedStateAgreementTests(TestCase):
    """feed-state must answer exactly what the list view was asked.

    The homepage renders feed-state's answer as its fingerprint and AutoRefresh
    polls the same endpoint every minute. If the two ever disagree for a slice
    the reader is looking at, the page reloads, renders the same mismatch, and
    reloads again - a loop that only ends when the tab is closed.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        for index in range(3):
            Announcement.objects.create(
                title=f"Exam notice {index}", category="exam", year_level="1"
            )
        Announcement.objects.create(title="Holiday notice", category="holiday")
        Announcement.objects.create(title="Hidden draft", published=False)

    def assert_agrees(self, query=""):
        """The two endpoints must describe the same set of announcements."""
        listing = self.client.get(reverse("public-announcement-list") + query)
        state = self.client.get(reverse("feed-state") + query)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(state.status_code, 200)

        self.assertEqual(
            listing.data["count"],
            state.data["count"],
            f"feed-state counted {state.data['count']} where the list showed "
            f"{listing.data['count']} for {query!r} - the page would reload for ever",
        )
        # And the timestamp has to be the newest across the whole filtered set,
        # not merely the rows that fitted on this page.
        newest = max(
            (row["updated_at"] for row in listing.data["results"]), default=None
        )
        self.assertEqual(state.data["last_modified"], newest, f"drift for {query!r}")

    def test_agrees_with_no_filters(self):
        self.assert_agrees()

    def test_agrees_when_searching(self):
        # The bug: feed-state ignored q, so any search left a permanent
        # mismatch and the page reloaded every minute.
        self.assert_agrees("?q=Exam")

    def test_agrees_when_filtering_by_category(self):
        self.assert_agrees("?category=exam")

    def test_agrees_when_filtering_by_year(self):
        self.assert_agrees("?year=1")

    def test_agrees_with_every_filter_at_once(self):
        self.assert_agrees("?q=notice&category=exam&year=1")

    def test_search_is_actually_applied(self):
        response = self.client.get(reverse("feed-state") + "?q=Holiday")
        self.assertEqual(response.data["count"], 1)

    def test_drafts_are_never_counted(self):
        response = self.client.get(reverse("feed-state"))
        self.assertEqual(response.data["count"], 4)

    def test_the_fingerprint_moves_when_a_post_is_edited(self):
        before = self.client.get(reverse("feed-state") + "?category=exam").data
        edited = Announcement.objects.filter(category="exam").first()
        edited.title = "Exam notice, moved"
        edited.save()
        after = self.client.get(reverse("feed-state") + "?category=exam").data
        self.assertNotEqual(before["last_modified"], after["last_modified"])

    def test_an_edit_outside_the_filter_does_not_move_it(self):
        # A reader browsing exams should not be reloaded because a holiday
        # notice was edited.
        before = self.client.get(reverse("feed-state") + "?category=exam").data
        holiday = Announcement.objects.get(title="Holiday notice")
        holiday.title = "Holiday notice, edited"
        holiday.save()
        after = self.client.get(reverse("feed-state") + "?category=exam").data
        self.assertEqual(before, after)


class InviteEdgeCaseTests(RoleTestCase):
    def test_an_email_too_long_for_the_username_column_is_a_field_error(self):
        # username is 150 wide and the address doubles as it; without the
        # guard this was a database error, not a validation message.
        self.as_user("admin", ADMIN_PASSWORD)
        response = self.client.post(
            reverse("publisher-list"),
            {"email": "a" * 200 + "@gmail.test"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data.get("errors", response.data))

    def test_password_changes_are_not_on_the_login_throttle(self):
        # Fumbling the password rules must not lock someone out of finishing
        # their own onboarding.
        self.as_user("juan@gmail.test", PUBLISHER_PASSWORD)
        for attempt in range(8):
            response = self.client.post(
                reverse("change-password"),
                {"current_password": PUBLISHER_PASSWORD, "new_password": "weak"},
                format="json",
            )
            self.assertEqual(
                response.status_code, 400, f"throttled on attempt {attempt + 1}"
            )


class RestoreCommandTests(TestCase):
    """Putting announcements back after the database was swapped underneath.

    The service ran on container-local SQLite, so its posts were reachable only
    through the public API of the container still holding them. These commands
    are the bridge from that export to a real database.
    """

    BACKUP = {
        "exported_at": "2026-09-08T03:56:55",
        "count": 1,
        "announcements": [
            {
                "id": 2,
                "title": "NOTICE! Collection of ₱100",
                "slug": "notice-collection",
                "body": "**NOTICE!** A collection will be made.",
                "published": True,
                "published_at": "2026-09-07T23:58:06.856638+08:00",
                "created_at": "2026-09-07T23:58:06.856765+08:00",
                "category": "event",
                "year_level": "3",
                "source_page": "",
                "source_url": "",
                "images": [
                    {
                        "url": "https://res.cloudinary.com/dsurmbjr/image/upload/v1788796687/announcements/images/slc_announcement-8d009745.png",
                        "original_filename": "slc_announcement.png",
                        "content_type": "image/png",
                        "size": 51608,
                        "width": 1200,
                        "height": 1200,
                        "caption": "",
                        "order": 0,
                    }
                ],
                "files": [],
            }
        ],
    }

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="announcement-restore-")
        self.path = pathlib.Path(self.directory) / "backup.json"
        self.path.write_text(json.dumps(self.BACKUP), encoding="utf-8")

    def run_import(self, *args):
        out = io.StringIO()
        call_command("import_announcements", str(self.path), *args, stdout=out)
        return out.getvalue()

    def test_public_id_is_recovered_from_a_cloudinary_url(self):
        # Not part of the export, but a later delete needs it to remove the
        # file from Cloudinary rather than orphaning it.
        self.assertEqual(
            public_id_from(
                "https://res.cloudinary.com/dsurmbjr/image/upload/v1788796687/"
                "announcements/images/slc_announcement-8d009745.png"
            ),
            "announcements/images/slc_announcement-8d009745",
        )

    def test_public_id_survives_a_url_without_a_version(self):
        self.assertEqual(
            public_id_from(
                "https://res.cloudinary.com/x/image/upload/announcements/images/a.jpg"
            ),
            "announcements/images/a",
        )

    def test_a_non_cloudinary_url_has_no_public_id(self):
        self.assertEqual(public_id_from("http://localhost:8000/media/a.png"), "")

    def test_the_announcement_comes_back_whole(self):
        self.run_import()
        announcement = Announcement.objects.get(slug="notice-collection")
        self.assertEqual(announcement.title, "NOTICE! Collection of ₱100")
        self.assertEqual(announcement.body, "**NOTICE!** A collection will be made.")
        self.assertEqual(announcement.category, "event")
        self.assertEqual(announcement.year_level, "3")
        self.assertTrue(announcement.published)

    def test_the_original_publish_date_is_kept(self):
        # save() would otherwise stamp published_at with "now" and shuffle the
        # board out of its real order.
        self.run_import()
        announcement = Announcement.objects.get(slug="notice-collection")
        self.assertEqual(
            announcement.published_at, parse_datetime("2026-09-07T23:58:06.856638+08:00")
        )

    def test_the_image_is_relinked_not_reuploaded(self):
        self.run_import()
        attachment = Attachment.objects.get()
        self.assertEqual(attachment.kind, "image")
        self.assertIn("res.cloudinary.com", attachment.url)
        self.assertEqual(
            attachment.public_id, "announcements/images/slc_announcement-8d009745"
        )
        self.assertEqual(attachment.storage_backend, Attachment.Backend.CLOUDINARY)
        self.assertEqual(attachment.size, 51608)

    def test_running_it_twice_does_not_duplicate(self):
        self.run_import()
        output = self.run_import()
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertIn("already present", output)

    def test_a_dry_run_writes_nothing(self):
        output = self.run_import("--dry-run")
        self.assertEqual(Announcement.objects.count(), 0)
        self.assertIn("would restore", output.lower())

    def test_a_missing_file_is_a_clean_error(self):
        with self.assertRaises(CommandError):
            call_command("import_announcements", str(self.path) + ".nope")

    def test_a_malformed_file_is_a_clean_error(self):
        self.path.write_text("not json at all", encoding="utf-8")
        with self.assertRaises(CommandError):
            call_command("import_announcements", str(self.path))

    def test_export_round_trips_through_the_local_database(self):
        self.run_import()
        out = pathlib.Path(self.directory) / "again.json"
        call_command("export_announcements", "--out", str(out), stdout=io.StringIO())

        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["announcements"][0]["slug"], "notice-collection")
        self.assertEqual(len(payload["announcements"][0]["images"]), 1)


class DatabaseUrlOptionsTests(TestCase):
    """sslmode is a Postgres connection argument and nothing else's.

    Applying it to every DATABASE_URL made a sqlite:/// URL - the obvious way
    to restore into a throwaway copy - fail to connect at all.
    """

    def options_for(self, url):
        config = dj_database_url.parse(url)
        engine = config.get("ENGINE", "")
        if engine.endswith(("postgresql", "postgresql_psycopg2")) and "sslmode" not in url:
            config.setdefault("OPTIONS", {})["sslmode"] = "prefer"
        return config.get("OPTIONS", {})

    def test_postgres_gets_an_sslmode(self):
        self.assertEqual(
            self.options_for("postgres://u:p@host:5432/db").get("sslmode"), "prefer"
        )

    def test_sqlite_does_not(self):
        self.assertNotIn("sslmode", self.options_for("sqlite:////tmp/copy.sqlite3"))

    def test_an_explicit_sslmode_is_not_overwritten(self):
        self.assertEqual(
            self.options_for("postgres://u:p@h:5432/db?sslmode=require").get("sslmode"),
            "require",
        )


@override_settings(EMAIL_BACKEND=LOCMEM_EMAIL)
class InviteDeliveryFailureTests(RoleTestCase):
    """A failed email must not strand the account.

    Since the invite is a link rather than a credential, a bounced email costs
    nothing: the admin copies the link and sends it another way. What matters
    is that they are told why, and that the link is there either way.
    """

    def invite(self, email="unlucky@gmail.test"):
        self.as_user("admin", ADMIN_PASSWORD)
        return self.client.post(
            reverse("publisher-list"), {"email": email, "full_name": "Un Lucky"},
            format="json",
        )

    def test_a_blocked_port_is_reported_as_such(self):
        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=OSError(101, "Network is unreachable"),
        ):
            response = self.invite()

        self.assertEqual(response.status_code, 207)
        self.assertFalse(response.data["invite_email_sent"])
        self.assertIn("blocking outbound SMTP", response.data["detail"])

    def test_bad_credentials_are_reported_as_such(self):
        import smtplib

        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPAuthenticationError(535, b"nope"),
        ):
            response = self.invite()

        self.assertIn("App Password", response.data["detail"])
        self.assertNotIn("blocking outbound SMTP", response.data["detail"])

    def test_the_link_is_returned_even_when_the_email_fails(self):
        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=OSError(101, "Network is unreachable"),
        ):
            response = self.invite()

        link = response.data.get("invite_url")
        self.assertTrue(link, "no invite link was returned")

        # And it genuinely works when handed over by another route.
        token = link.rstrip("/").rsplit("/", 1)[-1]
        self.logout()
        accepted = self.client.post(
            reverse("accept-invite"),
            {"token": token, "new_password": "Un-Lucky-2026!"}, format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)

    def test_still_no_password_anywhere_in_the_failure_response(self):
        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=OSError(101, "Network is unreachable"),
        ):
            response = self.invite()
        self.assertNotIn("temporary_password", json.dumps(response.data))

    def test_a_failed_resend_also_returns_the_new_link(self):
        self.invite()
        user = User.objects.get(email="unlucky@gmail.test")
        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=OSError(101, "Network is unreachable"),
        ):
            response = self.client.post(
                reverse("publisher-resend-invite", args=[user.pk])
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["invite_email_sent"])
        self.assertIn("/invite/", response.data["invite_url"])

    def test_the_token_never_reaches_the_log(self):
        with mock.patch(
            "announcements.emails.EmailMultiAlternatives.send",
            side_effect=OSError(101, "Network is unreachable"),
        ):
            with self.assertLogs("announcements.emails", level="ERROR") as captured:
                response = self.invite()

        token = response.data["invite_url"].rstrip("/").rsplit("/", 1)[-1]
        self.assertNotIn(token, "\n".join(captured.output))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
class ConsoleBackendIsNotDeliveryTests(RoleTestCase):
    def test_printing_to_the_console_does_not_count_as_sent(self):
        # Otherwise the dashboard reports success while the password goes to
        # the deploy log and the invitee receives nothing.
        self.as_user("admin", ADMIN_PASSWORD)
        response = self.client.post(
            reverse("publisher-list"), {"email": "nowhere@gmail.test"}, format="json"
        )
        self.assertEqual(response.status_code, 207)
        self.assertFalse(response.data["invite_email_sent"])
        self.assertIn("not configured", response.data["detail"])
        self.assertIn("/invite/", response.data["invite_url"])
