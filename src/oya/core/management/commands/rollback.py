from oya.db.migrations import Command as AerichCommand
from oya.core.exceptions import DowngradeError
from oya.core.management.base import BaseCommand
from oya.core.management.utils import coro
from oya.core.management.color import make_style
from oya.conf import settings
from oya.apps import apps as oya_apps



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


class Command(BaseCommand):
    help = "Downgrade to specified version."

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            '--delete',
            dest="delete",
            default=False,
            action="store_true",
            help="Delete version files at the same time.",
        )

        parser.add_argument(
            "-V",
            '--Version',
            dest="Version",
            type=int,
            default=-1,
            nargs=1,
            required=True,
            help="Specified version, default to last.",
        )

        parser.add_argument(
            "-a",
            '--app',
            nargs=1,
            dest="app",
            required=True,
            help="tells oya the name of the application to downgrade.",
        )

    @coro
    async def handle(self, *args, **options):
        app = options['app'][0]
        style = make_style()
        try:
            oya_app = oya_apps.get_app_config(app)
        except LookupError:
            return self.stdout.write(
                style.ERROR(f"Application '{app}' not found"))
        
        command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, app=app, location=oya_app.get_migrations_path())
        await command.init()
        print(options['Version'][0])
        try:
            files = await command.downgrade(options['Version'][0], options['delete'])
        except DowngradeError as e:
            return self.stdout.write(
                style.ERROR(f"Downgrade error: {e}"))
        for file in files:
            self.stdout.write(style.SUCCESS(f"Success downgrade {file}"))
