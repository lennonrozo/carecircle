from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Circle(models.Model):
	name = models.CharField(max_length=255)
	care_recipient = models.CharField(max_length=255, blank=True)
	created_by = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='created_circles',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return self.name


class CircleMembership(models.Model):
	class Role(models.TextChoices):
		OWNER = 'owner', 'Owner'
		MEMBER = 'member', 'Member'

	user = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='circle_memberships',
	)
	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='memberships',
	)
	role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
	joined_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('user', 'circle')
		ordering = ['joined_at']

	def __str__(self):
		return f'{self.user} in {self.circle} ({self.role})'


class Notification(models.Model):
	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='notifications',
	)
	sent_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		related_name='sent_notifications',
	)
	recipient = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='received_notifications',
	)
	title = models.CharField(max_length=255)
	message = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)
	read_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'Notification from {self.sent_by} to {self.recipient}: {self.title}'


class Alert(models.Model):
	class Severity(models.TextChoices):
		INFO = 'info', 'Info'
		WATCH = 'watch', 'Watch'
		URGENT = 'urgent', 'Urgent'

	class Status(models.TextChoices):
		ACTIVE = 'active', 'Active'
		ADDRESSED = 'addressed', 'Addressed'
		DISMISSED = 'dismissed', 'Dismissed'

	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='alerts',
	)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_alerts',
	)
	title = models.CharField(max_length=255)
	message = models.TextField()
	severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WATCH)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
	addressed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='addressed_alerts',
	)
	dismissed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='dismissed_alerts',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	addressed_at = models.DateTimeField(null=True, blank=True)
	dismissed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-updated_at', '-created_at']

	def __str__(self):
		return f'{self.circle} · {self.title} ({self.status})'


class Task(models.Model):
	class TaskType(models.TextChoices):
		MEDICAL = 'medical', 'Medical'
		LOGISTICS = 'logistics', 'Logistics'
		EMOTIONAL = 'emotional', 'Emotional'

	class Urgency(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'

	class Status(models.TextChoices):
		OPEN = 'open', 'Open'
		CLAIMED = 'claimed', 'Claimed'
		VERIFIED = 'verified', 'Verified'

	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='tasks',
	)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_tasks',
	)
	title = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	task_type = models.CharField(max_length=20, choices=TaskType.choices, default=TaskType.LOGISTICS)
	urgency = models.CharField(max_length=20, choices=Urgency.choices, default=Urgency.MEDIUM)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
	due_at = models.DateTimeField(null=True, blank=True)
	claimed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='claimed_tasks',
	)
	claimed_at = models.DateTimeField(null=True, blank=True)
	claimed_expires_at = models.DateTimeField(null=True, blank=True)
	verified_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='verified_tasks',
	)
	verified_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['status', 'due_at', '-updated_at']

	def __str__(self):
		return f'{self.circle} · {self.title} ({self.status})'


class FeedEntry(models.Model):
	class EntryType(models.TextChoices):
		HUMAN = 'human', 'Human'
		SYSTEM = 'system', 'System'

	class Source(models.TextChoices):
		MEMBER = 'member', 'Member'
		AI = 'ai', 'AI'
		ALERT = 'alert', 'Alert'
		TASK = 'task', 'Task'

	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='feed_entries',
	)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='feed_entries',
	)
	entry_type = models.CharField(max_length=20, choices=EntryType.choices, default=EntryType.HUMAN)
	source = models.CharField(max_length=20, choices=Source.choices, default=Source.MEMBER)
	title = models.CharField(max_length=255, blank=True)
	content = models.TextField()
	tags = models.JSONField(default=list, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		label = self.title if self.title else self.content[:50]
		return f'{self.circle} · {label}'


class VoiceLog(models.Model):
	class Status(models.TextChoices):
		QUEUED = 'queued', 'Queued'
		PROCESSING = 'processing', 'Processing'
		COMPLETED = 'completed', 'Completed'
		FAILED = 'failed', 'Failed'

	circle = models.ForeignKey(
		Circle,
		on_delete=models.CASCADE,
		related_name='voice_logs',
	)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='voice_logs',
	)
	audio_label = models.CharField(max_length=255, blank=True)
	audio_file = models.FileField(upload_to='voice_logs/%Y/%m/', blank=True, null=True)
	transcript = models.TextField(blank=True)
	extracted_signals = models.JSONField(default=list, blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
	error_message = models.CharField(max_length=255, blank=True)
	retry_count = models.PositiveSmallIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	processed_at = models.DateTimeField(null=True, blank=True)
	failed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		label = self.audio_label or (self.transcript[:40] if self.transcript else f'Voice Log #{self.id}')
		return f'{self.circle} · {label} ({self.status})'
