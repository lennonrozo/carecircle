from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.management.commands.seed_demo_circle import DEMO_CIRCLE_NAME
from core.models import Alert, Circle, CircleMembership, FeedEntry, Notification, Task, VoiceLog


class Command(BaseCommand):
    help = 'Prove empty-state conditions for a target interface and optionally restore demo data.'

    INTERFACES = ['activity', 'tasks', 'feed', 'voice', 'insights']

    def add_arguments(self, parser):
        target_group = parser.add_mutually_exclusive_group(required=True)
        target_group.add_argument(
            '--interface',
            choices=self.INTERFACES,
            help='Interface empty state to prove.',
        )
        target_group.add_argument(
            '--all',
            action='store_true',
            help='Run empty-state proof for all interfaces in sequence.',
        )
        parser.add_argument(
            '--no-restore',
            action='store_true',
            help='Do not reseed demo data after proof.',
        )

    def run_interface_proof(self, circle, interface):
        if interface == 'activity':
            CircleMembership.objects.filter(circle=circle).delete()
            Notification.objects.filter(circle=circle).delete()
            Alert.objects.filter(circle=circle).delete()
            Task.objects.filter(circle=circle).delete()
            FeedEntry.objects.filter(circle=circle).delete()
            VoiceLog.objects.filter(circle=circle).delete()

            is_empty = (
                CircleMembership.objects.filter(circle=circle).count() == 0
                and Notification.objects.filter(circle=circle).count() == 0
                and Alert.objects.filter(circle=circle).count() == 0
                and Task.objects.filter(circle=circle).count() == 0
            )
            self.stdout.write(self.style.SUCCESS(f'Proof: recent activity empty = {is_empty}'))

        elif interface == 'tasks':
            Task.objects.filter(circle=circle).delete()
            task_count = Task.objects.filter(circle=circle).count()
            self.stdout.write(self.style.SUCCESS(f'Proof: tasks empty = {task_count == 0} (count={task_count})'))

        elif interface == 'feed':
            FeedEntry.objects.filter(circle=circle).delete()
            feed_count = FeedEntry.objects.filter(circle=circle).count()
            self.stdout.write(self.style.SUCCESS(f'Proof: feed empty = {feed_count == 0} (count={feed_count})'))

        elif interface == 'voice':
            VoiceLog.objects.filter(circle=circle).delete()
            voice_count = VoiceLog.objects.filter(circle=circle).count()
            self.stdout.write(self.style.SUCCESS(f'Proof: voice logs empty = {voice_count == 0} (count={voice_count})'))

        elif interface == 'insights':
            VoiceLog.objects.filter(circle=circle).delete()
            Alert.objects.filter(circle=circle).delete()
            FeedEntry.objects.filter(circle=circle).delete()
            voice_count = VoiceLog.objects.filter(circle=circle).count()
            alert_count = Alert.objects.filter(circle=circle).count()
            feed_count = FeedEntry.objects.filter(circle=circle).count()
            is_empty = voice_count == 0 and alert_count == 0 and feed_count == 0
            self.stdout.write(self.style.SUCCESS(
                f'Proof: insights inputs empty = {is_empty} (voice={voice_count}, alerts={alert_count}, feed={feed_count})'
            ))

    def handle(self, *args, **options):
        interface = options.get('interface')
        run_all = options.get('all')
        should_restore = not options['no_restore']

        circle = Circle.objects.filter(name=DEMO_CIRCLE_NAME).first() or Circle.objects.filter(pk=2).first() or Circle.objects.order_by('id').first()
        if circle is None:
            raise CommandError('No circle found to run empty-state proof against.')

        self.stdout.write(f'Using circle: {circle.name} (id={circle.id})')

        if run_all:
            for target in self.INTERFACES:
                self.stdout.write(self.style.NOTICE(f'----- {target} -----'))
                self.run_interface_proof(circle, target)
        else:
            self.run_interface_proof(circle, interface)

        if should_restore:
            call_command('seed_demo_circle')
            self.stdout.write(self.style.SUCCESS('Demo data restored via seed_demo_circle.'))
        else:
            self.stdout.write('Restore skipped (--no-restore).')
