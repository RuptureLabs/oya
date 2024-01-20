from __future__ import annotations
from typing import List, Any
import os, sys
import stat
import shutil
import argparse
from importlib.util import find_spec

import black
from jinja2 import Environment, FileSystemLoader

import oya

os.environ.setdefault('OYA_SETTINGS_MODULE', 'oya.conf.global_settings')
os.environ.setdefault('INITIALISER', 'RUN')

from oya.core.management.utils import get_random_secret_key 
from oya.core.management.base import BaseCommand, CommandError


STATIC_DIR = 'static'
TEMPLATES_DIR = 'templates'

class Command(BaseCommand):
    help = 'A template starter for oya project or oya application'

    requires_system_checks: List = []

    url_schemes: List = ['http', 'https', 'ftp']


    def add_arguments(self, parser : argparse.ArgumentParser) -> None:
        parser.add_argument('name', help='Name of the application or project.')
        parser.add_argument(
            '--directory',
            '-d',
            dest='directory',
            nargs=1,
            help="Optional destination directory"
            )

        parser.add_argument(
            '--project',
            '-p',
            action='store_true',
            dest='project',
            help="Set the template's category as a project"
        )

        parser.add_argument(
            '--application',
            '-a',
            action='store_true',
            dest='application',
            help="Set the template's category as an application"
        )


    def handle(self, name:str, **options):
        # pylint: disable=W0221
        # pylint: disable=W0201

        self.app_or_project_name = name
        self.verbosity: Any =  options['verbosity']

        if (options['application'] and options['project']) or (not options['application'] and not options['project']):
            self.stdout.write(
                "Please you must provide one argument --project/-p OR --application/-a"
            )
            sys.exit(-1)
        else:
            self.is_application = options['application'] == True
            self.a_or_an = "an" if self.is_application else "a"

        target = options['directory']

        self.validate_name(name)

        base_name = name
        camel_case_name = self.camel_case(name)
        snake_case_name = self.snake_case(name)

        if target is None:
            root_dir = os.path.join(os.getcwd(), snake_case_name)
            try:
                os.makedirs(root_dir)
            except FileExistsError as e:
                raise CommandError("'%s' already exists" % root_dir) from e
            except OSError as e:
                raise CommandError from  e
        else:
            target = target[0]
            root_dir = os.path.abspath(os.path.expanduser(target))
            if self.is_application:
                self.validate_name(os.path.basename(root_dir), 'directory')
                
            if not os.path.exists(root_dir):
                raise CommandError(
                    "Destination directory '%s' does not "
                    "exist, please create it first." % root_dir
                )


        template_context = {
            "oya_version": oya.__version__,
            'secret_key' : get_random_secret_key(),
            'base_name' : base_name,
            'camel_case_name' : camel_case_name,
            'snake_case_name' : snake_case_name,
        }


        if self.is_application:
            _tpl_dir = "application"
        else:
            _tpl_dir = "project"


        TEMPLATE_BASE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
        TEMPLATE_DIR = os.path.join(TEMPLATE_BASE_DIR, _tpl_dir)

        tree = os.walk(TEMPLATE_DIR)

        if self.is_application and target is not None:
            output_dir_path = os.path.join(root_dir, snake_case_name)
        elif self.is_application:
            output_dir_path = root_dir
        else:
            output_dir_path = os.path.join(root_dir, camel_case_name)

        if not os.path.exists(output_dir_path):
            os.mkdir(output_dir_path)

        if not self.is_application:
            self.copy_jinja_file(TEMPLATE_BASE_DIR, 'manage.py.jinja', root_dir, template_context)
            os.mkdir(os.path.join(root_dir, STATIC_DIR))
            os.mkdir(os.path.join(root_dir, TEMPLATES_DIR))

        for directory in tree:
            dir_path, sub_dir_names, files_names = directory


            for sub_dir_name in sub_dir_names:
                if sub_dir_name.startswith("_"):
                    continue

                sub_dir_path = os.path.join(dir_path, sub_dir_name)
                if not os.path.exists(sub_dir_path):
                    os.mkdir(sub_dir_path)

                self.make_writeable(sub_dir_path)


            for file_name in files_names:
                if file_name.startswith("_") and file_name != "__init__.py.jinja":
                    continue

                extension = file_name.rsplit('.')[0]
                if extension in (".pyo", ".pyc", ".py.class"):
                    continue

                if file_name.endswith('.jinja'):
                    self.copy_jinja_file(dir_path, file_name, output_dir_path, template_context)
                else:
                    shutil.copyfile(
                        os.path.join(dir_path, file_name),
                        os.path.join(output_dir_path, file_name),
                    )


    def copy_jinja_file(self, template_path:str, file_name:str, output_dir_path:str, context:dict):
        output_file_name = file_name.replace('.jinja', '')
        template = Environment(
            loader=FileSystemLoader(searchpath=template_path)
        ).get_template(file_name)

        output_contents = template.render(**context)

        if output_file_name.endswith('.py'):
            try:
                output_contents = black.format_str(
                    output_contents,
                    mode=black.FileMode(line_length=80),
                )
            except Exception as exception:
                print(f"Problem processing {output_file_name}")
                raise exception from exception

        with open(os.path.join(output_dir_path, output_file_name), 'w') as output_file: # pylint: disable=W1514
            output_file.write(output_contents)


    def validate_name(self, name: str, name_or_dir='name') -> None:
        """
        Validate Application or project name
        """
        if name is None:
            raise CommandError(
                "you must provide {an} {app} name".format(
                    an=self.a_or_an,
                    app=self.app_or_project_name
                )
            )

        if not name.isidentifier():
            raise CommandError(
                "'{name}' is not a valid {app} {type}. Please make sure the "
                "{type} is valid identifier.".format(
                    name=name,
                    app=self.app_or_project_name,
                    type='name'
                )
            )

        if find_spec(name) is not None and name_or_dir != 'directory':
            raise CommandError(
                "'{name}' conflicts with the name of an existing python "
                "module and cannot be used as {an} {app} {type}. Please try "
                "another {type}.".format(
                    name=name,
                    an=self.a_or_an,
                    app=self.app_or_project_name,
                    type=name_or_dir
                )
            )


    def make_writeable(self, filename):
        """
        Make sure that the file is writeable.
        Useful if our source is read-only.
        """
        if not os.access(filename, os.W_OK):
            st = os.stat(filename)
            new_permissions = stat.S_IMODE(st.st_mode) | stat.S_IWUSR
            os.chmod(filename, new_permissions)


    def snake_case(self, name:str):
        """
        Convert string to snake_case, words must be separate by spaces, to work correctly.
        """
        return name.replace(" ", "_").lower()


    def camel_case(self, name: str):
        """
        Convert String to CamelCase
        """
        return name.replace('_', ' ').title().replace(' ', '')


def main():
    try:
        sys.argv.insert(1, 'oya')           # necessary ?
        Command().run_from_argv(sys.argv)   # yes, to avoid IndexError from create_parser
    except CommandError as exc:
        print(f'[*_*] {exc}')


if __name__ == '__main__':
    main()
