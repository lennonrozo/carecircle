from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.management.commands.seed_demo_circle import DEMO_CIRCLE_NAME, DEMO_USERS
from core.models import Circle


User = get_user_model()


class Command(BaseCommand):
    help = 'Delete the seeded demo circle and demo users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip interactive confirmation.',
        )

    def handle(self, *args, **options):
        if not options['yes']:
            confirmation = input('Delete seeded demo circle and demo users? (yes/no): ').strip().lower()
            if confirmation != 'yes':
                self.stdout.write('Cancelled.')
                return

        circle_qs = Circle.objects.filter(name=DEMO_CIRCLE_NAME)
        circle_count = circle_qs.count()
        circle_qs.delete()

        emails = [row['email'] for row in DEMO_USERS]
        users_qs = User.objects.filter(email__in=emails)
        user_count = users_qs.count()
        users_qs.delete()

        self.stdout.write(self.style.SUCCESS('Demo data purge complete.'))
        self.stdout.write(f'Circles deleted: {circle_count}')
        self.stdout.write(f'Users deleted: {user_count}')
