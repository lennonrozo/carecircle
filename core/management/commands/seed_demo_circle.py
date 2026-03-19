from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Alert, Circle, CircleMembership, FeedEntry, Task, VoiceLog


User = get_user_model()


DEMO_CIRCLE_NAME = 'Generic CareCircle Demo'
DEMO_CARE_RECIPIENT = 'Margaret Johnson'

DEMO_USERS = [
    {
        'username': 'demo_admin_sarah',
        'email': 'demo.admin@carecircle.local',
        'first_name': 'Sarah',
        'last_name': 'Johnson',
        'password': 'CareCircleAdmin!2026',
        'role': CircleMembership.Role.OWNER,
    },
    {
        'username': 'demo_member_james',
        'email': 'demo.james@carecircle.local',
        'first_name': 'James',
        'last_name': 'Wilson',
        'password': 'CareCircleMember!2026',
        'role': CircleMembership.Role.MEMBER,
    },
    {
        'username': 'demo_member_anita',
        'email': 'demo.anita@carecircle.local',
        'first_name': 'Anita',
        'last_name': 'Patel',
        'password': 'CareCircleMember!2026',
        'role': CircleMembership.Role.MEMBER,
    },
    {
        'username': 'demo_member_rita',
        'email': 'demo.rita@carecircle.local',
        'first_name': 'Rita',
        'last_name': 'Sharma',
        'password': 'CareCircleMember!2026',
        'role': CircleMembership.Role.MEMBER,
    },
]

DEMO_ALERTS = [
    {
        'title': 'Hydration trend dipped this week',
        'message': 'Margaret has had fewer water reminders logged than usual over the last three days.',
        'severity': Alert.Severity.WATCH,
        'status': Alert.Status.ACTIVE,
    },
    {
        'title': 'Mobility check requested',
        'message': 'A follow-up is needed after the latest note mentioned slower movement getting out of bed.',
        'severity': Alert.Severity.INFO,
        'status': Alert.Status.ACTIVE,
    },
]

DEMO_TASKS = [
    {
        'title': 'Pharmacy pickup — prescription refill',
        'description': 'Collect the latest refill before Thursday evening.',
        'task_type': Task.TaskType.LOGISTICS,
        'urgency': Task.Urgency.HIGH,
        'status': Task.Status.OPEN,
        'due_offset_days': 2,
    },
    {
        'title': 'Weekly check-in call with Margaret',
        'description': 'Short wellbeing call and reminder about upcoming appointments.',
        'task_type': Task.TaskType.EMOTIONAL,
        'urgency': Task.Urgency.MEDIUM,
        'status': Task.Status.OPEN,
        'due_offset_days': 3,
    },
    {
        'title': 'Morning medication — Tuesday',
        'description': 'Confirm medication was taken with breakfast.',
        'task_type': Task.TaskType.MEDICAL,
        'urgency': Task.Urgency.HIGH,
        'status': Task.Status.CLAIMED,
        'due_offset_days': 0,
        'claim_email': 'demo.james@carecircle.local',
    },
    {
        'title': 'GP appointment transport',
        'description': 'Arrange and complete transport to the GP appointment.',
        'task_type': Task.TaskType.LOGISTICS,
        'urgency': Task.Urgency.LOW,
        'status': Task.Status.VERIFIED,
        'due_offset_days': -2,
        'verify_email': 'demo.admin@carecircle.local',
    },
    {
        'title': 'Sunday lunch visit',
        'description': 'Visit during lunch and note appetite and mood.',
        'task_type': Task.TaskType.EMOTIONAL,
        'urgency': Task.Urgency.LOW,
        'status': Task.Status.VERIFIED,
        'due_offset_days': -3,
        'verify_email': 'demo.anita@carecircle.local',
    },
]

DEMO_FEED_ENTRIES = [
    {
        'entry_type': FeedEntry.EntryType.SYSTEM,
        'source': FeedEntry.Source.AI,
        'title': 'AI Health Summary',
        'content': "Voice log from this morning noted that Margaret mentioned not wanting much water and feeling tired. Mobility appeared reduced compared to last week's notes.",
        'tags': ['Hydration · Low', 'Fatigue · Present', 'Mobility · Reduced'],
        'created_by_email': None,
    },
    {
        'entry_type': FeedEntry.EntryType.HUMAN,
        'source': FeedEntry.Source.MEMBER,
        'title': '',
        'content': "Visited this afternoon. Margaret was in good spirits, watched some TV together. She ate most of her dinner and took medication.",
        'tags': [],
        'created_by_email': 'demo.james@carecircle.local',
    },
    {
        'entry_type': FeedEntry.EntryType.SYSTEM,
        'source': FeedEntry.Source.ALERT,
        'title': 'Health Watch · Hydration',
        'content': 'Low hydration signals detected across 3 consecutive days of logs. No action required — keep this in mind during the next visit.',
        'tags': ['watch'],
        'created_by_email': None,
    },
]

DEMO_VOICE_LOGS = [
    {
        'audio_label': 'Morning check-in',
        'transcript': "Margaret said she felt tired and had less water than usual this morning.",
        'status': VoiceLog.Status.COMPLETED,
        'signals': ['Hydration · Watch', 'Fatigue · Present'],
        'created_by_email': 'demo.admin@carecircle.local',
    },
    {
        'audio_label': 'Evening visit update',
        'transcript': "She ate well this evening and was in a positive mood watching television.",
        'status': VoiceLog.Status.COMPLETED,
        'signals': ['Mood · Positive', 'Appetite · Tracked'],
        'created_by_email': 'demo.james@carecircle.local',
    },
    {
        'audio_label': 'Kitchen note retry demo',
        'transcript': 'This should fail once before retry and then complete.',
        'status': VoiceLog.Status.FAILED,
        'signals': [],
        'error_message': 'Transcription service timed out. Retry available.',
        'created_by_email': 'demo.anita@carecircle.local',
    },
]


class Command(BaseCommand):
    help = 'Seed one generic demo circle with one admin and members for UI/API testing.'

    def handle(self, *args, **options):
        created_users = []
        owner_user = None

        for payload in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=payload['email'],
                defaults={
                    'username': payload['username'],
                    'first_name': payload['first_name'],
                    'last_name': payload['last_name'],
                },
            )

            if created:
                user.set_password(payload['password'])
                user.save(update_fields=['password'])
                created_users.append(user.email)
            else:
                if not user.username:
                    user.username = payload['username']
                user.first_name = payload['first_name']
                user.last_name = payload['last_name']
                user.set_password(payload['password'])
                user.save(update_fields=['username', 'first_name', 'last_name', 'password'])

            if payload['role'] == CircleMembership.Role.OWNER:
                owner_user = user

        if owner_user is None:
            raise RuntimeError('Owner user payload missing.')

        circle, _ = Circle.objects.get_or_create(
            name=DEMO_CIRCLE_NAME,
            defaults={
                'care_recipient': DEMO_CARE_RECIPIENT,
                'created_by': owner_user,
            },
        )

        if circle.created_by_id != owner_user.id:
            circle.created_by = owner_user
            circle.care_recipient = DEMO_CARE_RECIPIENT
            circle.save(update_fields=['created_by', 'care_recipient'])

        for payload in DEMO_USERS:
            user = User.objects.get(email=payload['email'])
            CircleMembership.objects.update_or_create(
                circle=circle,
                user=user,
                defaults={'role': payload['role']},
            )

        existing_titles = set(Alert.objects.filter(circle=circle).values_list('title', flat=True))
        for payload in DEMO_ALERTS:
            if payload['title'] in existing_titles:
                continue
            Alert.objects.create(
                circle=circle,
                created_by=owner_user,
                title=payload['title'],
                message=payload['message'],
                severity=payload['severity'],
                status=payload['status'],
            )

        existing_task_titles = set(Task.objects.filter(circle=circle).values_list('title', flat=True))
        now = timezone.now()
        for payload in DEMO_TASKS:
            if payload['title'] in existing_task_titles:
                continue

            task = Task(
                circle=circle,
                created_by=owner_user,
                title=payload['title'],
                description=payload['description'],
                task_type=payload['task_type'],
                urgency=payload['urgency'],
                status=payload['status'],
                due_at=now + timedelta(days=payload['due_offset_days']),
            )

            if payload['status'] == Task.Status.CLAIMED:
                claimed_user = User.objects.get(email=payload['claim_email'])
                task.claimed_by = claimed_user
                task.claimed_at = now - timedelta(hours=1)
                task.claimed_expires_at = now + timedelta(hours=3)

            if payload['status'] == Task.Status.VERIFIED:
                verified_user = User.objects.get(email=payload['verify_email'])
                task.verified_by = verified_user
                task.verified_at = now - timedelta(days=1)

            task.save()

        existing_feed_signatures = set(
            FeedEntry.objects.filter(circle=circle).values_list('title', 'content')
        )
        for payload in DEMO_FEED_ENTRIES:
            signature = (payload['title'], payload['content'])
            if signature in existing_feed_signatures:
                continue

            created_by = None
            if payload['created_by_email']:
                created_by = User.objects.get(email=payload['created_by_email'])

            FeedEntry.objects.create(
                circle=circle,
                created_by=created_by,
                entry_type=payload['entry_type'],
                source=payload['source'],
                title=payload['title'],
                content=payload['content'],
                tags=payload['tags'],
            )

        existing_audio_labels = set(VoiceLog.objects.filter(circle=circle).values_list('audio_label', flat=True))
        for payload in DEMO_VOICE_LOGS:
            if payload['audio_label'] in existing_audio_labels:
                continue

            created_by = None
            if payload['created_by_email']:
                created_by = User.objects.get(email=payload['created_by_email'])

            voice_log = VoiceLog.objects.create(
                circle=circle,
                created_by=created_by,
                audio_label=payload['audio_label'],
                transcript=payload['transcript'],
                extracted_signals=payload.get('signals', []),
                status=payload['status'],
                error_message=payload.get('error_message', ''),
            )

            if payload['status'] == VoiceLog.Status.COMPLETED:
                voice_log.processed_at = timezone.now() - timedelta(hours=2)
                voice_log.save(update_fields=['processed_at'])
            if payload['status'] == VoiceLog.Status.FAILED:
                voice_log.failed_at = timezone.now() - timedelta(hours=1)
                voice_log.save(update_fields=['failed_at'])

        self.stdout.write(self.style.SUCCESS('Demo circle is ready.'))
        self.stdout.write(f'Circle: {circle.name} (id={circle.id})')
        if created_users:
            self.stdout.write('Created users: ' + ', '.join(created_users))
        else:
            self.stdout.write('No new users created; existing demo users refreshed.')

        self.stdout.write('Credentials:')
        for payload in DEMO_USERS:
            role_label = 'admin/owner' if payload['role'] == CircleMembership.Role.OWNER else 'member'
            self.stdout.write(
                f"- {payload['first_name']} {payload['last_name']} | {role_label} | {payload['email']} | {payload['password']}"
            )
