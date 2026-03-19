from django.contrib import admin

from .models import Alert, Circle, CircleMembership, FeedEntry, Notification, Task, VoiceLog


@admin.register(Circle)
class CircleAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'care_recipient', 'created_by', 'created_at')
	search_fields = ('name', 'care_recipient', 'created_by__email')


@admin.register(CircleMembership)
class CircleMembershipAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'user', 'role', 'joined_at')
	list_filter = ('role',)
	search_fields = ('circle__name', 'user__email')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'title', 'sent_by', 'recipient', 'created_at', 'read_at')
	list_filter = ('read_at', 'created_at')
	search_fields = ('circle__name', 'sent_by__email', 'recipient__email', 'title')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'title', 'severity', 'status', 'created_by', 'updated_at')
	list_filter = ('severity', 'status', 'updated_at')
	search_fields = ('circle__name', 'title', 'message')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'title', 'task_type', 'urgency', 'status', 'claimed_by', 'due_at')
	list_filter = ('task_type', 'urgency', 'status')
	search_fields = ('circle__name', 'title', 'description')


@admin.register(FeedEntry)
class FeedEntryAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'entry_type', 'source', 'title', 'created_by', 'created_at')
	list_filter = ('entry_type', 'source', 'created_at')
	search_fields = ('circle__name', 'title', 'content')


@admin.register(VoiceLog)
class VoiceLogAdmin(admin.ModelAdmin):
	list_display = ('id', 'circle', 'audio_label', 'status', 'retry_count', 'created_by', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('circle__name', 'audio_label', 'transcript', 'error_message')
