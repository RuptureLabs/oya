# pylint: disable=no-value-for-parameter

import sys
from uvicorn import main
from oya.conf import settings
from oya.core.management.base import BaseCommand
from oya.core.management.utils import print_banner


class Command(BaseCommand):
    help = "An interface for uvicorn"
    add_help = False # don't add -h/--help and argparse have to accept unknown options

    
    def handle(self, *args, **options):
        print_banner()
        sys.argv = sys.argv[1:]
        sys.argv.insert(1, settings.ASGI_APPLICATION)
        sys.exit(main()) # ignore: E1120