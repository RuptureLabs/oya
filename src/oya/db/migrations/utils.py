import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Dict
from tortoise import BaseDBAsyncClient, Tortoise

from oya.core.management.color import make_style


style = make_style()


def add_src_path(path: str) -> str:
    """
    add a folder to the paths, so we can import from there
    :param path: path to add
    :return: absolute path
    """
    if not os.path.isabs(path):
        # use the absolute path, otherwise some other things (e.g. __file__) won't work properly
        path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Specified source folder does not exist: {path}")
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def get_app_connection_name(config, app_name: str) -> str:
    """
    get connection name
    :param config:
    :param app_name:
    :return:
    """
    app = config.get("apps").get(app_name)
    if app:
        return app.get("default_connection", "default")
    raise LookupError(f'Can\'t get app named "{app_name}"')


def get_app_connection(config, app) -> BaseDBAsyncClient:
    """
    get connection name
    :param config:
    :param app:
    :return:
    """
    return Tortoise.get_connection(get_app_connection_name(config, app))



def get_models_describe(app: str) -> Dict:
    """
    get app models describe
    :param app:
    :return:
    """
    ret = {}
    
    for model in Tortoise.apps.get(app).values():
        describe = model.describe()
        ret[describe.get("name")] = describe
    return ret


def is_default_function(string: str):
    return re.match(r"^<function.+>$", str(string or ""))


def import_py_file(file: Path):
    module_name, file_ext = os.path.splitext(os.path.split(file)[-1])
    spec = importlib.util.spec_from_file_location(module_name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
