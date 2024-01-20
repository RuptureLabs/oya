from oya.db.migrations import Command as AerichCommand
from oya.core.management.base import BaseCommand
from oya.core.management.utils import coro
from oya.core.management.color import make_style
from oya.apps import apps as oya_apps
from oya.conf import settings



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


class Command(BaseCommand):
    help = "Show current available heads in migrate location."

    @coro
    async def handle(self, *args, **options):
        style = make_style()
        count_heads = 0
        apps = oya_apps.get_app_configs()

        for app in apps:
            command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, app=app.label, location=app.get_migrations_path())
            await command.init()
            try:
                head_list = await command.heads()
                if head_list:
                    count_heads += 1
                    self.stdout.write(style.SUCCESS(f"--> Application {app.label} : "))

                for version in head_list:
                    self.stdout.write(f"\t+ {version}")
            except FileNotFoundError:
                self.stdout.write(style.WARNING("No available heads, try 'makemigrations' first"))

        if count_heads == 0:
            return self.stdout.write(style.WARNING("No available heads, try 'makemigrations' first"))
