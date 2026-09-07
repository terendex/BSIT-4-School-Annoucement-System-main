import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from .models import Announcement, Attachment, unique_slug

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
