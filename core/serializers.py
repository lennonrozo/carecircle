from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Alert, Circle, CircleMembership, FeedEntry, Notification, Task, VoiceLog


User = get_user_model()


class CircleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Circle
        fields = ['id', 'name', 'care_recipient']
        read_only_fields = ['id']


class CircleListSerializer(serializers.ModelSerializer):
    my_role = serializers.CharField(read_only=True)

    class Meta:
        model = Circle
        fields = ['id', 'name', 'care_recipient', 'my_role', 'created_at']


class CircleDetailSerializer(serializers.ModelSerializer):
    my_role = serializers.CharField(read_only=True)

    class Meta:
        model = Circle
        fields = ['id', 'name', 'care_recipient', 'created_by', 'my_role', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class CircleMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CircleMembership
        fields = ['user_id', 'email', 'full_name', 'role', 'joined_at']

    def get_full_name(self, obj):
        full_name = obj.user.get_full_name()
        return full_name if full_name else obj.user.username


class CircleInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[CircleMembership.Role.MEMBER],
        default=CircleMembership.Role.MEMBER,
    )

    def validate_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError('No user exists with this email.') from exc
        self.context['invite_user'] = user
        return value


class NotificationSerializer(serializers.ModelSerializer):
    sent_by_name = serializers.CharField(source='sent_by.get_full_name', read_only=True)
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'sent_by_name', 'recipient_name', 'created_at', 'read_at']
        read_only_fields = ['id', 'created_at']


class NotificationSendSerializer(serializers.Serializer):
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'username']


class NotificationListSerializer(serializers.ModelSerializer):
    sent_by_name = serializers.CharField(source='sent_by.get_full_name', read_only=True)
    circle_name = serializers.CharField(source='circle.name', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'sent_by_name', 'circle_name', 'created_at', 'read_at']
        read_only_fields = ['id', 'created_at', 'sent_by_name', 'circle_name']


class AlertSerializer(serializers.ModelSerializer):
    circle_name = serializers.CharField(source='circle.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    addressed_by_name = serializers.SerializerMethodField()
    dismissed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            'id',
            'title',
            'message',
            'severity',
            'status',
            'circle_name',
            'created_by_name',
            'addressed_by_name',
            'dismissed_by_name',
            'created_at',
            'updated_at',
            'addressed_at',
            'dismissed_at',
        ]
        read_only_fields = [
            'id',
            'circle_name',
            'created_by_name',
            'addressed_by_name',
            'dismissed_by_name',
            'created_at',
            'updated_at',
            'addressed_at',
            'dismissed_at',
        ]

    def _display_name(self, user):
        if not user:
            return None
        return user.get_full_name() or user.username

    def get_created_by_name(self, obj):
        return self._display_name(obj.created_by)

    def get_addressed_by_name(self, obj):
        return self._display_name(obj.addressed_by)

    def get_dismissed_by_name(self, obj):
        return self._display_name(obj.dismissed_by)


class AlertUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ['title', 'message', 'severity', 'status']


class TaskSerializer(serializers.ModelSerializer):
    circle_name = serializers.CharField(source='circle.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    claimed_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'description',
            'task_type',
            'urgency',
            'status',
            'due_at',
            'circle_name',
            'created_by_name',
            'claimed_by_name',
            'verified_by_name',
            'claimed_at',
            'claimed_expires_at',
            'verified_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'circle_name',
            'created_by_name',
            'claimed_by_name',
            'verified_by_name',
            'claimed_at',
            'claimed_expires_at',
            'verified_at',
            'created_at',
            'updated_at',
        ]

    def _display_name(self, user):
        if not user:
            return None
        return user.get_full_name() or user.username

    def get_created_by_name(self, obj):
        return self._display_name(obj.created_by)

    def get_claimed_by_name(self, obj):
        return self._display_name(obj.claimed_by)

    def get_verified_by_name(self, obj):
        return self._display_name(obj.verified_by)


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['title', 'description', 'task_type', 'urgency', 'due_at']


class FeedEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_initial = serializers.SerializerMethodField()

    class Meta:
        model = FeedEntry
        fields = [
            'id',
            'entry_type',
            'source',
            'title',
            'content',
            'tags',
            'created_by_name',
            'created_by_initial',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by_name', 'created_by_initial', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    def get_created_by_initial(self, obj):
        name = self.get_created_by_name(obj)
        if not name:
            return 'AI' if obj.source == FeedEntry.Source.AI else 'CC'
        parts = [part for part in name.split() if part]
        if not parts:
            return 'CC'
        if len(parts) == 1:
            return parts[0][0].upper()
        return f'{parts[0][0]}{parts[-1][0]}'.upper()


class FeedEntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedEntry
        fields = ['title', 'content', 'tags']


class VoiceLogSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    has_audio = serializers.SerializerMethodField()

    class Meta:
        model = VoiceLog
        fields = [
            'id',
            'audio_label',
            'has_audio',
            'transcript',
            'extracted_signals',
            'status',
            'error_message',
            'retry_count',
            'created_by_name',
            'created_at',
            'updated_at',
            'processed_at',
            'failed_at',
        ]
        read_only_fields = [
            'id',
            'has_audio',
            'extracted_signals',
            'status',
            'error_message',
            'retry_count',
            'created_by_name',
            'created_at',
            'updated_at',
            'processed_at',
            'failed_at',
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return 'Caregiver'
        return obj.created_by.get_full_name() or obj.created_by.username

    def get_has_audio(self, obj):
        return bool(obj.audio_file)


class VoiceLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceLog
        fields = ['audio_label', 'transcript', 'audio_file']


class VoiceLogRetrySerializer(serializers.Serializer):
    pass