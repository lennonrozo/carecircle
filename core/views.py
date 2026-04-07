from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login as auth_login
from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from datetime import timedelta
from collections import Counter

from .models import Alert, Circle, CircleMembership, FeedEntry, MemberAvailability, Notification, Task, VoiceLog
from .insights import build_characteristic_trends
from .permissions import IsCircleMember, IsCircleOwner
from .services import extract_signals_from_transcript, process_voice_log
from .serializers import (
	CircleCreateSerializer,
	CircleDetailSerializer,
	CircleInviteSerializer,
	CircleListSerializer,
	CircleMemberSerializer,
	AlertSerializer,
	AlertUpdateSerializer,
	FeedEntryCreateSerializer,
	FeedEntrySerializer,
	VoiceLogCreateSerializer,
	VoiceLogSerializer,
	TaskCreateUpdateSerializer,
	TaskSerializer,
	NotificationSendSerializer,
	NotificationSerializer,
	UserProfileSerializer,
	NotificationListSerializer,
)
from .serializers import MemberAvailabilitySerializer


User = get_user_model()


DEMO_CIRCLE_ID = 2


def get_demo_user_role_label(request):
	if not request.user.is_authenticated:
		return 'admin'

	membership = (
		CircleMembership.objects.filter(user=request.user)
		.order_by('joined_at')
		.first()
	)
	if membership is None:
		return 'member'

	if membership.role == CircleMembership.Role.OWNER:
		return 'admin'

	return 'member'


def get_request_circle_membership(request):
	if request.user.is_authenticated:
		membership = (
			CircleMembership.objects.select_related('circle')
			.filter(user=request.user)
			.order_by('joined_at')
			.first()
		)
		if membership is not None:
			return membership.circle, membership.role, request.user

	circle = Circle.objects.filter(pk=DEMO_CIRCLE_ID).first() or Circle.objects.order_by('id').first()
	owner_membership = None
	if circle is not None:
		owner_membership = (
			CircleMembership.objects.select_related('user')
			.filter(circle=circle, role=CircleMembership.Role.OWNER)
			.first()
		)
	actor = owner_membership.user if owner_membership is not None else None
	return circle, CircleMembership.Role.OWNER, actor


def get_member_circle_context(request):
	if request.user.is_authenticated:
		membership = (
			CircleMembership.objects.select_related('circle')
			.filter(user=request.user)
			.order_by('joined_at')
			.first()
		)
		if membership is None:
			raise PermissionDenied('You must be a member of a circle to access the feed.')
		return membership.circle, membership.role, request.user

	return get_request_circle_membership(request)


def get_dashboard_circle_and_role(request):
	circle, membership_role, _actor = get_request_circle_membership(request)
	role = 'admin' if membership_role == CircleMembership.Role.OWNER else 'member'
	return circle, role


def get_initials(name):
	parts = [part for part in name.split() if part]
	if not parts:
		return '?'
	if len(parts) == 1:
		return parts[0][0].upper()
	return f'{parts[0][0]}{parts[-1][0]}'.upper()


def get_available_members_now(circle, at_time=None):
	"""Return memberships (members only) that have an active availability window at at_time."""
	if at_time is None:
		at_time = timezone.now()
	return (
		CircleMembership.objects.filter(
			circle=circle,
			role=CircleMembership.Role.MEMBER,
			availabilities__available_from__lte=at_time,
			availabilities__available_until__gte=at_time,
		)
		.select_related('user')
		.prefetch_related('availabilities')
		.distinct()
	)


def get_available_members_current_or_upcoming(circle, from_time=None):
	"""Return member memberships that have any current or future availability window."""
	if from_time is None:
		from_time = timezone.now()
	return (
		CircleMembership.objects.filter(
			circle=circle,
			role=CircleMembership.Role.MEMBER,
			availabilities__available_until__gte=from_time,
		)
		.select_related('user')
		.prefetch_related('availabilities')
		.distinct()
	)


def cleanup_expired_task_claims(circle):
	if circle is None:
		return

	now = timezone.now()
	Task.objects.filter(
		circle=circle,
		status=Task.Status.CLAIMED,
		claimed_expires_at__isnull=False,
		claimed_expires_at__lte=now,
	).update(
		status=Task.Status.OPEN,
		claimed_by=None,
		claimed_at=None,
		claimed_expires_at=None,
		verified_by=None,
		verified_at=None,
	)


def build_recent_activity(circle):
	if circle is None:
		return []

	memberships = list(
		CircleMembership.objects.filter(circle=circle)
		.select_related('user')
		.order_by('-joined_at')[:3]
	)
	notifications = list(
		Notification.objects.filter(circle=circle)
		.select_related('sent_by', 'recipient')
		.order_by('-created_at')[:5]
	)
	alerts = list(
		Alert.objects.filter(circle=circle)
		.order_by('-created_at')[:5]
	)
	tasks = list(
		Task.objects.filter(circle=circle)
		.select_related('claimed_by', 'verified_by')
		.order_by('-updated_at')[:5]
	)

	activity = []
	for membership in memberships:
		member_name = membership.user.get_full_name() or membership.user.username
		activity.append(
			{
				'timestamp': membership.joined_at,
				'text': f'{member_name} joined the care circle',
				'tag': 'member',
				'color': 'sage',
				'target_url': f'/circles/{circle.id}/members/',
			}
		)

	for notification in notifications:
		if notification.sent_by:
			sender_name = notification.sent_by.get_full_name() or notification.sent_by.username
		else:
			sender_name = 'Circle admin'
		activity.append(
			{
				'timestamp': notification.created_at,
				'text': f'{sender_name} sent “{notification.title}”',
				'tag': 'notice',
				'color': 'warm' if notification.read_at is None else 'blue',
				'target_url': '/notifications/',
			}
		)

	for alert in alerts:
		activity.append(
			{
				'timestamp': alert.updated_at,
				'text': f'Alert updated: {alert.title}',
				'tag': alert.severity,
				'color': 'warm' if alert.status == Alert.Status.ACTIVE else 'blue',
				'target_url': '/alerts/',
			}
		)

	for task in tasks:
		if task.status == Task.Status.CLAIMED and task.claimed_by:
			name = task.claimed_by.get_full_name() or task.claimed_by.username
			text = f'{name} claimed “{task.title}”'
			color = 'blue'
			tag = 'claimed'
		elif task.status == Task.Status.VERIFIED:
			name = task.verified_by.get_full_name() or task.verified_by.username if task.verified_by else 'Circle member'
			text = f'{name} verified “{task.title}”'
			color = 'sage'
			tag = 'verified'
		else:
			text = f'Task updated: {task.title}'
			color = 'sage'
			tag = 'task'
		activity.append(
			{
				'timestamp': task.updated_at,
				'text': text,
				'tag': tag,
				'color': color,
				'target_url': '/tasks/',
			}
		)

	activity.sort(key=lambda item: item['timestamp'], reverse=True)
	return [
		{
			'text': item['text'],
			'tag': item['tag'],
			'color': item['color'],
			'timestamp': item['timestamp'].isoformat(),
			'target_url': item.get('target_url'),
		}
		for item in activity[:5]
	]


def advance_voice_log_pipeline(circle):
	"""
	Advance any text-only logs still sitting in QUEUED state.
	Audio-file logs are processed synchronously on upload so they never
	stay QUEUED — this handles edge cases (e.g. server restart mid-request).
	"""
	if circle is None:
		return

	stuck_logs = VoiceLog.objects.filter(
		circle=circle,
		status=VoiceLog.Status.QUEUED,
	).filter(Q(audio_file__isnull=True) | Q(audio_file=''))

	for log in stuck_logs:
		process_voice_log(log)


def build_insights_payload(circle):
	if circle is None:
		return {
			'trend_cards': [],
			'characteristic_trends': [],
			'watch_highlights': [],
			'confidence': {
				'score': 0,
				'label': 'Low confidence',
				'reason': 'No recent care activity to build insights from yet.',
			},
			'updated_at': timezone.now().isoformat(),
		}

	now = timezone.now()
	seven_days_ago = now - timedelta(days=7)
	fourteen_days_ago = now - timedelta(days=14)

	voice_recent = VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.COMPLETED, created_at__gte=fourteen_days_ago)
	voice_last_7 = voice_recent.filter(created_at__gte=seven_days_ago).count()
	voice_prev_7 = voice_recent.filter(created_at__lt=seven_days_ago).count()

	watch_alerts_active = Alert.objects.filter(circle=circle, severity=Alert.Severity.WATCH, status=Alert.Status.ACTIVE).count()
	watch_alerts_recent = Alert.objects.filter(circle=circle, severity=Alert.Severity.WATCH, created_at__gte=fourteen_days_ago).count()

	feed_recent_count = FeedEntry.objects.filter(circle=circle, created_at__gte=fourteen_days_ago).count()
	tasks_recent_count = Task.objects.filter(circle=circle, updated_at__gte=fourteen_days_ago).count()

	signal_counter = Counter()
	for log in voice_recent.only('extracted_signals'):
		for signal in (log.extracted_signals or []):
			normalized = str(signal).strip()
			if normalized:
				signal_counter[normalized] += 1

	if voice_last_7 > voice_prev_7:
		voice_direction = 'up'
		voice_note = 'More completed voice updates than the prior week.'
	elif voice_last_7 < voice_prev_7:
		voice_direction = 'down'
		voice_note = 'Fewer completed voice updates than the prior week.'
	else:
		voice_direction = 'steady'
		voice_note = 'Voice update volume is steady week-to-week.'

	if watch_alerts_active >= 3:
		watch_note = 'Several watch-level alerts are active. Keep observation frequency consistent.'
	elif watch_alerts_active > 0:
		watch_note = 'A small number of watch-level alerts are active for awareness.'
	else:
		watch_note = 'No active watch-level alerts right now.'

	top_signals = signal_counter.most_common(3)
	signal_summary = ', '.join([f'{name} ({count})' for name, count in top_signals]) if top_signals else 'No repeated signals yet.'

	evidence_points = voice_recent.count() + watch_alerts_recent + feed_recent_count
	confidence_score = min(95, evidence_points * 9)
	if confidence_score >= 70:
		confidence_label = 'High confidence'
	elif confidence_score >= 35:
		confidence_label = 'Moderate confidence'
	else:
		confidence_label = 'Low confidence'

	trend_cards = [
		{
			'title': 'Voice trend',
			'value': f'{voice_last_7} in last 7 days',
			'direction': voice_direction,
			'note': voice_note,
			'confidence': min(95, 45 + (voice_recent.count() * 8)),
		},
		{
			'title': 'Watch-level alerts',
			'value': f'{watch_alerts_active} active',
			'direction': 'up' if watch_alerts_active > 0 else 'steady',
			'note': watch_note,
			'confidence': min(95, 40 + (watch_alerts_recent * 10)),
		},
		{
			'title': 'Top shared signals',
			'value': signal_summary,
			'direction': 'steady',
			'note': 'Signal summaries are assistive and non-diagnostic.',
			'confidence': min(95, 30 + (sum(signal_counter.values()) * 7)),
		},
	]

	watch_highlights = []
	for name, count in top_signals:
		if count >= 2:
			watch_highlights.append(
				{
					'title': f'Repeated signal: {name}',
					'level': 'watch',
					'detail': f'Appeared {count} times in recent voice updates. Consider closer observation and care-team check-ins.',
				}
			)

	if watch_alerts_active:
		watch_highlights.append(
			{
				'title': 'Active watch alerts',
				'level': 'watch',
				'detail': f'{watch_alerts_active} watch-level alerts are active. Keep daily routines and updates consistent.',
			}
		)

	if not watch_highlights:
		watch_highlights.append(
			{
				'title': 'No watch anomalies detected',
				'level': 'stable',
				'detail': 'Recent patterns look stable. Continue logging routine updates to keep insight confidence strong.',
			}
		)

	characteristic_trends = build_characteristic_trends(circle, days=14)
	for characteristic in characteristic_trends:
		if characteristic['key'] == 'hydration_mentions' and characteristic['direction'] == 'down' and characteristic['baseline_average'] >= 1.0:
			watch_highlights.insert(
				0,
				{
					'title': 'Hydration mentions trending down',
					'level': 'watch',
					'detail': 'Hydration references dropped versus the prior baseline. Consider adding direct hydration check-ins.',
				},
			)
		if characteristic['key'] in {'fatigue_mentions', 'sleep_disruption_mentions', 'low_mood_mentions'} and characteristic['direction'] == 'up' and characteristic['current_average'] >= 1.5:
			watch_highlights.insert(
				0,
				{
					'title': f"{characteristic['label']} elevated",
					'level': 'watch',
					'detail': 'Recent mentions are higher than baseline. Keep observation consistent and coordinate updates across members.',
				},
			)

	return {
		'trend_cards': trend_cards,
		'characteristic_trends': characteristic_trends,
		'watch_highlights': watch_highlights[:4],
		'confidence': {
			'score': confidence_score,
			'label': confidence_label,
			'reason': f'Based on {evidence_points} recent data points across voice, feed, and alerts.',
		},
		'updated_at': now.isoformat(),
	}

@ensure_csrf_cookie
def landing_page(request):
	return render(request, 'core/landing.html', {'login_error': ''})


@ensure_csrf_cookie
def landing_login(request):
	if request.method != 'POST':
		return render(request, 'core/landing.html', {'login_error': ''})

	identifier = (request.POST.get('identifier') or '').strip()
	password = request.POST.get('password') or ''

	if not identifier or not password:
		return render(request, 'core/landing.html', {'login_error': 'Please enter your email/username and password.'})

	username_to_auth = identifier
	if '@' in identifier:
		user_match = User.objects.filter(email__iexact=identifier).first()
		if user_match is not None:
			username_to_auth = user_match.username

	user = authenticate(request, username=username_to_auth, password=password)
	if user is None:
		return render(request, 'core/landing.html', {'login_error': 'Invalid credentials. Please try again.'})

	auth_login(request, user)
	return render_dashboard_page(request, 'dashboard')


@ensure_csrf_cookie
def render_dashboard_page(request, initial_page='dashboard'):
	return render(
		request,
		'core/dashboard.html',
		{
			'user_role': get_demo_user_role_label(request),
			'initial_page': initial_page,
		},
	)


def dashboard_demo(request):
	return render_dashboard_page(request, 'dashboard')


def tasks_page(request):
	return render_dashboard_page(request, 'tasks')


def logs_page(request):
	return render_dashboard_page(request, 'voice')


@ensure_csrf_cookie
def alerts_page(request):
	return render(
		request,
		'core/alerts.html',
		{'user_role': get_demo_user_role_label(request)},
	)


class DashboardAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, role = get_dashboard_circle_and_role(request)

		if circle is None:
			return Response(
				{
					'viewer_name': 'Caregiver',
					'user_role': role,
					'circle': None,
					'stats': {
						'active_tasks': {'count': 0, 'hint': 'Task board arrives in Phase B'},
						'new_logs': {'count': 0, 'hint': 'Voice logs arrive in Phase E'},
						'alerts': {'count': 0, 'hint': 'No alerts yet'},
					},
					'recent_activity': [],
				}
			)

		memberships = list(
			CircleMembership.objects.filter(circle=circle)
			.select_related('user')
			.order_by('joined_at')
		)
		cleanup_expired_task_claims(circle)
		advance_voice_log_pipeline(circle)
		active_tasks_count = Task.objects.filter(circle=circle, status__in=[Task.Status.OPEN, Task.Status.CLAIMED]).count()
		claimed_tasks_count = Task.objects.filter(circle=circle, status=Task.Status.CLAIMED).count()
		active_alerts = Alert.objects.filter(circle=circle, status=Alert.Status.ACTIVE).count()
		week_ago = timezone.now() - timedelta(days=7)
		new_logs_count = VoiceLog.objects.filter(circle=circle, created_at__gte=week_ago).count()
		pending_logs_count = VoiceLog.objects.filter(circle=circle, status__in=[VoiceLog.Status.QUEUED, VoiceLog.Status.PROCESSING]).count()
		failed_logs_count = VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.FAILED).count()

		member_names = [membership.user.get_full_name() or membership.user.username for membership in memberships]
		member_pips = []
		for name in member_names[:3]:
			member_pips.append({'label': get_initials(name), 'color': None})
		if len(member_names) > 3:
			member_pips.append({'label': f'+{len(member_names) - 3}', 'color': None})

		viewer_name = 'Caregiver'
		if request.user.is_authenticated:
			viewer_name = request.user.first_name or request.user.get_full_name() or request.user.username

		return Response(
			{
				'viewer_name': viewer_name,
				'viewer_id': request.user.id if request.user.is_authenticated else None,
				'user_role': role,
				'circle': {
					'id': circle.id,
					'name': circle.name,
					'care_recipient': circle.care_recipient,
					'member_count': len(memberships),
					'member_pips': member_pips,
				},
				'stats': {
					'active_tasks': {
						'count': active_tasks_count,
						'hint': f'{claimed_tasks_count} currently claimed' if claimed_tasks_count else 'ready for caregivers to claim',
					},
					'new_logs': {
						'count': new_logs_count,
						'hint': (
							f'{pending_logs_count} processing'
							if pending_logs_count
							else f'{failed_logs_count} failed · retry available'
							if failed_logs_count
							else 'latest transcriptions ready'
							if new_logs_count
							else 'No logs yet'
						),
					},
					'alerts': {
						'count': active_alerts,
						'hint': 'active health alerts' if active_alerts else 'no active alerts',
					},
				},
				'recent_activity': build_recent_activity(circle),
			}
		)


class InsightsAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, membership_role, _actor = get_member_circle_context(request)
		insights = build_insights_payload(circle)
		return Response(
			{
				**insights,
				'user_role': 'admin' if membership_role == CircleMembership.Role.OWNER else 'member',
			}
		)


class HealthAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		return Response(
			{
				'status': 'ok',
				'service': 'carecircle',
				'debug': settings.DEBUG,
				'timestamp': timezone.now().isoformat(),
			}
		)


class LiveSyncAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, _membership_role, _actor = get_member_circle_context(request)

		task_max_updated = Task.objects.filter(circle=circle).aggregate(max_updated=Max('updated_at'))['max_updated']
		feed_max_updated = FeedEntry.objects.filter(circle=circle).aggregate(max_updated=Max('updated_at'))['max_updated']
		voice_max_updated = VoiceLog.objects.filter(circle=circle).aggregate(max_updated=Max('updated_at'))['max_updated']
		alert_max_updated = Alert.objects.filter(circle=circle).aggregate(max_updated=Max('updated_at'))['max_updated']

		notification_max_created = Notification.objects.filter(circle=circle).aggregate(max_created=Max('created_at'))['max_created']
		membership_max_joined = CircleMembership.objects.filter(circle=circle).aggregate(max_joined=Max('joined_at'))['max_joined']

		latest_activity_candidates = [
			value
			for value in [
				task_max_updated,
				alert_max_updated,
				notification_max_created,
				membership_max_joined,
				voice_max_updated,
			]
			if value is not None
		]
		latest_activity = max(latest_activity_candidates).isoformat() if latest_activity_candidates else None

		return Response(
			{
				'tasks': {
					'updated_at': task_max_updated.isoformat() if task_max_updated else None,
					'count': Task.objects.filter(circle=circle).count(),
				},
				'feed': {
					'updated_at': feed_max_updated.isoformat() if feed_max_updated else None,
					'count': FeedEntry.objects.filter(circle=circle).count(),
				},
				'voice': {
					'updated_at': voice_max_updated.isoformat() if voice_max_updated else None,
					'queued': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.QUEUED).count(),
					'processing': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.PROCESSING).count(),
					'failed': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.FAILED).count(),
				},
				'alerts': {
					'updated_at': alert_max_updated.isoformat() if alert_max_updated else None,
					'active_count': Alert.objects.filter(circle=circle, status=Alert.Status.ACTIVE).count(),
				},
				'activity': {
					'updated_at': latest_activity,
				},
			}
		)


class VoiceLogListCreateAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, membership_role, _actor = get_member_circle_context(request)
		advance_voice_log_pipeline(circle)

		logs = (
			VoiceLog.objects.filter(circle=circle)
			.select_related('created_by')
			.order_by('-created_at')[:25]
		)
		serializer = VoiceLogSerializer(logs, many=True)
		pipeline = {
			'queued': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.QUEUED).count(),
			'processing': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.PROCESSING).count(),
			'completed': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.COMPLETED).count(),
			'failed': VoiceLog.objects.filter(circle=circle, status=VoiceLog.Status.FAILED).count(),
		}
		return Response(
			{
				'logs': serializer.data,
				'pipeline': pipeline,
				'user_role': 'admin' if membership_role == CircleMembership.Role.OWNER else 'member',
				'can_upload': True,
			}
		)

	def post(self, request):
		circle, _membership_role, actor = get_member_circle_context(request)
		serializer = VoiceLogCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		voice_log = serializer.save(
			circle=circle,
			created_by=actor,
			status=VoiceLog.Status.QUEUED,
		)
		# Process synchronously — audio-file logs transcribe immediately;
		# text-only logs extract signals and complete without delay.
		if voice_log.audio_file or voice_log.transcript:
			process_voice_log(voice_log)
		return Response(VoiceLogSerializer(voice_log).data, status=status.HTTP_201_CREATED)


class VoiceLogRetryAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request, log_id):
		circle, _membership_role, _actor = get_member_circle_context(request)
		voice_log = generics.get_object_or_404(VoiceLog, id=log_id, circle=circle)

		if voice_log.status != VoiceLog.Status.FAILED:
			return Response({'detail': 'Only failed logs can be retried.'}, status=status.HTTP_400_BAD_REQUEST)

		voice_log.status = VoiceLog.Status.QUEUED
		voice_log.retry_count += 1
		voice_log.error_message = ''
		voice_log.failed_at = None
		voice_log.save(update_fields=['status', 'retry_count', 'error_message', 'failed_at', 'updated_at'])
		# Re-process immediately so retry returns a final state
		process_voice_log(voice_log)
		return Response(VoiceLogSerializer(voice_log).data)


class FeedEntryListCreateAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, membership_role, _actor = get_member_circle_context(request)
		entries = (
			FeedEntry.objects.filter(circle=circle)
			.select_related('created_by')
			.order_by('-created_at')[:50]
		)
		serializer = FeedEntrySerializer(entries, many=True)
		return Response(
			{
				'entries': serializer.data,
				'user_role': 'admin' if membership_role == CircleMembership.Role.OWNER else 'member',
				'can_post': True,
			}
		)

	def post(self, request):
		circle, _membership_role, actor = get_member_circle_context(request)
		serializer = FeedEntryCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		entry = serializer.save(
			circle=circle,
			created_by=actor,
			entry_type=FeedEntry.EntryType.HUMAN,
			source=FeedEntry.Source.MEMBER,
		)
		return Response(FeedEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class TaskListCreateAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, membership_role, actor = get_request_circle_membership(request)
		if circle is None:
			return Response({'tasks': [], 'user_role': 'admin', 'can_manage': True})

		cleanup_expired_task_claims(circle)
		tasks = Task.objects.filter(circle=circle).select_related('claimed_by', 'verified_by', 'created_by', 'assigned_to')
		serializer = TaskSerializer(tasks, many=True)
		user_role = 'admin' if membership_role == CircleMembership.Role.OWNER else 'member'
		can_manage = membership_role == CircleMembership.Role.OWNER
		data = []
		for item, task in zip(serializer.data, tasks):
			can_claim_assigned = actor is not None and task.assigned_to_id == actor.id
			item['can_claim'] = task.status == Task.Status.OPEN and (can_manage or can_claim_assigned)
			item['can_release'] = task.status == Task.Status.CLAIMED and (
				can_manage or (actor is not None and task.claimed_by_id == actor.id)
			)
			item['can_verify'] = task.status == Task.Status.CLAIMED
			item['can_edit'] = can_manage
			item['can_delete'] = can_manage
			data.append(item)
		return Response({'tasks': data, 'user_role': user_role, 'can_manage': can_manage})

	def post(self, request):
		circle, membership_role, actor = get_request_circle_membership(request)
		if circle is None:
			raise PermissionDenied('No circle available.')
		if membership_role != CircleMembership.Role.OWNER:
			raise PermissionDenied('Only admins can create tasks.')

		# Availability gate: if due_at is provided, require availability at due time.
		# If due_at is blank, allow members with current or upcoming windows.
		from django.utils.dateparse import parse_datetime as _parse_dt
		at_time = None
		due_at_raw = request.data.get('due_at')
		if due_at_raw:
			parsed_due = _parse_dt(str(due_at_raw))
			if parsed_due:
				at_time = parsed_due

		if at_time is not None:
			available_qs = get_available_members_now(circle, at_time)
			no_avail_detail = (
				'No members are available at the selected due time. '
				'Please adjust member availability or choose another due time.'
			)
		else:
			available_qs = get_available_members_current_or_upcoming(circle)
			no_avail_detail = (
				'No members have any current or upcoming availability. '
				'Please set member availability before creating a task.'
			)

		if not available_qs.exists():
			return Response(
				{'detail': no_avail_detail},
				status=status.HTTP_400_BAD_REQUEST,
			)

		serializer = TaskCreateUpdateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		# Validate assigned_to is required and belongs to this circle.
		assigned_to = serializer.validated_data.get('assigned_to')
		if assigned_to is None:
			return Response(
				{'detail': 'You must assign this task to an available member.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		if not CircleMembership.objects.filter(
			circle=circle,
			user=assigned_to,
			role=CircleMembership.Role.MEMBER,
		).exists():
			return Response(
				{'detail': 'The assigned member does not belong to this circle.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		if not available_qs.filter(user=assigned_to).exists():
			assigned_detail = (
				'The selected member is not available at the selected due time.'
				if at_time is not None
				else 'The selected member has no current or upcoming availability window.'
			)
			return Response(
				{'detail': assigned_detail},
				status=status.HTTP_400_BAD_REQUEST,
			)

		task = serializer.save(circle=circle, created_by=actor)
		return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def patch(self, request, task_id):
		circle, membership_role, _actor = get_request_circle_membership(request)
		task = generics.get_object_or_404(Task, id=task_id, circle=circle)
		if membership_role != CircleMembership.Role.OWNER:
			raise PermissionDenied('Only admins can edit tasks.')

		serializer = TaskCreateUpdateSerializer(task, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(TaskSerializer(task).data)

	def delete(self, request, task_id):
		circle, membership_role, _actor = get_request_circle_membership(request)
		task = generics.get_object_or_404(Task, id=task_id, circle=circle)
		if membership_role != CircleMembership.Role.OWNER:
			raise PermissionDenied('Only admins can delete tasks.')
		task.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)


class TaskActionAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request, task_id, action):
		circle, membership_role, actor = get_request_circle_membership(request)
		cleanup_expired_task_claims(circle)
		task = generics.get_object_or_404(Task, id=task_id, circle=circle)
		now = timezone.now()

		if action == 'claim':
			if task.status != Task.Status.OPEN:
				return Response({'detail': 'Only open tasks can be claimed.'}, status=status.HTTP_400_BAD_REQUEST)
			if (
				membership_role != CircleMembership.Role.OWNER
				and task.assigned_to_id is not None
				and (actor is None or task.assigned_to_id != actor.id)
			):
				raise PermissionDenied('Only the assigned member or an admin can claim this task.')
			task.status = Task.Status.CLAIMED
			task.claimed_by = actor
			task.claimed_at = now
			task.claimed_expires_at = now + timedelta(hours=4)
			task.verified_by = None
			task.verified_at = None
		elif action == 'release':
			is_claim_owner = actor is not None and task.claimed_by_id == actor.id
			if task.status != Task.Status.CLAIMED or not (is_claim_owner or membership_role == CircleMembership.Role.OWNER):
				raise PermissionDenied('Only the claimer or an admin can release this task.')
			task.status = Task.Status.OPEN
			task.claimed_by = None
			task.claimed_at = None
			task.claimed_expires_at = None
			task.verified_by = None
			task.verified_at = None
		elif action == 'verify':
			if task.status != Task.Status.CLAIMED:
				return Response({'detail': 'Only claimed tasks can be verified.'}, status=status.HTTP_400_BAD_REQUEST)
			task.status = Task.Status.VERIFIED
			task.verified_by = actor
			task.verified_at = now
		else:
			return Response({'detail': 'Unsupported action.'}, status=status.HTTP_400_BAD_REQUEST)

		task.save()
		return Response(TaskSerializer(task).data)


class AlertListAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, membership_role, _actor = get_request_circle_membership(request)
		if circle is None:
			return Response([])

		alerts = Alert.objects.filter(circle=circle).order_by('-updated_at', '-created_at')
		serializer = AlertSerializer(alerts, many=True)
		data = serializer.data
		can_dismiss = membership_role == CircleMembership.Role.OWNER
		for item in data:
			item['can_edit'] = True
			item['can_address'] = True
			item['can_dismiss'] = can_dismiss
		return Response(data)


class AlertDetailAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def patch(self, request, alert_id):
		circle, membership_role, actor = get_request_circle_membership(request)
		alert = generics.get_object_or_404(Alert, id=alert_id, circle=circle)

		serializer = AlertUpdateSerializer(alert, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		validated = serializer.validated_data

		if 'status' in validated and validated['status'] == Alert.Status.DISMISSED and membership_role != CircleMembership.Role.OWNER:
			raise PermissionDenied('Only admins can dismiss alerts.')

		for field, value in validated.items():
			setattr(alert, field, value)

		if validated.get('status') == Alert.Status.ADDRESSED:
			alert.addressed_by = actor
			alert.addressed_at = timezone.now()
			alert.dismissed_by = None
			alert.dismissed_at = None
		elif validated.get('status') == Alert.Status.DISMISSED:
			alert.dismissed_by = actor
			alert.dismissed_at = timezone.now()
		elif 'status' in validated and validated['status'] == Alert.Status.ACTIVE:
			alert.addressed_by = None
			alert.addressed_at = None
			alert.dismissed_by = None
			alert.dismissed_at = None

		alert.save()
		return Response(AlertSerializer(alert).data)


class CircleListCreateAPIView(generics.ListCreateAPIView):
	permission_classes = [permissions.IsAuthenticated]

	def get_queryset(self):
		memberships = CircleMembership.objects.filter(user=self.request.user).select_related('circle')
		circles = [membership.circle for membership in memberships]
		for membership, circle in zip(memberships, circles):
			circle.my_role = membership.role
		return circles

	def get_serializer_class(self):
		if self.request.method == 'POST':
			return CircleCreateSerializer
		return CircleListSerializer

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return Response(serializer.data)

	def perform_create(self, serializer):
		if CircleMembership.objects.filter(user=self.request.user).exists():
			from rest_framework.exceptions import ValidationError
			raise ValidationError(
				'You already belong to a circle. Each user can only be a member of one circle.'
			)
		circle = serializer.save(created_by=self.request.user)
		CircleMembership.objects.create(
			circle=circle,
			user=self.request.user,
			role=CircleMembership.Role.OWNER,
		)


class CircleDetailAPIView(generics.RetrieveAPIView):
	serializer_class = CircleDetailSerializer
	permission_classes = [permissions.IsAuthenticated, IsCircleMember]
	lookup_url_kwarg = 'circle_id'

	def get_queryset(self):
		return Circle.objects.all()

	def get_object(self):
		circle = super().get_object()
		membership = CircleMembership.objects.get(circle=circle, user=self.request.user)
		circle.my_role = membership.role
		return circle


class CircleMemberListAPIView(generics.ListAPIView):
	serializer_class = CircleMemberSerializer
	permission_classes = [permissions.IsAuthenticated, IsCircleMember]

	def get_queryset(self):
		circle_id = self.kwargs['circle_id']
		membership = generics.get_object_or_404(
			CircleMembership,
			circle_id=circle_id,
			user=self.request.user,
		)
		queryset = (
			CircleMembership.objects.filter(circle_id=circle_id)
			.select_related('user')
			.prefetch_related('availabilities')
		)
		if membership.role == CircleMembership.Role.OWNER:
			return queryset
		return queryset.filter(user=self.request.user)


class CircleMemberInviteAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated, IsCircleOwner]

	def post(self, request, circle_id):
		serializer = CircleInviteSerializer(data=request.data, context={})
		serializer.is_valid(raise_exception=True)

		circle = Circle.objects.get(pk=circle_id)
		invite_user = serializer.context['invite_user']
		role = serializer.validated_data['role']

		membership, created = CircleMembership.objects.get_or_create(
			circle=circle,
			user=invite_user,
			defaults={'role': role},
		)

		if not created:
			return Response(
				{'detail': 'User is already a member of this circle.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		return Response(CircleMemberSerializer(membership).data, status=status.HTTP_201_CREATED)


class MemberAvailabilityAPIView(APIView):
	"""GET/POST availability windows for a specific circle member.

	Owners can manage any member.
	Members can only manage their own windows.
	"""
	permission_classes = [permissions.IsAuthenticated, IsCircleMember]

	def _assert_can_manage(self, request, circle_id, user_id):
		request_membership = generics.get_object_or_404(
			CircleMembership,
			circle_id=circle_id,
			user=request.user,
		)
		if request_membership.role == CircleMembership.Role.OWNER:
			return
		if request.user.id != user_id:
			raise PermissionDenied('You can only manage your own availability windows.')

	def get(self, request, circle_id, user_id):
		self._assert_can_manage(request, circle_id, user_id)
		membership = generics.get_object_or_404(
			CircleMembership, circle_id=circle_id, user_id=user_id
		)
		serializer = MemberAvailabilitySerializer(membership.availabilities.all(), many=True)
		return Response(serializer.data)

	def post(self, request, circle_id, user_id):
		self._assert_can_manage(request, circle_id, user_id)
		membership = generics.get_object_or_404(
			CircleMembership, circle_id=circle_id, user_id=user_id
		)
		serializer = MemberAvailabilitySerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		availability = serializer.save(membership=membership)
		return Response(MemberAvailabilitySerializer(availability).data, status=status.HTTP_201_CREATED)


class MemberAvailabilityDeleteAPIView(APIView):
	"""DELETE a specific availability window.

	Owners can delete any member's windows.
	Members can only delete their own windows.
	"""
	permission_classes = [permissions.IsAuthenticated, IsCircleMember]

	def _assert_can_manage(self, request, circle_id, user_id):
		request_membership = generics.get_object_or_404(
			CircleMembership,
			circle_id=circle_id,
			user=request.user,
		)
		if request_membership.role == CircleMembership.Role.OWNER:
			return
		if request.user.id != user_id:
			raise PermissionDenied('You can only manage your own availability windows.')

	def delete(self, request, circle_id, user_id, avail_id):
		self._assert_can_manage(request, circle_id, user_id)
		membership = generics.get_object_or_404(
			CircleMembership, circle_id=circle_id, user_id=user_id
		)
		avail = generics.get_object_or_404(
			MemberAvailability, id=avail_id, membership=membership
		)
		avail.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)


class AvailableMembersAPIView(APIView):
	"""Returns circle members who are available at a given time (default: now)."""
	permission_classes = [permissions.IsAuthenticated, IsCircleOwner]

	def get(self, request, circle_id):
		circle = generics.get_object_or_404(Circle, pk=circle_id)
		from django.utils.dateparse import parse_datetime as _parse_dt
		at_time = None
		at_str = request.query_params.get('at')
		if at_str:
			parsed = _parse_dt(at_str)
			if parsed:
				at_time = parsed
		if at_time is None:
			memberships = get_available_members_current_or_upcoming(circle)
		else:
			memberships = get_available_members_now(circle, at_time)
		return Response(CircleMemberSerializer(memberships, many=True).data)


class CircleMemberDeleteAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated, IsCircleOwner]

	def delete(self, request, circle_id, user_id):
		membership = generics.get_object_or_404(
			CircleMembership,
			circle_id=circle_id,
			user_id=user_id,
		)

		if membership.role == CircleMembership.Role.OWNER:
			raise PermissionDenied('Owner membership cannot be removed.')

		if membership.user_id == request.user.id:
			raise PermissionDenied('Owner cannot remove their own membership.')

		membership.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)


class CircleNotificationSendAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated, IsCircleOwner]

	def post(self, request, circle_id):
		serializer = NotificationSendSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		circle = generics.get_object_or_404(Circle, pk=circle_id)
		recipient_ids = serializer.validated_data['recipient_ids']
		title = serializer.validated_data['title']
		message = serializer.validated_data['message']

		valid_recipient_ids = CircleMembership.objects.filter(
			circle=circle,
			user_id__in=recipient_ids,
		).values_list('user_id', flat=True)

		if not valid_recipient_ids:
			return Response(
				{'detail': 'No valid recipients in this circle.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		notifications = [
			Notification(
				circle=circle,
				sent_by=request.user,
				recipient_id=recipient_id,
				title=title,
				message=message,
			)
			for recipient_id in valid_recipient_ids
		]
		Notification.objects.bulk_create(notifications)

		return Response({'count': len(notifications)}, status=status.HTTP_201_CREATED)


@ensure_csrf_cookie
def members_management_page(request, circle_id):
	can_manage_members = False
	if request.user.is_authenticated:
		membership = CircleMembership.objects.filter(circle_id=circle_id, user=request.user).first()
		if membership is not None:
			can_manage_members = membership.role == CircleMembership.Role.OWNER
	return render(
		request,
		'core/members_management.html',
		{
			'circle_id': circle_id,
			'can_manage_members': can_manage_members,
		},
	)

def profile_page(request):
	return render(request, 'core/profile.html', {'user_role': get_demo_user_role_label(request)})


def notifications_page(request):
	return render(request, 'core/notifications.html', {'user_role': get_demo_user_role_label(request)})


class UserProfileAPIView(generics.RetrieveUpdateAPIView):
	permission_classes = [permissions.IsAuthenticated]
	serializer_class = UserProfileSerializer

	def get_object(self):
		return self.request.user


class UserNotificationsAPIView(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request):
		circle, _membership_role, actor = get_request_circle_membership(request)
		if request.user.is_authenticated:
			recipient = request.user
		else:
			recipient = actor

		if recipient is None:
			return Response([])

		queryset = Notification.objects.filter(recipient=recipient)
		if circle is not None:
			queryset = queryset.filter(circle=circle)
		notifications = queryset.order_by('-created_at')
		serializer = NotificationListSerializer(notifications, many=True)
		return Response(serializer.data)


class NotificationMarkReadAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request, notification_id):
		notification = generics.get_object_or_404(
			Notification,
			id=notification_id,
			recipient=request.user,
		)
		notification.read_at = timezone.now()
		notification.save()
		from .serializers import NotificationListSerializer
		return Response(NotificationListSerializer(notification).data, status=status.HTTP_200_OK)