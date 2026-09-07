import logging

from django.contrib.auth import authenticate
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Announcement, Attachment
from .pagination import StandardPagination
from .serializers import (
    AnnouncementDetailSerializer,
    AnnouncementListSerializer,
    AnnouncementWriteSerializer,
    AttachmentSerializer,
    AttachmentUpdateSerializer,
    AttachmentUploadSerializer,
    LoginSerializer,
    UserSerializer,
)
from .storage import delete_attachment, upload_attachment
from .throttles import UploadRateThrottle
from .validators import validate_upload

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class LoginView(APIView):
    """Rate-limited admin login. Returns a JWT access/refresh pair."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        # Only the admin account may sign in; there are no viewer accounts.
        if user is None or not user.is_active or not user.is_staff:
            logger.info("Failed admin login attempt for %r",
                        serializer.validated_data["username"])
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "login"


class MeView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# --------------------------------------------------------------------------
# Public (read-only, no auth)
# --------------------------------------------------------------------------
class PublicAnnouncementListView(generics.ListAPIView):
    """Published announcements, newest first."""

    serializer_class = AnnouncementListSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardPagination
    throttle_scope = "public"

    def get_queryset(self):
        queryset = (
            Announcement.objects.published()
            .with_attachments()
            .order_by("-created_at", "-id")
        )
        search = (self.request.query_params.get("q") or "").strip()
        if search:
            # ORM only - parameterised, never string-interpolated SQL.
            queryset = queryset.filter(title__icontains=search)
        return queryset


class PublicAnnouncementDetailView(generics.RetrieveAPIView):
    """Single published announcement by slug - the shareable link target."""

    serializer_class = AnnouncementDetailSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "slug"
    throttle_scope = "public"

    def get_queryset(self):
        return Announcement.objects.published().with_attachments()


# --------------------------------------------------------------------------
# Admin (JWT protected)
# --------------------------------------------------------------------------
class AdminAnnouncementViewSet(viewsets.ModelViewSet):
    """Full CRUD over every announcement, drafts included."""

    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination
    lookup_field = "pk"

    def get_queryset(self):
        queryset = Announcement.objects.with_attachments().order_by("-created_at", "-id")
        published = self.request.query_params.get("published")
        if published in {"true", "false"}:
            queryset = queryset.filter(published=published == "true")
        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset

    def get_serializer_class(self):
        if self.action == "add_attachment":
            return AttachmentUploadSerializer
        if self.action in {"list", "retrieve"}:
            return AnnouncementDetailSerializer
        return AnnouncementWriteSerializer

    def create(self, request, *args, **kwargs):
        write = AnnouncementWriteSerializer(data=request.data, context=self.get_serializer_context())
        write.is_valid(raise_exception=True)
        announcement = write.save()
        return Response(
            AnnouncementDetailSerializer(announcement, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = AnnouncementWriteSerializer(
            instance, data=request.data, partial=partial, context=self.get_serializer_context()
        )
        write.is_valid(raise_exception=True)
        announcement = write.save()
        return Response(
            AnnouncementDetailSerializer(announcement, context=self.get_serializer_context()).data
        )

    def perform_destroy(self, instance):
        # Remove the stored blobs before the cascade drops the rows.
        for attachment in instance.attachments.all():
            delete_attachment(attachment)
        instance.delete()

    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        throttle_classes=[UploadRateThrottle],
        serializer_class=AttachmentUploadSerializer,
    )
    def add_attachment(self, request, pk=None):
        announcement = self.get_object()
        payload = AttachmentUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        uploaded = payload.validated_data["file"]
        kind = payload.validated_data["kind"]
        safe_name = validate_upload(uploaded, kind)

        stored = upload_attachment(uploaded, kind, safe_name)
        attachment = Attachment.objects.create(
            announcement=announcement,
            kind=kind,
            original_filename=safe_name,
            content_type=(getattr(uploaded, "content_type", "") or "")[:100],
            caption=payload.validated_data.get("caption", ""),
            order=payload.validated_data.get("order", 0),
            **stored,
        )
        return Response(
            AttachmentSerializer(attachment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class AdminAttachmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Edit an attachment caption/order, or delete it (blob included)."""

    permission_classes = [IsAdminUser]
    queryset = Attachment.objects.select_related("announcement")

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AttachmentUpdateSerializer
        return AttachmentSerializer

    def perform_destroy(self, instance):
        delete_attachment(instance)
        instance.delete()
