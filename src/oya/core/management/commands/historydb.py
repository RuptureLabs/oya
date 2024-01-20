from oya.db.migrations import Command as AerichCommand
from oya.core.management.base import BaseCommand
from oya.core.management.color import make_style
from oya.core.management.utils import coro, get_migratable_apps
from oya.conf import settings
from oya.apps import apps as oya_apps



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}



class Command(BaseCommand):
    help = "List all migrate items."

    def add_arguments(self, parser):
        parser.add_argument(
            "-a",
            '--app',
            nargs='*',
            dest="app",
            help="tells oya the name of the application to migrate.",
        )

    @coro
    async def handle(self, *args, **options):
        apps = options['app']
        style = make_style()

        if not apps:
            apps = get_migratable_apps()

        for app in apps:
            try:
                oya_app = oya_apps.get_app_config(app)
            except LookupError:
                self.stdout.write(
                    style.ERROR(f"Application '{app}' not found"))
                continue

            command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, app=app, location=oya_app.get_migrations_path())
            await command.init()
            try:
                versions = await command.history()
                if not versions:
                    return self.stdout.write(style.WARNING("No history, try migrate"))

                self.stdout.write(style.SUCCESS(f"--> Application {app} : "))
                for version in versions:
                    self.stdout.write(f"\t+ {version}")
            except FileNotFoundError:
                self.stdout.write(style.WARNING("No history, try 'migrate' first"))
