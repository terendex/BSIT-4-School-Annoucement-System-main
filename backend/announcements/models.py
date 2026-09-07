import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .sources import SOURCE_PAGE_CHOICES, page_name

SLUG_MAX_LENGTH = 80

# Rough markdown stripper used only to build plain-text excerpts for OG tags.
_MD_PATTERNS = [
    (re.compile(r"```.*?```", re.S), " "),           # fenced code
    (re.compile(r"`([^`]*)`"), r"\1"),                # inline code
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),      # images
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),   # links
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),    # headings
    (re.compile(r"^\s{0,3}>\s?", re.M), ""),         # blockquotes
    (re.compile(r"^\s{0,3}[-*+]\s+", re.M), ""),     # bullets
    (re.compile(r"[*_~]{1,3}"), ""),                  # emphasis
    (re.compile(r"<[^>]+>"), " "),                    # stray html
    (re.compile(r"\s+"), " "),                        # collapse whitespace
]


# A markdown table separator row, e.g. |---|:--:|---|
_TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")
# A table body row: starts and ends with a pipe.
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _flatten_tables(text: str) -> str:
    """Turn table rows into readable prose so excerpts are not full of pipes.

    Only lines that really look like table rows are touched, so a title such as
    "SUNDAY STARLIGHT || September Mass" keeps its own punctuation.
    """
    lines = []
    for line in text.splitlines():
        if _TABLE_SEPARATOR.match(line):
            continue
        if _TABLE_ROW.match(line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            line = " - ".join(cell for cell in cells if cell)
        lines.append(line)
    return "\n".join(lines)


def markdown_to_text(value: str) -> str:
    text = _flatten_tables(value or "")
    for pattern, replacement in _MD_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


def unique_slug(title: str, queryset, instance_pk=None) -> str:
    """Slugify the title and append -2, -3, ... until the slug is free."""
    base = slugify(title)[:SLUG_MAX_LENGTH].strip("-") or "announcement"
    candidate = base
    suffix = 2
    taken = queryset
    if instance_pk is not None:
        taken = taken.exclude(pk=instance_pk)
    while taken.filter(slug=candidate).exists():
        tail = "-{}".format(suffix)
        candidate = base[: SLUG_MAX_LENGTH - len(tail)].strip("-") + tail
        suffix += 1
    return candidate


class AnnouncementQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published=True)

    def with_attachments(self):
        return self.prefetch_related("attachments")


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=SLUG_MAX_LENGTH, unique=True, blank=True)
    body = models.TextField(blank=True, help_text="Markdown.")
    published = models.BooleanField(default=True, db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    # Where this was re-posted from, when it mirrors a Facebook page post.
    source_page = models.CharField(
        max_length=50, blank=True, choices=SOURCE_PAGE_CHOICES
    )
    source_url = models.URLField(max_length=500, blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self.title, Announcement.objects.all(), self.pk)
        if self.published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def excerpt(self) -> str:
        """Plain-text summary for cards and the OG description."""
        text = markdown_to_text(self.body)
        if len(text) <= 200:
            return text
        return text[:197].rsplit(" ", 1)[0] + "..."

    @property
    def source_page_name(self) -> str:
        return page_name(self.source_page)

    @property
    def cover_image(self):
        """First image attachment; the OG preview image."""
        for attachment in self.attachments.all():
            if attachment.kind == Attachment.Kind.IMAGE:
                return attachment
        return None


class Attachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        FILE = "file", "File"

    class Backend(models.TextChoices):
        CLOUDINARY = "cloudinary", "Cloudinary"
        LOCAL = "local", "Local disk"

    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    url = models.URLField(max_length=500)
    # Cloudinary public id (blank for local-disk uploads) - needed to delete remotely.
    public_id = models.CharField(max_length=255, blank=True)
    resource_type = models.CharField(max_length=20, blank=True)
    storage_backend = models.CharField(
        max_length=20, choices=Backend.choices, default=Backend.CLOUDINARY
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return "{} ({})".format(self.original_filename, self.kind)
