from django.contrib import admin
from .models import FileIntegrity


@admin.register(FileIntegrity)
class FileIntegrityAdmin(admin.ModelAdmin):
    list_display = [
        "file_path",
        "status",
        "is_change_approved",
        "last_checked",
        "change_detected_at",
    ]
    list_filter = ["status", "is_change_approved", "file_type", "last_checked"]
    search_fields = ["file_path", "change_notes"]
    readonly_fields = [
        "sha512_hash",
        "previous_hash",
        "last_checked",
        "change_detected_at",
        "approved_at",
    ]
