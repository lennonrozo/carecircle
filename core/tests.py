from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from datetime import timedelta

from .models import Alert, Circle, CircleMembership, FeedEntry, MemberAvailability, Notification, Task, VoiceLog


User = get_user_model()


class CircleRBACAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.owner = User.objects.create_user(
			username='owner',
			email='owner@example.com',
			password='ownerpass123',
		)
		self.member = User.objects.create_user(
			username='member',
			email='member@example.com',
			password='memberpass123',
		)
		self.outsider = User.objects.create_user(
			username='outsider',
			email='outsider@example.com',
			password='outsiderpass123',
		)
		self.invitee = User.objects.create_user(
			username='invitee',
			email='invitee@example.com',
			password='inviteepass123',
		)

		self.circle = Circle.objects.create(
			name='Margaret Circle',
			care_recipient='Margaret Johnson',
			created_by=self.owner,
		)
		CircleMembership.objects.create(
			user=self.owner,
			circle=self.circle,
			role=CircleMembership.Role.OWNER,
		)
		CircleMembership.objects.create(
			user=self.member,
			circle=self.circle,
			role=CircleMembership.Role.MEMBER,
		)

	def test_owner_can_list_all_members(self):
		self.client.force_authenticate(user=self.owner)

		response = self.client.get(f'/api/circles/{self.circle.id}/members/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 2)

	def test_member_cannot_list_all_members(self):
		self.client.force_authenticate(user=self.member)

		response = self.client.get(f'/api/circles/{self.circle.id}/members/')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_owner_can_invite_member(self):
		self.client.force_authenticate(user=self.owner)

		response = self.client.post(
			f'/api/circles/{self.circle.id}/members/invite/',
			{'email': self.invitee.email, 'role': CircleMembership.Role.MEMBER},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertTrue(
			CircleMembership.objects.filter(circle=self.circle, user=self.invitee).exists()
		)

	def test_member_cannot_invite(self):
		self.client.force_authenticate(user=self.member)

		response = self.client.post(
			f'/api/circles/{self.circle.id}/members/invite/',
			{'email': self.invitee.email, 'role': CircleMembership.Role.MEMBER},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_owner_can_remove_member(self):
		self.client.force_authenticate(user=self.owner)

		response = self.client.delete(f'/api/circles/{self.circle.id}/members/{self.member.id}/')

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(
			CircleMembership.objects.filter(circle=self.circle, user=self.member).exists()
		)

	def test_owner_cannot_remove_owner_membership(self):
		self.client.force_authenticate(user=self.owner)

		response = self.client.delete(f'/api/circles/{self.circle.id}/members/{self.owner.id}/')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_member_can_access_circle_detail_without_member_roster(self):
		self.client.force_authenticate(user=self.member)

		response = self.client.get(f'/api/circles/{self.circle.id}/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['my_role'], CircleMembership.Role.MEMBER)

	def test_outsider_cannot_access_circle_detail(self):
		self.client.force_authenticate(user=self.outsider)

		response = self.client.get(f'/api/circles/{self.circle.id}/')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_notifications_api_accessible_for_demo_anonymous(self):
		Notification.objects.create(
			circle=self.circle,
			sent_by=self.owner,
			recipient=self.owner,
			title='Circle update',
			message='Medication reminder posted.',
		)

		response = self.client.get('/api/notifications/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]['title'], 'Circle update')

	def test_landing_login_success_redirects_to_dashboard_view(self):
		response = self.client.post(
			'/login/',
			{'identifier': self.owner.email, 'password': 'ownerpass123'},
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertContains(response, 'Task Board')

	def test_landing_login_invalid_credentials_shows_error(self):
		response = self.client.post(
			'/login/',
			{'identifier': self.owner.email, 'password': 'wrong-password'},
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertContains(response, 'Invalid credentials. Please try again.')

	def test_owner_dashboard_shows_circle_card(self):
		self.client.force_login(self.owner)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertContains(response, 'id="admin-circle-panel"', html=False)
		self.assertContains(response, 'View Circle →')

	def test_member_dashboard_hides_circle_card(self):
		self.client.force_login(self.member)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertNotContains(response, 'id="admin-circle-panel"', html=False)
		self.assertNotContains(response, '<button class="btn-enter" id="view-circle-button"', html=False)

	def test_full_login_flow_owner_then_member(self):
		owner_logged_in = self.client.login(username=self.owner.username, password='ownerpass123')
		self.assertTrue(owner_logged_in)

		member_membership = CircleMembership.objects.get(circle=self.circle, user=self.member)
		now = timezone.now()
		MemberAvailability.objects.create(
			membership=member_membership,
			available_from=now - timedelta(hours=1),
			available_until=now + timedelta(hours=3),
			notes='Test coverage window',
		)

		owner_dashboard_response = self.client.get('/dashboard/')
		self.assertEqual(owner_dashboard_response.status_code, status.HTTP_200_OK)

		owner_members_response = self.client.get(f'/api/circles/{self.circle.id}/members/')
		self.assertEqual(owner_members_response.status_code, status.HTTP_200_OK)

		owner_task_create_response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Owner created task',
				'description': 'Owner can create tasks',
				'task_type': 'logistics',
				'urgency': 'medium',
				'due_at': (now + timedelta(hours=1)).isoformat(),
				'assigned_to': self.member.id,
			},
			format='json',
		)
		self.assertEqual(owner_task_create_response.status_code, status.HTTP_201_CREATED)

		self.client.logout()

		member_logged_in = self.client.login(username=self.member.username, password='memberpass123')
		self.assertTrue(member_logged_in)

		member_dashboard_response = self.client.get('/dashboard/')
		self.assertEqual(member_dashboard_response.status_code, status.HTTP_200_OK)

		member_tasks_list_response = self.client.get('/api/tasks/')
		self.assertEqual(member_tasks_list_response.status_code, status.HTTP_200_OK)

		member_task_create_response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Member should fail create',
				'description': 'Members cannot create tasks',
				'task_type': 'logistics',
				'urgency': 'low',
				'due_at': None,
			},
			format='json',
		)
		self.assertEqual(member_task_create_response.status_code, status.HTTP_403_FORBIDDEN)

		member_members_response = self.client.get(f'/api/circles/{self.circle.id}/members/')
		self.assertEqual(member_members_response.status_code, status.HTTP_403_FORBIDDEN)

		member_feed_post_response = self.client.post(
			'/api/feed/',
			{'title': '', 'content': 'Member flow update', 'tags': []},
			format='json',
		)
		self.assertEqual(member_feed_post_response.status_code, status.HTTP_201_CREATED)

		member_voice_post_response = self.client.post(
			'/api/voice-logs/',
			{'audio_label': 'Member flow voice', 'transcript': 'Hydration looks stable today.'},
			format='json',
		)
		self.assertEqual(member_voice_post_response.status_code, status.HTTP_201_CREATED)

		self.client.logout()


class AdminTaskVoiceFlowTests(TestCase):
	"""Temporary integration tests to catch admin flow regressions across task and voice features."""

	def setUp(self):
		self.client = APIClient()
		self.owner = User.objects.create_user(
			username='adminflow-owner',
			email='adminflow-owner@example.com',
			password='ownerpass123',
		)
		self.member = User.objects.create_user(
			username='adminflow-member',
			email='adminflow-member@example.com',
			password='memberpass123',
		)
		self.other_member = User.objects.create_user(
			username='adminflow-other',
			email='adminflow-other@example.com',
			password='memberpass123',
		)

		self.circle = Circle.objects.create(
			name='Admin Flow Circle',
			care_recipient='Flow Recipient',
			created_by=self.owner,
		)
		self.owner_membership = CircleMembership.objects.create(
			user=self.owner,
			circle=self.circle,
			role=CircleMembership.Role.OWNER,
		)
		self.member_membership = CircleMembership.objects.create(
			user=self.member,
			circle=self.circle,
			role=CircleMembership.Role.MEMBER,
		)
		self.other_member_membership = CircleMembership.objects.create(
			user=self.other_member,
			circle=self.circle,
			role=CircleMembership.Role.MEMBER,
		)

	def _add_window(self, membership, start, end, notes=''):
		return MemberAvailability.objects.create(
			membership=membership,
			available_from=start,
			available_until=end,
			notes=notes,
		)

	def test_admin_login_full_flow_create_task_voice_claim_verify(self):
		self.assertTrue(self.client.login(username=self.owner.username, password='ownerpass123'))

		now = timezone.now()
		due_at = now + timedelta(hours=2)
		self._add_window(
			self.member_membership,
			start=now - timedelta(minutes=30),
			end=now + timedelta(hours=4),
			notes='Primary assignee',
		)

		task_response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Coordinate medication pickup',
				'description': 'Pharmacy closes early',
				'task_type': 'medical',
				'urgency': 'high',
				'due_at': due_at.isoformat(),
				'assigned_to': self.member.id,
			},
			format='json',
		)
		self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
		task_id = task_response.data['id']
		self.assertEqual(task_response.data['assigned_to_id'], self.member.id)

		voice_response = self.client.post(
			'/api/voice-logs/',
			{
				'audio_label': 'Evening summary',
				'transcript': 'Hydration is good and appetite improved today.',
			},
			format='json',
		)
		self.assertEqual(voice_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(voice_response.data['status'], VoiceLog.Status.COMPLETED)
		self.assertTrue(isinstance(voice_response.data['extracted_signals'], list))

		self.client.logout()
		self.assertTrue(self.client.login(username=self.member.username, password='memberpass123'))

		claim_response = self.client.post(f'/api/tasks/{task_id}/claim/', {}, format='json')
		self.assertEqual(claim_response.status_code, status.HTTP_200_OK)
		self.assertEqual(claim_response.data['status'], Task.Status.CLAIMED)
		self.assertEqual(claim_response.data['claimed_by_name'], self.member.username)

		self.client.logout()
		self.assertTrue(self.client.login(username=self.owner.username, password='ownerpass123'))
		verify_response = self.client.post(f'/api/tasks/{task_id}/verify/', {}, format='json')
		self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
		self.assertEqual(verify_response.data['status'], Task.Status.VERIFIED)

	def test_admin_cannot_create_task_without_any_available_member(self):
		self.assertTrue(self.client.login(username=self.owner.username, password='ownerpass123'))

		response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Should fail',
				'description': 'No one is available right now',
				'task_type': 'logistics',
				'urgency': 'medium',
				'assigned_to': self.member.id,
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('No members are currently available', response.data['detail'])

	def test_admin_can_create_task_for_past_due_when_past_availability_matches(self):
		self.assertTrue(self.client.login(username=self.owner.username, password='ownerpass123'))

		now = timezone.now()
		past_due = now - timedelta(days=1)
		self._add_window(
			self.member_membership,
			start=past_due - timedelta(hours=1),
			end=past_due + timedelta(hours=1),
			notes='Past retrospective window',
		)

		response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Backfill task',
				'description': 'Created for past due check',
				'task_type': 'logistics',
				'urgency': 'low',
				'due_at': past_due.isoformat(),
				'assigned_to': self.member.id,
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

	def test_non_assigned_member_cannot_claim_open_task(self):
		self.assertTrue(self.client.login(username=self.owner.username, password='ownerpass123'))
		now = timezone.now()
		self._add_window(
			self.member_membership,
			start=now - timedelta(minutes=10),
			end=now + timedelta(hours=2),
			notes='Assigned window',
		)
		task_response = self.client.post(
			'/api/tasks/',
			{
				'title': 'Assigned task',
				'description': 'Only assigned member should claim',
				'task_type': 'emotional',
				'urgency': 'medium',
				'assigned_to': self.member.id,
			},
			format='json',
		)
		self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
		task_id = task_response.data['id']
		self.client.logout()

		self.assertTrue(self.client.login(username=self.other_member.username, password='memberpass123'))
		claim_response = self.client.post(f'/api/tasks/{task_id}/claim/', {}, format='json')
		self.assertEqual(claim_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_health_endpoint_available_for_launch_checks(self):
		response = self.client.get('/api/health/')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['status'], 'ok')
		self.assertEqual(response.data['service'], 'carecircle')


class VoiceLogAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.owner = User.objects.create_user(
			username='owner2',
			email='owner2@example.com',
			password='ownerpass123',
		)
		self.member = User.objects.create_user(
			username='member2',
			email='member2@example.com',
			password='memberpass123',
		)

		self.circle = Circle.objects.create(
			name='Voice Circle',
			care_recipient='Margaret Johnson',
			created_by=self.owner,
		)
		CircleMembership.objects.create(
			user=self.owner,
			circle=self.circle,
			role=CircleMembership.Role.OWNER,
		)
		CircleMembership.objects.create(
			user=self.member,
			circle=self.circle,
			role=CircleMembership.Role.MEMBER,
		)

	def test_member_can_create_voice_log(self):
		self.client.force_authenticate(user=self.member)

		response = self.client.post(
			'/api/voice-logs/',
			{'audio_label': 'Morning note', 'transcript': 'She feels a little tired today.'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		# Text-only logs are processed synchronously; expect COMPLETED not QUEUED
		self.assertEqual(response.data['status'], VoiceLog.Status.COMPLETED)

	def test_failed_voice_log_can_be_retried(self):
		self.client.force_authenticate(user=self.member)
		voice_log = VoiceLog.objects.create(
			circle=self.circle,
			created_by=self.member,
			audio_label='Needs retry',
			transcript='This should fail once',
			status=VoiceLog.Status.FAILED,
			error_message='Transcription service timed out. Retry available.',
		)

		response = self.client.post(f'/api/voice-logs/{voice_log.id}/retry/', {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		voice_log.refresh_from_db()
		# Retry processes synchronously; text-only log completes immediately
		self.assertEqual(voice_log.status, VoiceLog.Status.COMPLETED)
		self.assertEqual(voice_log.retry_count, 1)

	def test_dashboard_uses_real_voice_log_stats(self):
		self.client.force_authenticate(user=self.owner)
		VoiceLog.objects.create(
			circle=self.circle,
			created_by=self.owner,
			audio_label='Completed note',
			transcript='Hydration and appetite improved today.',
			status=VoiceLog.Status.COMPLETED,
		)

		response = self.client.get('/api/dashboard/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['stats']['new_logs']['count'], 1)


class InsightsAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.owner = User.objects.create_user(
			username='owner3',
			email='owner3@example.com',
			password='ownerpass123',
		)
		self.member = User.objects.create_user(
			username='member3',
			email='member3@example.com',
			password='memberpass123',
		)

		self.circle = Circle.objects.create(
			name='Insights Circle',
			care_recipient='Margaret Johnson',
			created_by=self.owner,
		)
		CircleMembership.objects.create(
			user=self.owner,
			circle=self.circle,
			role=CircleMembership.Role.OWNER,
		)
		CircleMembership.objects.create(
			user=self.member,
			circle=self.circle,
			role=CircleMembership.Role.MEMBER,
		)

	def test_insights_returns_trends_and_confidence(self):
		self.client.force_authenticate(user=self.member)

		VoiceLog.objects.create(
			circle=self.circle,
			created_by=self.member,
			audio_label='Morning check-in',
			transcript='Hydration and appetite looked better today.',
			extracted_signals=['Hydration concern', 'Appetite pattern'],
			status=VoiceLog.Status.COMPLETED,
		)
		VoiceLog.objects.create(
			circle=self.circle,
			created_by=self.member,
			audio_label='Evening check-in',
			transcript='Hydration concern still present.',
			extracted_signals=['Hydration concern'],
			status=VoiceLog.Status.COMPLETED,
		)
		Alert.objects.create(
			circle=self.circle,
			created_by=self.owner,
			title='Hydration watch',
			message='Continue monitoring intake.',
			severity=Alert.Severity.WATCH,
			status=Alert.Status.ACTIVE,
		)
		FeedEntry.objects.create(
			circle=self.circle,
			created_by=self.member,
			content='Shared evening update with care team.',
		)

		response = self.client.get('/api/insights/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['trend_cards']), 3)
		self.assertEqual(len(response.data['characteristic_trends']), 4)
		self.assertEqual(len(response.data['characteristic_trends'][0]['history']), 14)
		self.assertGreaterEqual(response.data['confidence']['score'], 1)
		self.assertTrue(response.data['watch_highlights'])
		self.assertIn('assistive', response.data['trend_cards'][2]['note'].lower())

	def test_insights_empty_state_is_safe_and_non_diagnostic(self):
		self.client.force_authenticate(user=self.member)

		response = self.client.get('/api/insights/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['trend_cards']), 3)
		self.assertEqual(len(response.data['characteristic_trends']), 4)
		self.assertGreaterEqual(len(response.data['watch_highlights']), 1)
		self.assertIn('non-diagnostic', response.data['trend_cards'][2]['note'].lower())

	def test_async_trend_analyzer_creates_hydration_alert(self):
		now = timezone.now()
		for day_offset in range(7, 14):
			log = VoiceLog.objects.create(
				circle=self.circle,
				created_by=self.member,
				transcript='Hydration and water intake tracked today.',
				extracted_signals=['Hydration · Watch'],
				status=VoiceLog.Status.COMPLETED,
			)
			VoiceLog.objects.filter(id=log.id).update(created_at=now - timedelta(days=day_offset))

		for day_offset in range(0, 3):
			log = VoiceLog.objects.create(
				circle=self.circle,
				created_by=self.member,
				transcript='General update about routines only.',
				extracted_signals=[],
				status=VoiceLog.Status.COMPLETED,
			)
			VoiceLog.objects.filter(id=log.id).update(created_at=now - timedelta(days=day_offset))

		call_command('analyze_insight_trends', circle_id=self.circle.id, days=14)

		created_alert = Alert.objects.filter(circle=self.circle, title__icontains='Hydration trend').first()
		self.assertIsNotNone(created_alert)
		self.assertIn(created_alert.severity, [Alert.Severity.WATCH, Alert.Severity.URGENT])
		self.assertGreaterEqual(Notification.objects.filter(circle=self.circle, title__icontains='Insight alert').count(), 1)
