from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers

from .models import Announcement, Attachment, unique_slug
from .sources import SOURCE_PAGE_SLUGS

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
            "source_page",
            "source_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

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
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False,
                                     style={"input_type": "password"})


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "last_login"]
        read_only_fields = fields
