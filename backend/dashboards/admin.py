from django.contrib import admin
from .models import Dashboard, Widget

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'is_public', 'created_at']
    list_filter = ['is_default', 'is_public', 'created_at']
    search_fields = ['name', 'description', 'user__username']

@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ['title', 'dashboard', 'widget_type', 'is_visible', 'refresh_interval']
    list_filter = ['widget_type', 'is_visible', 'dashboard']
    search_fields = ['title', 'dashboard__name']
