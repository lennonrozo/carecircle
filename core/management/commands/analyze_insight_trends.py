from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from core.insights import build_characteristic_trends, build_trend_alert_candidates
from core.models import Alert, Circle, CircleMembership, Notification


class Command(BaseCommand):
	help = 'Analyze insight trends asynchronously and create watch/urgent alerts for worsening patterns.'

	def add_arguments(self, parser):
		parser.add_argument('--circle-id', type=int, default=None, help='Analyze only a specific circle id.')
		parser.add_argument('--days', type=int, default=14, help='Number of trailing days to analyze (default: 14).')

	def handle(self, *args, **options):
		circle_id = options['circle_id']
		days = max(7, options['days'])

		circles = Circle.objects.all().order_by('id')
		if circle_id is not None:
			circles = circles.filter(id=circle_id)

		created_count = 0
		for circle in circles:
			trends = build_characteristic_trends(circle, days=days)
			candidates = build_trend_alert_candidates(trends)
			for candidate in candidates:
				created = self._create_alert_if_needed(circle, candidate)
				if created:
					created_count += 1

		self.stdout.write(self.style.SUCCESS(f'Insight trend analysis complete. Alerts created: {created_count}'))

	def _create_alert_if_needed(self, circle, candidate):
		now = timezone.now()
		recent_duplicate = Alert.objects.filter(
			circle=circle,
			title=candidate['title'],
			status=Alert.Status.ACTIVE,
			created_at__gte=now - timedelta(hours=24),
		).exists()
		if recent_duplicate:
			return False

		severity = Alert.Severity.WATCH
		if candidate['severity'] == 'urgent':
			severity = Alert.Severity.URGENT

		with transaction.atomic():
			alert = Alert.objects.create(
				circle=circle,
				created_by=None,
				title=candidate['title'],
				message=candidate['message'],
				severity=severity,
				status=Alert.Status.ACTIVE,
			)

			memberships = CircleMembership.objects.select_related('user').filter(circle=circle)
			for membership in memberships:
				Notification.objects.create(
					circle=circle,
					sent_by=None,
					recipient=membership.user,
					title=f'Insight alert: {alert.title}',
					message=alert.message,
				)

		return True