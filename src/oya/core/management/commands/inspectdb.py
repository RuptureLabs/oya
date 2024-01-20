from oya.db.migrations import Command as AerichCommand
from oya.core.management.base import BaseCommand
from oya.core.management.color import make_style
from oya.core.management.utils import coro
from oya.conf import settings



CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}



class Command(BaseCommand):
    help = "Migrate the database to the latest version."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            '--table',
            dest="table",
            nargs='+',
            help="Introspects the database tables to standard output as TortoiseORM model.",
        )

    @coro
    async def handle(self, *args, **options):
        table = options['table'] or []
        style = make_style()
        location = settings.MIGRATIONS_LOCATION
        command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, location=location)
        await command.init()
        ret = await command.inspectdb(table)
        self.stdout.write(style.WARNING(ret))
