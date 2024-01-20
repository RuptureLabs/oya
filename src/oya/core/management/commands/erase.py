import os
import shutil
from oya.core.management.utils import coro, get_oya_migrations_path
from oya.core.management.base import BaseCommand
from oya.core.management.color import make_style
from oya.db.migrations.models import Migration
from oya.conf import settings
from oya.apps import apps as oya_apps



class Command(BaseCommand):
    help = "Delete migrations folder."

    def add_arguments(self, parser):
        
        parser.add_argument(
            "-y",
            '--yes',
            action="store_true",
            dest="yes",
            help="execute without asking for confirmation.",
        )

        parser.add_argument(
            "-t",
            '--table',
            dest="table",
            action="store_true",
            help="tells oya to delete migrations table.",
        )



    @coro
    async def handle(self, *args, **options):
        style = make_style()

        if not options['yes']:
            print(style.WARNING("[***] Do you want to delete migrations folder ? [Y/n] default [n]: "), end="")
            confirm = input()
            if confirm.upper() != "Y" and confirm.upper() != "YES":
                return
            

        if options['table']:
            try:
                from oya.db.migrations import Command as AerichCommand
                command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, location=settings.MIGRATIONS_LOCATION)
                await command.init()
                await Migration.raw("DROP TABLE migration;")
                self.stdout.write(style.SUCCESS("Success drop Migration table"))
            except Exception as e:
                self.stderr.write(style.ERROR(f"Failed to drop Migration table : {e}"))

        apps = oya_apps.get_app_configs()
        for app in apps:
            mig_path = app.get_migrations_path()
            if os.path.exists(mig_path):
                shutil.rmtree(mig_path)
                self.stdout.write(
                    style.SUCCESS("Deleted migrations folder at %s" % app.label)
                )
            

        initial_mig_path = get_oya_migrations_path()
        if os.path.exists(initial_mig_path):
            shutil.rmtree(initial_mig_path)
            self.stdout.write(
                style.SUCCESS("Deleted initial schema")
            )
        