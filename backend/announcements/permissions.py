"""Who may do what.

    Publisher  create announcements; edit their own; upload to their own
    Admin      everything, on anyone's announcement, plus managing publishers

Deleting is deliberately admin-only: a publisher who mis-posts can fix the text
themselves, but taking a notice off the board is the admin's call.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Profile, profile_for


def role_of(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    return profile_for(user).role


def is_admin(user) -> bool:
    return role_of(user) == Profile.Role.ADMIN


def must_change_password(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return profile_for(user).must_change_password


class IsStaffMember(BasePermission):
    """Signed in as either role, and finished with the temporary password.

    The second half matters: without it, an invited publisher could skip the
    forced password change simply by calling the API directly, leaving an
    account live on a credential that was emailed in plain text.
    """

    message = "Set your own password before using the dashboard."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_staff):
            return False
        return not must_change_password(user)


class IsAdmin(IsStaffMember):
    """Admin-only endpoints: managing publishers, deleting announcements."""

    message = "Only an admin can do that."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_admin(request.user)


class CanEditAnnouncement(IsStaffMember):
    """Object-level rule for the announcement endpoints.

    Reads are open to both roles - a publisher needs to see the board they are
    posting to. Writes are narrowed per object.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if is_admin(request.user):
            return True
        # Publisher: may edit their own post, may not delete anything.
        if request.method == "DELETE":
            self.message = "Only an admin can delete an announcement."
            return False
        if obj.author_id == request.user.id:
            return True
        self.message = "You can only edit your own announcements."
        return False
