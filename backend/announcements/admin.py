from django.contrib import admin

from .models import Announcement, Attachment


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ["url", "public_id", "storage_backend", "size", "created_at"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "published", "created_at", "updated_at"]
    list_filter = ["published", "created_at"]
    search_fields = ["title", "body", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [AttachmentInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "kind", "announcement", "size", "created_at"]
    list_filter = ["kind", "storage_backend"]
    search_fields = ["original_filename", "caption"]
