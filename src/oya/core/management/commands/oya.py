from oya.core.management import BaseCommand
from oya.core.initializer.starter import main

class Command(BaseCommand):
    add_help = False

    def handle(self, *args, **options):
        main()
