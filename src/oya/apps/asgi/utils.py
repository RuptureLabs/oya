from typing import List, Iterable
from pathlib import Path
from litestar.template.config import TemplateConfig
from litestar.static_files.config import StaticFilesConfig

from oya.conf import settings
from oya.core.exceptions import ImproperlyConfigured, LoadMiddlewareError
from oya.utils.module_loading import import_string



def get_template_config() -> TemplateConfig | None:
    """Get template configuration.

    Returns:
        TemplateConfig | None: Template configuration.

    Raises:
        ImproperlyConfigured: If settings.TEMPLATES is not a TemplateConfig or dict.
    """
    if not settings.TEMPLATES:
        return None

    if isinstance(settings.TEMPLATES, TemplateConfig):
        return settings.TEMPLATES

    if isinstance(settings.TEMPLATES, dict):
        try:
            _dirs = settings.TEMPLATES["DIRS"]
            _engine = settings.TEMPLATES["ENGINE"]
        except LookupError as exc:
            raise ImproperlyConfigured("Unable to find template directory and/or template engine.") from exc
        
        return TemplateConfig(directory=_dirs, engine=_engine)
        
    raise ImproperlyConfigured("settings.TEMPLATES must be a TemplateConfig or dict.")



def _parse_static_config(conf: dict) -> StaticFilesConfig:
    """Parse static files configuration.

    Args:
        conf (dict): Static files configuration.

    Returns:
        StaticFilesConfig: Static files configuration.
    """
    _conf = {}
    _dirs = conf.get("DIRS", None)
    if _dirs is None or not isinstance(_dirs, (list, tuple)) or len(_dirs) < 1:
        raise ImproperlyConfigured("settings.STATIC_FILES.DIRS must be a list and must contain at least one directory.")
    
    _conf["directories"] = _dirs

    _path = conf.get("PATH", None)
    if _path is None or not isinstance(_path, (str, Path)):
        raise ImproperlyConfigured("settings.STATIC_FILES.PATH must be a string or a Path instance.")
    _conf["path"] = _path

    _conf["html_mode"] = True if conf.get("HTML_MODE", None) else False

    _conf["send_as_attachment"] = True if conf.get("AS_ATTACHMENT", None) else False

    _name = conf.get("NAME", None)
    if _name and isinstance(_name, str):
        _conf["name"] = _name

    return StaticFilesConfig(**_conf)


def get_static_file_config() -> List[StaticFilesConfig]:
    """Get static files configuration.

    Returns:
        List[StaticFilesConfig]: Static files configuration.

    Raises:
        ImproperlyConfigured: If settings.STATIC_FILES has a dictionary that is missing the path and/or folders attribute.
    """
    configs = []
    if isinstance(settings.STATIC_FILES, list) or isinstance(settings.STATIC_FILES, tuple):
        for conf in settings.STATIC_FILES:
            if isinstance(conf, dict):
                configs.append(_parse_static_config(conf))
            elif isinstance(conf, StaticFilesConfig):
                configs.append(conf)
            else:
                raise ImproperlyConfigured("settings.STATIC_FILES element must be a dict or StaticFilesConfig.")
        
        return configs
    raise ImproperlyConfigured("settings.STATIC_FILES must be a list or tuple.")



def get_middleware():
    """Load Middlewares from oya settings"""
    _mids = []
    if hasattr(settings, 'MIDDLEWARE'):
        mids:Iterable = settings.MIDDLEWARE
        for mid in mids:
            if isinstance(mid, str):
                try:
                    _mid = import_string(mid)
                    _mids.append(_mid)
                except Exception as ex:
                    raise LoadMiddlewareError(f"failed to load {mid}, {ex}") from ex
            else:
                raise ImproperlyConfigured(f"middleware in settings.MIDDLEWARE must compatible string for import, {mid} is not a string")

    return _mids
