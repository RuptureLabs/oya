import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
from importlib import import_module
from subprocess import run
import asyncio
from functools import wraps

from tortoise import Tortoise

from oya import __version__
from oya.apps import apps as installed_apps
from oya.conf import settings
from oya.utils.crypto import get_random_string
from oya.utils.encoding import DEFAULT_LOCALE_ENCODING
from .base import CommandError, CommandParser
from oya.db.migrations import Command as AerichCommand



def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()

        try:
            loop.run_until_complete(f(*args, **kwargs))
        finally:
            try:
                loop.run_until_complete(Tortoise.close_connections())
            except Exception: # pylint: disable=W0718
                pass  # Because some command may not use Tortoise

    return wrapper


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()

        try:
            loop.run_until_complete(f(*args, **kwargs))
        finally:
            pass

    return wrapper


def coro_initdb(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        command = AerichCommand(tortoise_config=settings.TORTOISE_ORM, location=get_oya_migrations_path())
        loop.run_until_complete(command.init())

        try:
            loop.run_until_complete(f(*args, **kwargs))
        finally:
            pass

    return wrapper


async def init_tortoise(tortoise_config):
    await Tortoise.init(tortoise_config)


async def init_tortoise_auto():
    await init_tortoise(settings.TORTOISE_ORM)


async def close_tortoise():
    await Tortoise.close_connections()


def popen_wrapper(args, stdout_encoding="utf-8"):
    """
    Friendly wrapper around Popen.

    Return stdout output, stderr output, and OS status code.
    """
    try:
        p = run(args, capture_output=True, close_fds=os.name != "nt")
    except OSError as err:
        raise CommandError("Error executing %s" % args[0]) from err
    return (
        p.stdout.decode(stdout_encoding),
        p.stderr.decode(DEFAULT_LOCALE_ENCODING, errors="replace"),
        p.returncode,
    )


def handle_extensions(extensions):
    """
    Organize multiple extensions that are separated with commas or passed by
    using --extension/-e multiple times.

    For example: running 'django-admin makemessages -e js,txt -e xhtml -a'
    would result in an extension list: ['.js', '.txt', '.xhtml']

    >>> handle_extensions(['.html', 'html,js,py,py,py,.py', 'py,.py'])
    {'.html', '.js', '.py'}
    >>> handle_extensions(['.html, txt,.tpl'])
    {'.html', '.tpl', '.txt'}
    """
    ext_list = []
    for ext in extensions:
        ext_list.extend(ext.replace(" ", "").split(","))
    for i, ext in enumerate(ext_list):
        if not ext.startswith("."):
            ext_list[i] = ".%s" % ext_list[i]
    return set(ext_list)


def find_command(cmd, path=None, pathext=None):
    if path is None:
        path = os.environ.get("PATH", "").split(os.pathsep)
    if isinstance(path, str):
        path = [path]
    # check if there are funny path extensions for executables, e.g. Windows
    if pathext is None:
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep)
    # don't use extensions if the command ends with one of them
    for ext in pathext:
        if cmd.endswith(ext):
            pathext = [""]
            break
    # check if we find the command on PATH
    for p in path:
        f = os.path.join(p, cmd)
        if os.path.isfile(f):
            return f
        for ext in pathext:
            fext = f + ext
            if os.path.isfile(fext):
                return fext
    return None


def get_random_secret_key():
    """
    Return a 50 character random string usable as a SECRET_KEY setting value.
    """
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return get_random_string(50, chars)


def parse_apps_and_model_labels(labels):
    """
    Parse a list of "app_label.ModelName" or "app_label" strings into actual
    objects and return a two-element tuple:
        (set of model classes, set of app_configs).
    Raise a CommandError if some specified models or apps don't exist.
    """
    apps = set()
    models = set()

    for label in labels:
        if "." in label:
            try:
                model = installed_apps.get_model(label)
            except LookupError as exc:
                raise CommandError("Unknown model: %s" % label) from exc
            models.add(model)
        else:
            try:
                app_config = installed_apps.get_app_config(label)
            except LookupError as e:
                raise CommandError from  e
            apps.add(app_config)

    return models, apps


def get_command_line_option(argv, option):
    """
    Return the value of a command line option (which should include leading
    dashes, e.g. '--testrunner') from an argument list. Return None if the
    option wasn't passed or if the argument list couldn't be parsed.
    """
    parser = CommandParser(add_help=False, allow_abbrev=False)
    parser.add_argument(option, dest="value")
    try:
        options, _ = parser.parse_known_args(argv[2:])
    except CommandError:
        return None
    else:
        return options.value


def normalize_path_patterns(patterns):
    """Normalize an iterable of glob style patterns based on OS."""
    patterns = [os.path.normcase(p) for p in patterns]
    dir_suffixes = {"%s*" % path_sep for path_sep in {"/", os.sep}}
    norm_patterns = []
    for pattern in patterns:
        for dir_suffix in dir_suffixes:
            if pattern.endswith(dir_suffix):
                norm_patterns.append(pattern.removesuffix(dir_suffix))
                break
        else:
            norm_patterns.append(pattern)
    return norm_patterns


def is_ignored_path(path, ignore_patterns):
    """
    Check if the given path should be ignored or not based on matching
    one of the glob style `ignore_patterns`.
    """
    path = Path(path)

    def ignore(pattern):
        return fnmatch.fnmatchcase(path.name, pattern) or fnmatch.fnmatchcase(
            str(path), pattern
        )

    return any(ignore(pattern) for pattern in normalize_path_patterns(ignore_patterns))


def find_formatters():
    return {"black_path": shutil.which("black")}


def run_formatters(written_files, black_path=(sentinel := object())):
    """
    Run the black formatter on the specified files.
    """
    # Use a sentinel rather than None, as which() returns None when not found.
    if black_path is sentinel:
        black_path = shutil.which("black")
    if black_path:
        subprocess.run(
            [black_path, "--fast", "--", *written_files],
            capture_output=True,
        )


def get_oya_migrations_path() -> str:
    """
    Used for initial migrations, returns the path of project
    """
    project_module = import_module(os.environ['OYA_SETTINGS_MODULE'])
    return os.path.join(os.path.dirname(project_module.__file__), settings.APP_MIGRATIONS_FOLDER + "_dev")

def remove_initial(apps):
    """
    Used for initial migrations, removes oya.db.migrations, when makemigrations runs, because it's not needed
    """
    try:
        apps.remove('oya.db.migrations')
    except ValueError:
        pass


def get_migratable_apps() -> list[str]:
    """
    Returns all apps except oya.db.migrations
    """
    apps = list(settings.TORTOISE_ORM['apps'].keys()) # need to remove oya.db.migrations
    remove_initial(apps)
    return apps


def print_banner():
    banner = f"\n OYA {__version__}. Copyright (c) OyaBytes 2023."
    print(banner)
    print( " " + " MIT License. ".center(len(banner) - 1, "-"), end="\n\n")
