from oya.core.management.utils import coro, get_oya_migrations_path
from oya.core.management.base import BaseCommand
from oya.core.management.color import make_style
from oya.conf import settings
from oya.core.management.utils import print_banner

from oya.db.migrations import Command as AerichCommand
from ptpython.repl import embed
from tortoise.exceptions import OperationalError



class Command(BaseCommand):

    @coro
    async def handle(self, *args, **options):
        style = make_style()
        command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, location=get_oya_migrations_path())
        await command.init()
        
        try:
            await command.init_db(False)
        except (OperationalError, FileExistsError):
            pass

        try:
            print_banner()
            def exit(*args):
                print("Use Ctrl+D to exit.")
                

            await embed(
                globals=globals(),
                locals={'exit' : exit},
                title="OYA Shell",
                vi_mode=True,
                return_asyncio_coroutine=True,
                patch_stdout=True,
            )
        except (EOFError, ValueError):
            pass
