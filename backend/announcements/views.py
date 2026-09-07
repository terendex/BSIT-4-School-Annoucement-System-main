import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .emails import send_invite_email
from .models import Announcement, Attachment, Profile, profile_for
from .pagination import StandardPagination
from .passwords import generate_temp_password
from .permissions import CanEditAnnouncement, IsAdmin, IsStaffMember, is_admin
from .serializers import (
    AnnouncementDetailSerializer,
    AnnouncementListSerializer,
    AnnouncementWriteSerializer,
    AttachmentSerializer,
    AttachmentUpdateSerializer,
    AttachmentUploadSerializer,
    ChangePasswordSerializer,
    InviteSerializer,
    LoginSerializer,
    PublisherSerializer,
    PublisherUpdateSerializer,
    UserSerializer,
)
from .sources import SOURCE_PAGES
from .storage import delete_attachment, upload_attachment
from .taxonomy import CATEGORIES, YEAR_LEVELS
from .throttles import UploadRateThrottle
from .validators import validate_upload

User = get_user_model()

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def resolve_login_user(identifier: str):
    """Find the account for what was typed in the Email box.

    Email first, since that is what the form asks for; username second so the
    bootstrap admin - created from ADMIN_USERNAME before invites existed, and
    possibly with no email at all - is never locked out of their own site.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    return (
        User.objects.filter(email__iexact=identifier).first()
        or User.objects.filter(username__iexact=identifier).first()
    )


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


class LoginView(APIView):
    """Rate-limited sign in for admins and publishers. Returns a JWT pair."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    # One message for every failure, so the response never reveals whether an
    # address has an account here.
    INVALID = "Invalid email or password."

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["username"]

        account = resolve_login_user(identifier)
        user = None
        if account is not None:
            user = authenticate(
                request,
                username=account.username,
                password=serializer.validated_data["password"],
            )

        if user is None or not user.is_active or not user.is_staff:
            logger.info("Failed login attempt for %r", identifier)
            return Response(
                {"detail": self.INVALID}, status=status.HTTP_401_UNAUTHORIZED
            )

        profile = profile_for(user)
        if profile.temp_password_expired:
            logger.info("Expired invite used for %r", identifier)
            return Response(
                {
                    "detail": (
                        "This invitation has expired. Ask an admin to send you "
                        "a new one."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # A publisher still on their emailed password gets tokens, but every
        # other endpoint refuses them until the password is replaced.
        return Response(issue_tokens(user))


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "login"


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Set your own password - forced after an invite, optional afterwards.

    Deliberately NOT behind IsStaffMember: an account still holding a
    temporary password is blocked from every other endpoint, and this is the
    one door it must be able to walk through.
    """

    permission_classes = [IsAuthenticated]
    # Not the "login" scope: five tries a minute is brute-force protection for
    # anonymous guessing, but here the caller already holds a valid token and
    # their current password. Sharing that budget would lock an invited
    # publisher out mid-onboarding for fumbling the password rules.
    throttle_scope = "password"

    def post(self, request):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        profile = profile_for(user)
        profile.must_change_password = False
        profile.temp_password_expires_at = None
        profile.password_changed_at = timezone.now()
        profile.save(
            update_fields=[
                "must_change_password",
                "temp_password_expires_at",
                "password_changed_at",
            ]
        )

        logger.info("Password changed for user id %s", user.id)
        # Hand back a fresh pair so the caller is not bounced to the login
        # screen mid-flow. Note this does not retire the previous tokens -
        # JWTs are stateless, so the old access token stays valid until it
        # expires on its own (30 minutes, per SIMPLE_JWT above).
        return Response(issue_tokens(user))


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
        params = self.request.query_params
        queryset = (
            Announcement.objects.published()
            .with_attachments()
            .in_category((params.get("category") or "").strip())
            .for_year_level((params.get("year") or "").strip())
            .order_by("-created_at", "-id")
        )
        search = (params.get("q") or "").strip()
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


class FeedStateView(APIView):
    """Tiny fingerprint of the published feed, for polling.

    Returns only a count and the newest updated_at, so the frontend can tell
    whether anything changed without refetching the whole list every minute -
    which matters when classmates leave the page open on mobile data.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public"

    def get(self, request):
        # Every filter the list view accepts has to be honoured here too. The
        # page's fingerprint is this endpoint's own answer, so if the two
        # disagreed the frontend would see a change that never resolves and
        # reload on a loop for as long as the reader left the tab open.
        params = request.query_params
        queryset = (
            Announcement.objects.published()
            .in_category((params.get("category") or "").strip())
            .for_year_level((params.get("year") or "").strip())
        )
        search = (params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(title__icontains=search)
        aggregate = queryset.aggregate(last_modified=Max("updated_at"))
        last_modified = aggregate["last_modified"]
        # Serialize through DRF's field, not .isoformat(): the announcement
        # serializer renders in the active timezone (+08:00) while a raw
        # isoformat gives UTC (+00:00). Mismatched strings made the frontend
        # think the feed had changed on every single poll.
        return Response(
            {
                "count": queryset.count(),
                "last_modified": serializers.DateTimeField().to_representation(
                    last_modified
                )
                if last_modified
                else None,
            }
        )


class SourcePageListView(APIView):
    """The Facebook pages the admin re-posts from, for the editor dropdown."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public"

    def get(self, request):
        return Response({"results": SOURCE_PAGES})


class TaxonomyView(APIView):
    """The filter vocabulary - categories and year levels, with their labels.

    Served so the filter bar, the editor dropdowns and the card badges all read
    from one list instead of three copies drifting apart.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public"

    def get(self, request):
        return Response({"categories": CATEGORIES, "year_levels": YEAR_LEVELS})


# --------------------------------------------------------------------------
# Admin (JWT protected)
# --------------------------------------------------------------------------
class AdminAnnouncementViewSet(viewsets.ModelViewSet):
    """The dashboard's CRUD, drafts included.

    Both roles see the whole board - a publisher needs to know what has already
    been posted before adding to it. What differs is what they may change, and
    that is decided per object by CanEditAnnouncement.
    """

    permission_classes = [CanEditAnnouncement]
    pagination_class = StandardPagination
    lookup_field = "pk"

    def get_queryset(self):
        params = self.request.query_params
        queryset = (
            Announcement.objects.with_attachments()
            .select_related("author__profile")
            .in_category((params.get("category") or "").strip())
            .for_year_level((params.get("year") or "").strip())
            .order_by("-created_at", "-id")
        )
        published = params.get("published")
        if published in {"true", "false"}:
            queryset = queryset.filter(published=published == "true")
        if params.get("mine") == "true":
            queryset = queryset.filter(author=self.request.user)
        search = (params.get("q") or "").strip()
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
    """Edit an attachment caption/order, or delete it (blob included).

    An attachment inherits its announcement's rule: a publisher may manage the
    images on a post they wrote, and nothing else. Deleting an attachment is
    editing the post, not deleting it, so publishers keep that on their own.
    """

    permission_classes = [IsStaffMember]
    queryset = Attachment.objects.select_related("announcement")

    def get_object(self):
        attachment = super().get_object()
        if self.request.method not in {"GET", "HEAD", "OPTIONS"}:
            announcement = attachment.announcement
            if not is_admin(self.request.user) and announcement.author_id != self.request.user.id:
                raise PermissionDenied("You can only change your own announcements.")
        return attachment

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AttachmentUpdateSerializer
        return AttachmentSerializer

    def perform_destroy(self, instance):
        delete_attachment(instance)
        instance.delete()


# --------------------------------------------------------------------------
# Publishers (admin only)
# --------------------------------------------------------------------------
def issue_temp_password(profile) -> str:
    """Give this account a fresh single-use password and return it.

    Returned to the caller only so it can be put in the email. It is stored
    hashed like any other password and never written to a log or a response.
    """
    password = generate_temp_password()
    user = profile.user
    user.set_password(password)
    user.save(update_fields=["password"])

    profile.must_change_password = True
    profile.temp_password_expires_at = timezone.now() + timezone.timedelta(
        days=settings.INVITE_EXPIRY_DAYS
    )
    profile.invited_at = timezone.now()
    profile.save(
        update_fields=["must_change_password", "temp_password_expires_at", "invited_at"]
    )
    return password


class PublisherViewSet(viewsets.ViewSet):
    """Admin-only management of the accounts that may post.

    An admin adds a publisher by email; the account is created with a generated
    password that is mailed out and must be replaced on first sign in.
    """

    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        return (
            User.objects.filter(is_staff=True)
            .select_related("profile")
            .annotate(announcement_count=Count("announcements"))
            .order_by("profile__role", "email", "username")
        )

    def list(self, request):
        # Backfill profiles for accounts made before roles existed, so the
        # table never shows a blank role for the original admin.
        for user in User.objects.filter(is_staff=True, profile__isnull=True):
            profile_for(user)
        return Response(
            {"results": PublisherSerializer(self.get_queryset(), many=True).data}
        )

    def create(self, request):
        """Invite a publisher: create the account, mail the temp password."""
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        full_name = serializer.validated_data.get("full_name", "")

        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email, is_staff=True, is_superuser=False
            )
            if full_name:
                parts = full_name.split()
                user.first_name = parts[0][:150]
                user.last_name = " ".join(parts[1:])[:150]
                user.save(update_fields=["first_name", "last_name"])

            profile = Profile.objects.create(
                user=user,
                role=Profile.Role.PUBLISHER,
                full_name=full_name,
                invited_by=request.user,
            )
            password = issue_temp_password(profile)

        delivered = send_invite_email(
            email=email,
            password=password,
            expires_at=profile.temp_password_expires_at,
            inviter=request.user,
            full_name=full_name,
        )

        data = PublisherSerializer(
            self.get_queryset().get(pk=user.pk)
        ).data
        data["invite_email_sent"] = delivered
        if not delivered:
            data["detail"] = (
                "The account was created but the invite email could not be sent. "
                "Check the mail settings, then use Resend invite."
            )
        return Response(
            data,
            status=status.HTTP_201_CREATED if delivered else status.HTTP_207_MULTI_STATUS,
        )

    def partial_update(self, request, pk=None):
        """Rename an account, or switch it off without losing their posts."""
        user = self._get_managed_user(request, pk)
        serializer = PublisherUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "is_active" in data:
            user.is_active = data["is_active"]
            user.save(update_fields=["is_active"])
        if "full_name" in data:
            profile = profile_for(user)
            profile.full_name = data["full_name"]
            profile.save(update_fields=["full_name"])

        return Response(PublisherSerializer(self.get_queryset().get(pk=user.pk)).data)

    def destroy(self, request, pk=None):
        """Remove an account. Their announcements stay on the board.

        Announcement.author is SET_NULL, so deleting a publisher never takes a
        class suspension notice down with it.
        """
        user = self._get_managed_user(request, pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, pk=None):
        """Issue a new temporary password and mail it. The old one stops working.

        Covers both halves of the same need: re-sending an invite that was lost
        before it was ever used, and resetting the password of someone who has
        been posting for months and has forgotten it. There is no self-service
        reset - a class announcement board does not need one, and an admin is
        always within reach.
        """
        user = self._get_managed_user(request, pk)
        profile = profile_for(user)
        password = issue_temp_password(profile)

        delivered = send_invite_email(
            email=user.email or user.username,
            password=password,
            expires_at=profile.temp_password_expires_at,
            inviter=request.user,
            full_name=profile.full_name,
        )
        if not delivered:
            return Response(
                {"detail": "Could not send the email. Check the mail settings."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(PublisherSerializer(self.get_queryset().get(pk=user.pk)).data)

    def _get_managed_user(self, request, pk):
        """The target account, with the rules an admin cannot talk their way past."""
        try:
            user = self.get_queryset().get(pk=pk)
        except (User.DoesNotExist, ValueError):
            raise NotFound("No such account.")

        if user.pk == request.user.pk:
            raise PermissionDenied("You cannot change your own account here.")
        if profile_for(user).is_admin:
            raise PermissionDenied("Admin accounts are managed outside the dashboard.")
        return user
