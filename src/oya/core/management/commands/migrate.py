from oya.db.migrations import Command as AerichCommand
from oya.core.management.base import BaseCommand
from oya.core.management.utils import coro, get_migratable_apps, remove_initial
from oya.core.management.color import make_style
from oya.apps import apps as oya_apps
from oya.conf import settings



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


class Command(BaseCommand):
    help = "Upgrade to specified version."

    def add_arguments(self, parser):
        parser.add_argument(
            "-i",
            '--in-transaction',
            dest="transaction",
            default=True,
            action="store_true",
            help="Make migrations in transaction or not. Can be helpful for large migrations or creating concurrent indexes.",
        )

        parser.add_argument(
            "-a",
            '--app',
            nargs='*',
            dest="app",
            help="tells oya the name of the application to upgrade.",
        )

    @coro
    async def handle(self, *args, **options):
        style = make_style()
        count_migrations = 0
        
        if apps := options['app']:
            remove_initial(apps)
        else:
            apps = get_migratable_apps()

        
        for app in apps:
            try:
                oya_app = oya_apps.get_app_config(app)
            except LookupError:
                self.stdout.write(
                    style.ERROR(f"Application '{app}' not found"))
                continue
            
            command = AerichCommand(tortoise_config=settings.TORTOISE_ORM,app=app, location=oya_app.get_migrations_path())
            await command.init()
            migrated = await command.upgrade(run_in_transaction=options['transaction'])
            
            if migrated:
                count_migrations += len(migrated)
                for version_file in migrated:
                    self.stdout.write(style.WARNING(f"Success upgrade {version_file}"))

        if count_migrations == 0:
                self.stdout.write(style.WARNING("No upgrade items found"))
        else:
            self.stdout.write(style.SUCCESS(f"Success upgrade {count_migrations} migrations applied."))
