from oya.db.migrations import Command as AerichCommand
from oya.db.migrations.utils import add_src_path
from oya.core.management.base import BaseCommand
from oya.core.management.utils import coro, get_migratable_apps, remove_initial
from oya.core.management.color import make_style
from oya.conf import settings
from oya.apps import apps as oya_apps



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


class Command(BaseCommand):
    help = "Migrate the database to the latest version."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            nargs='?',
            help="tells oya the name of the application to migrate.",
        )

        parser.add_argument(
            "--app",
            nargs='*',
            help="tells oya the name of the application to migrate.",
        )

        parser.add_argument(
            "-s",
            '--src',
            nargs='?',
            dest="src",
            help="Folder of the source, relative to the project root.",
        )

    @coro
    async def handle(self, *args, **options):
        src_folder = options['src'] or CONFIG_DEFAULT_VALUES["src_folder"]
        add_src_path(src_folder)

        name = options['name']

        async def migrate_app(apps:list[str]):
            style = make_style()
            count_migrations = 0
            
            for app in apps:
                try:
                    oya_app = oya_apps.get_app_config(app)
                except LookupError:
                    self.stdout.write(
                        style.ERROR(f"Application '{app}' not found"))
                    continue
                        
                command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, app=app, location=oya_app.get_migrations_path())
                await command.init()
                if name:
                    res = await command.migrate(name)
                else:
                    res  = await command.migrate()
                if res:
                    count_migrations += 1
                    self.stdout.write(style.SUCCESS(f" --> Application {app} : "))
                    self.stdout.write(f"\t+ {res}")
            
            if count_migrations == 0:
                self.stdout.write(style.WARNING("No migrations found."))
            else:
                self.stdout.write(style.SUCCESS(f"{count_migrations} migrations created. Call 'migrate' to apply."))

        if apps := options['app']:
            remove_initial(apps)
            await migrate_app(apps)
        
        else:
            apps = get_migratable_apps()
            await migrate_app(apps)