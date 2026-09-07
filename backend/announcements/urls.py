from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"admin/announcements", views.AdminAnnouncementViewSet,
                basename="admin-announcement")
router.register(r"admin/publishers", views.PublisherViewSet, basename="publisher")

urlpatterns = [
    # --- auth ---
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(),
         name="change-password"),

    # --- public, read-only ---
    path("announcements/", views.PublicAnnouncementListView.as_view(),
         name="public-announcement-list"),
    path("announcements/<slug:slug>/", views.PublicAnnouncementDetailView.as_view(),
         name="public-announcement-detail"),
    path("source-pages/", views.SourcePageListView.as_view(), name="source-pages"),
    path("taxonomy/", views.TaxonomyView.as_view(), name="taxonomy"),
    path("feed-state/", views.FeedStateView.as_view(), name="feed-state"),

    # --- admin, JWT ---
    path("admin/attachments/<int:pk>/", views.AdminAttachmentDetailView.as_view(),
         name="admin-attachment-detail"),
    path("", include(router.urls)),
]
