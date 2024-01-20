from tortoise.exceptions import OperationalError
from oya.db.migrations import Command as AerichCommand
from oya.core.management.base import BaseCommand
from oya.core.management.utils import coro, get_oya_migrations_path
from oya.core.management.color import make_style
from oya.conf import settings



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


class Command(BaseCommand):
    help = "Generate schema and generate app migrate location."

    def add_arguments(self, parser):
        parser.add_argument(
            "-s",
            '--safe',
            action="store_true",
            dest="safe",
            help="Folder of the source, relative to the project root.",
        )

    @coro
    async def handle(self, *args, **options):
        style = make_style()
        location = get_oya_migrations_path()
        command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, location=location)
        safe = options['safe']
        
        try:
            await command.init();
            await command.init_db(safe)
            self.stdout.write(style.SUCCESS(f"Success generate schema and create app migrate location"))
        except FileExistsError:
            self.stdout.write(style.ERROR(f"Already inited, or run 'erase' and try again."))
        
        except OperationalError as e:
            print(e)
            self.stdout.write(style.ERROR(f"Please try 'initdb -s' for safe init. it seems like the database already exists with some tables."))

