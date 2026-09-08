import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .sources import SOURCE_PAGE_CHOICES, page_name
from .taxonomy import (
    CATEGORY_CHOICES,
    DEFAULT_CATEGORY,
    DEFAULT_YEAR_LEVEL,
    YEAR_LEVEL_CHOICES,
    category_name,
    year_level_name,
    section_name,
    audience_name,
    DEFAULT_SECTION,
    SECTION_CHOICES,
)

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

    def in_category(self, slug):
        return self.filter(category=slug) if slug else self

    def for_year_level(self, slug):
        """Posts for one year, plus the ones addressed to everybody.

        A 3rd year student filtering to their year still needs to see a campus
        wide class suspension, so "all" is always included.
        """
        if not slug or slug == DEFAULT_YEAR_LEVEL:
            return self
        return self.filter(year_level__in=[slug, DEFAULT_YEAR_LEVEL])

    def for_section(self, slug):
        """Posts for one section, plus the ones for every section.

        The same rule as the year above it: filtering to A must not hide a
        notice addressed to the whole year, only the ones meant for B, C or D.
        """
        if not slug or slug == DEFAULT_SECTION:
            return self
        return self.filter(section__in=[slug, DEFAULT_SECTION])


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=SLUG_MAX_LENGTH, unique=True, blank=True)
    body = models.TextField(blank=True, help_text="Markdown.")
    published = models.BooleanField(default=True, db_index=True)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=DEFAULT_CATEGORY,
        db_index=True,
    )
    # "all" means the whole school; a specific year narrows it without ever
    # hiding it from that year's filter.
    year_level = models.CharField(
        max_length=10,
        choices=YEAR_LEVEL_CHOICES,
        default=DEFAULT_YEAR_LEVEL,
        db_index=True,
    )
    # Which section within that year, or "all" for every section of it.
    section = models.CharField(
        max_length=10,
        choices=SECTION_CHOICES,
        default=DEFAULT_SECTION,
        db_index=True,
    )
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
    def category_name(self) -> str:
        return category_name(self.category)

    @property
    def year_level_name(self) -> str:
        return year_level_name(self.year_level)

    @property
    def section_name(self) -> str:
        return section_name(self.section)

    @property
    def audience_name(self) -> str:
        """Year and section as one label - "4A" - for a card's tag."""
        return audience_name(self.year_level, self.section)

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


class Profile(models.Model):
    """Who a signed-in account is: an admin, or an invited publisher.

    Kept beside the stock User rather than swapping in a custom user model,
    which cannot be done safely on a database that already has accounts and
    announcements pointing at it.

    Role maps onto the Django flags too, so `django-admin/` and any code using
    is_superuser keeps agreeing with us: admins are superusers, publishers are
    staff-but-not-superuser. The role field is the one the API reads.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        PUBLISHER = "publisher", "Publisher"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.PUBLISHER, db_index=True
    )
    full_name = models.CharField(max_length=150, blank=True)

    # True from the moment an invite is issued until the publisher has set
    # their own password. While true the account has no usable password at all.
    must_change_password = models.BooleanField(default=False)

    # SHA-256 of the outstanding invite token. The token itself only ever
    # exists in the link that is handed out; losing this row means the link
    # stops working, which is the intended failure mode.
    invite_token_hash = models.CharField(max_length=64, blank=True)
    # A live invite link should not stay usable for ever.
    invite_expires_at = models.DateTimeField(null=True, blank=True)

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invites_sent",
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user__email", "user__username"]

    def __str__(self):
        return "{} ({})".format(self.user.email or self.user.username, self.role)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def invite_expired(self) -> bool:
        if not self.must_change_password or self.invite_expires_at is None:
            return False
        return timezone.now() >= self.invite_expires_at

    def clear_invite(self):
        """Called once the publisher has set a password. The link dies here."""
        self.must_change_password = False
        self.invite_token_hash = ""
        self.invite_expires_at = None
        self.password_changed_at = timezone.now()
        self.save(
            update_fields=[
                "must_change_password",
                "invite_token_hash",
                "invite_expires_at",
                "password_changed_at",
            ]
        )


def profile_for(user) -> "Profile":
    """The user's profile, created on demand.

    Accounts made before roles existed - the bootstrap admin, most of all -
    have no profile row. Those are admins: the only way to have had an account
    at all was to be the one running the site.
    """
    profile, created = Profile.objects.get_or_create(
        user=user,
        defaults={
            "role": Profile.Role.ADMIN if user.is_superuser else Profile.Role.PUBLISHER
        },
    )
    return profile
