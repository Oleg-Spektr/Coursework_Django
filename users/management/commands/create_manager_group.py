from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Создаёт группу Менеджер с необходимыми правами'

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Менеджер')
        perms = Permission.objects.filter(
            codename__in=['can_disable_mailing', 'can_block_user']
        )
        group.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS('Группа "Менеджер" успешно настроена!'))
