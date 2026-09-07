from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from rest_framework import serializers

from .models import Announcement, Attachment, profile_for, unique_slug
from .sources import SOURCE_PAGE_SLUGS
from .taxonomy import CATEGORY_SLUGS, YEAR_LEVEL_SLUGS

User = get_user_model()


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id",
            "kind",
            "url",
            "original_filename",
            "content_type",
            "size",
            "width",
            "height",
            "caption",
            "order",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        # Local-dev uploads store a relative path; make it absolute for the frontend.
        request = self.context.get("request")
        if request is not None and obj.url.startswith("/"):
            return request.build_absolute_uri(obj.url)
        return obj.url


class AttachmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["caption", "order"]


class AnnouncementListSerializer(serializers.ModelSerializer):
    excerpt = serializers.CharField(read_only=True)
    source_page_name = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    year_level_name = serializers.CharField(read_only=True)
    author_name = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "published",
            "category",
            "category_name",
            "year_level",
            "year_level_name",
            "author",
            "author_name",
            "cover_image",
            "image_count",
            "file_count",
            "source_page",
            "source_page_name",
            "source_url",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def get_author_name(self, obj):
        """A human label for the byline; never the email address."""
        author = obj.author
        if author is None:
            return ""
        profile = getattr(author, "profile", None)
        if profile is not None and profile.full_name:
            return profile.full_name
        return author.get_full_name() or author.username

    def get_cover_image(self, obj):
        cover = obj.cover_image
        if cover is None:
            return None
        return AttachmentSerializer(cover, context=self.context).data

    def get_image_count(self, obj):
        return sum(1 for a in obj.attachments.all() if a.kind == Attachment.Kind.IMAGE)

    def get_file_count(self, obj):
        return sum(1 for a in obj.attachments.all() if a.kind == Attachment.Kind.FILE)


class AnnouncementDetailSerializer(AnnouncementListSerializer):
    images = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()

    class Meta(AnnouncementListSerializer.Meta):
        fields = AnnouncementListSerializer.Meta.fields + ["body", "images", "files"]

    def get_images(self, obj):
        images = [a for a in obj.attachments.all() if a.kind == Attachment.Kind.IMAGE]
        return AttachmentSerializer(images, many=True, context=self.context).data

    def get_files(self, obj):
        files = [a for a in obj.attachments.all() if a.kind == Attachment.Kind.FILE]
        return AttachmentSerializer(files, many=True, context=self.context).data


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    """Admin create/update. Slug is derived from the title unless one is given."""

    slug = serializers.SlugField(required=False, allow_blank=True, max_length=80)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "slug",
            "body",
            "published",
            "category",
            "year_level",
            "source_page",
            "source_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_category(self, value):
        value = (value or "").strip()
        if value and value not in CATEGORY_SLUGS:
            raise serializers.ValidationError("Not one of the announcement categories.")
        return value

    def validate_year_level(self, value):
        value = (value or "").strip()
        if value and value not in YEAR_LEVEL_SLUGS:
            raise serializers.ValidationError("Not one of the year levels.")
        return value

    def validate_source_page(self, value):
        value = (value or "").strip()
        if value and value not in SOURCE_PAGE_SLUGS:
            raise serializers.ValidationError("Not one of the watched pages.")
        return value

    def validate_source_url(self, value):
        value = (value or "").strip()
        if value and not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Must be a full http(s) link.")
        return value

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        return value

    def validate(self, attrs):
        instance = self.instance
        requested_slug = (attrs.get("slug") or "").strip()

        if requested_slug:
            base = slugify(requested_slug)
            if not base:
                raise serializers.ValidationError({"slug": "Not a usable slug."})
            taken = Announcement.objects.filter(slug=base)
            if instance is not None:
                taken = taken.exclude(pk=instance.pk)
            if taken.exists():
                raise serializers.ValidationError({"slug": "That slug is already taken."})
            attrs["slug"] = base
        elif instance is None:
            attrs["slug"] = unique_slug(attrs["title"], Announcement.objects.all())
        else:
            # Editing without touching the slug: keep the shareable link stable.
            attrs.pop("slug", None)
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            validated_data["author"] = request.user
        return super().create(validated_data)


class AttachmentUploadSerializer(serializers.Serializer):
    """Validates the multipart payload for POST .../attachments/."""

    file = serializers.FileField()
    kind = serializers.ChoiceField(choices=Attachment.Kind.choices)
    caption = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    order = serializers.IntegerField(required=False, min_value=0, default=0)


class LoginSerializer(serializers.Serializer):
    """Sign in with an email address.

    The field is still called `username` so old clients keep working, but the
    label everywhere in the UI is Email. The bootstrap admin account, which
    predates invites and may have no email set, can still use its username -
    locking the only admin out of their own site would be a poor trade.
    """

    username = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(
        max_length=128, trim_whitespace=False, style={"input_type": "password"}
    )

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter your email address.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Used both for the forced first-login change and voluntary changes."""

    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("That is not your current password.")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        try:
            # Runs every rule in AUTH_PASSWORD_VALIDATORS, including the
            # character mix and similarity to this account's own email.
            validate_password(value, user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages))
        return value

    def validate(self, attrs):
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Choose a password you have not used here before."}
            )
        return attrs


class AcceptInviteSerializer(serializers.Serializer):
    """Set a password using an invite link, with no old password to supply."""

    token = serializers.CharField(max_length=128, trim_whitespace=True)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_new_password(self, value):
        # The user this will belong to, so similarity to their own email is
        # judged against the right account.
        user = self.context.get("invited_user")
        try:
            validate_password(value, user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages))
        return value


class UserSerializer(serializers.ModelSerializer):
    """The signed-in account, as the dashboard needs to know it."""

    role = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    must_change_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "is_staff",
            "must_change_password",
            "last_login",
        ]
        read_only_fields = fields

    def _profile(self, obj):
        return profile_for(obj)

    def get_role(self, obj):
        return self._profile(obj).role

    def get_full_name(self, obj):
        return self._profile(obj).full_name or obj.get_full_name()

    def get_must_change_password(self, obj):
        return self._profile(obj).must_change_password


class PublisherSerializer(serializers.ModelSerializer):
    """A managed account as it appears in the admin's Publishers table."""

    role = serializers.CharField(source="profile.role", read_only=True)
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    must_change_password = serializers.BooleanField(
        source="profile.must_change_password", read_only=True
    )
    invite_expired = serializers.BooleanField(
        source="profile.invite_expired", read_only=True
    )
    invited_at = serializers.DateTimeField(source="profile.invited_at", read_only=True)
    password_changed_at = serializers.DateTimeField(
        source="profile.password_changed_at", read_only=True
    )
    announcement_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "must_change_password",
            "invite_expired",
            "invited_at",
            "password_changed_at",
            "last_login",
            "announcement_count",
        ]
        read_only_fields = fields


class InviteSerializer(serializers.Serializer):
    """Add a publisher by email. The password is generated, never chosen here."""

    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )

    def validate_email(self, value):
        value = value.strip().lower()
        # The address doubles as the username, and that column is 150 wide.
        # Caught here so it is a field error, not a database crash.
        if len(value) > 150:
            raise serializers.ValidationError("That email address is too long.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email already has an account.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That email already has an account.")
        return value

    def validate_full_name(self, value):
        return (value or "").strip()


class PublisherUpdateSerializer(serializers.Serializer):
    """The two things an admin may change about an existing account."""

    is_active = serializers.BooleanField(required=False)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_full_name(self, value):
        return (value or "").strip()
