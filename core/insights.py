from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import VoiceLog


TREND_DEFINITIONS = [
	{
		'key': 'hydration_mentions',
		'label': 'Hydration mentions',
		'keywords': ['hydration', 'water', 'drink', 'drank', 'dehydrated', 'thirsty'],
		'higher_is_better': True,
		'unit': 'mentions/day',
		'alert_floor': 0.5,
	},
	{
		'key': 'fatigue_mentions',
		'label': 'Fatigue mentions',
		'keywords': ['tired', 'fatigue', 'exhausted', 'lethargic', 'weak'],
		'higher_is_better': False,
		'unit': 'mentions/day',
		'alert_floor': 1.5,
	},
	{
		'key': 'sleep_disruption_mentions',
		'label': 'Sleep disruption mentions',
		'keywords': ['insomnia', 'awake', 'restless', 'poor sleep', 'could not sleep'],
		'higher_is_better': False,
		'unit': 'mentions/day',
		'alert_floor': 1.0,
	},
	{
		'key': 'low_mood_mentions',
		'label': 'Low mood mentions',
		'keywords': ['sad', 'anxious', 'worried', 'irritable', 'low mood', 'down'],
		'higher_is_better': False,
		'unit': 'mentions/day',
		'alert_floor': 1.0,
	},
]


def _safe_average(values):
	if not values:
		return 0.0
	return round(sum(values) / len(values), 2)


def _trend_direction(current, baseline, higher_is_better):
	if current == baseline:
		return 'steady'

	if higher_is_better:
		return 'up' if current > baseline else 'down'

	return 'down' if current < baseline else 'up'


def build_characteristic_trends(circle, days=14):
	if circle is None:
		return []

	now = timezone.now()
	start = now - timedelta(days=days - 1)

	logs = (
		VoiceLog.objects.filter(
			circle=circle,
			status=VoiceLog.Status.COMPLETED,
			created_at__gte=start,
		)
		.only('created_at', 'transcript', 'extracted_signals')
		.order_by('created_at')
	)

	day_keys = []
	for offset in range(days):
		day = (start + timedelta(days=offset)).date()
		day_keys.append(day)

	counts = {definition['key']: defaultdict(int) for definition in TREND_DEFINITIONS}

	for log in logs:
		day = timezone.localtime(log.created_at).date()
		blob = ' '.join((log.transcript or '', ' '.join(log.extracted_signals or []))).lower()
		for definition in TREND_DEFINITIONS:
			if any(keyword in blob for keyword in definition['keywords']):
				counts[definition['key']][day] += 1

	trends = []
	for definition in TREND_DEFINITIONS:
		series = [counts[definition['key']].get(day, 0) for day in day_keys]
		baseline = _safe_average(series[: max(1, days - 3)])
		current = _safe_average(series[-3:])
		trends.append(
			{
				'key': definition['key'],
				'label': definition['label'],
				'unit': definition['unit'],
				'higher_is_better': definition['higher_is_better'],
				'direction': _trend_direction(current, baseline, definition['higher_is_better']),
				'current_average': current,
				'baseline_average': baseline,
				'history': [
					{
						'date': day.isoformat(),
						'value': value,
					}
					for day, value in zip(day_keys, series)
				],
			}
		)

	return trends


def build_trend_alert_candidates(trends):
	candidates = []

	for trend in trends:
		key = trend['key']
		current = trend['current_average']
		baseline = trend['baseline_average']
		direction = trend['direction']

		if key == 'hydration_mentions':
			if baseline >= 1.0 and current <= 0.2:
				candidates.append(
					{
						'severity': 'urgent',
						'title': 'Hydration trend dropped',
						'message': (
							'Hydration mentions are down over the last 3 days compared with the previous 11 days. '
							'Please verify fluid intake and keep closer watch updates today.'
						),
					}
				)
			elif baseline >= 0.5 and direction == 'down' and current <= (baseline * 0.4):
				candidates.append(
					{
						'severity': 'watch',
						'title': 'Hydration trend softening',
						'message': (
							'Hydration mentions are trending lower this week. '
							'Consider adding a hydration check-in to the care routine.'
						),
					}
				)

		if key in {'fatigue_mentions', 'sleep_disruption_mentions', 'low_mood_mentions'}:
			if current >= max(2.0, baseline + 1.0):
				severity = 'urgent' if current >= max(3.0, baseline + 1.8) else 'watch'
				candidates.append(
					{
						'severity': severity,
						'title': f"{trend['label']} increasing",
						'message': (
							f"{trend['label']} increased in the last 3 days compared with the earlier baseline. "
							'Consider a direct check-in and monitor for additional changes.'
						),
					}
				)

	return candidates