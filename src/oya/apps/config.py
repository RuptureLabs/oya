"""
This file was copied from Django framework.
https://github.com/django/django/blob/master/django/apps/config.py
"""

# pylint: disable=broad-exception-caught

import inspect
import os
from importlib import import_module
from types import ModuleType

from oya.core.exceptions import ImproperlyConfigured
from oya.utils.module_loading import import_string, module_has_submodule
from oya.conf import settings

APPS_MODULE_NAME = "apps"
MODELS_MODULE_NAME = "models"
ENDPOINTS_MODULE_NAME = "endpoints"



class AppConfig:
    """
    Class representing a Oya application and its configuration.
    """

    def __init__(self, app_name : str, app_module : ModuleType):
        # Full Python path to the application e.g. 'oya.contrib.admin'.
        self.name = app_name

        # Root module for the application e.g. <module 'oya.contrib.admin'
        # from 'django/contrib/admin/__init__.py'>.
        self.module = app_module

        # Reference to the Apps registry that holds this AppConfig. Set by the
        # registry when it registers the AppConfig instance.
        self.apps = None

        # The following attributes could be defined at the class level in a
        # subclass, hence the test-and-set pattern.

        # Last component of the Python path to the application e.g. 'admin'.
        # This value must be unique across a Oya project.
        
        if not hasattr(self, "label"):
            self.label = app_name.rpartition(".")[2]
        if not self.label.isidentifier():
            raise ImproperlyConfigured(
                "The app label '%s' is not a valid Python identifier." % self.label
            )

        # Human-readable name for the application e.g. "Admin".
        if not hasattr(self, "verbose_name"):
            self.verbose_name = self.label.title()

        # Filesystem path to the application directory e.g.
        # '/path/to/django/contrib/admin'.
        if not hasattr(self, "path"):
            self.path = self._path_from_module(app_module)

        # Module containing models e.g. <module 'django.contrib.admin.models'
        # from 'django/contrib/admin/models.py'>. Set by import_models().
        # None if the application doesn't have a models module.
        self.models_module = None

        # Mapping of lowercase model names to model classes. Initially set to
        # None to prevent accidental access before import_models() runs.
        self.models = None

        self.endpoints : ModuleType = object()

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.label)

    
    def _path_from_module(self, module : ModuleType) -> str:
        """Attempt to determine app's filesystem path from its module."""
        # See #21874 for extended discussion of the behavior of this method in
        # various cases.
        # Convert to list because __path__ may not support indexing.
        paths = list(getattr(module, "__path__", []))
        if len(paths) != 1:
            filename = getattr(module, "__file__", None)
            if filename is not None:
                paths = [os.path.dirname(filename)]
            else:
                # For unknown reasons, sometimes the list returned by __path__
                # contains duplicates that must be removed (#25246).
                paths = list(set(paths))
        if len(paths) > 1:
            raise ImproperlyConfigured(
                "The app module %r has multiple filesystem locations (%r); "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % (module, paths)
            )
        elif not paths:
            raise ImproperlyConfigured(
                "The app module %r has no filesystem location, "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % module
            )
        return paths[0]

    @classmethod
    def create(cls, entry:str):
        """
        Factory that creates an app config from an entry in INSTALLED_APPS.
        """
        # create() eventually returns app_config_class(app_name, app_module).
        app_config_class = None
        app_name = None
        app_module = None

        # If import_module succeeds, entry points to the app module.
        try:
            app_module = import_module(entry)
        except Exception:
            pass
        else:
            # If app_module has an apps submodule that defines a single
            # AppConfig subclass, use it automatically.
            # To prevent this, an AppConfig subclass can declare a class
            # variable default = False.
            # If the apps module defines more than one AppConfig subclass,
            # the default one can declare default = True.
            if module_has_submodule(app_module, APPS_MODULE_NAME):
                mod_path = "%s.%s" % (entry, APPS_MODULE_NAME)
                mod = import_module(mod_path)
                # Check if there's exactly one AppConfig candidate,
                # excluding those that explicitly define default = False.
                app_configs = [
                    (name, candidate)
                    for name, candidate in inspect.getmembers(mod, inspect.isclass)
                    if (
                        issubclass(candidate, cls)
                        and candidate is not cls
                        and getattr(candidate, "default", True)
                    )
                ]
                if len(app_configs) == 1:
                    app_config_class = app_configs[0][1]
                else:
                    # Check if there's exactly one AppConfig subclass,
                    # among those that explicitly define default = True.
                    app_configs = [
                        (name, candidate)
                        for name, candidate in app_configs
                        if getattr(candidate, "default", False)
                    ]
                    if len(app_configs) > 1:
                        candidates = [repr(name) for name, _ in app_configs]
                        raise RuntimeError(
                            "%r declares more than one default AppConfig: "
                            "%s." % (mod_path, ", ".join(candidates))
                        )
                    elif len(app_configs) == 1:
                        app_config_class = app_configs[0][1]

            # Use the default app config class if we didn't find anything.
            if app_config_class is None:
                app_config_class = cls
                app_name = entry

        # If import_string succeeds, entry is an app config class.
        if app_config_class is None:
            try:
                app_config_class = import_string(entry)
            except Exception:
                pass
        # If both import_module and import_string failed, it means that entry
        # doesn't have a valid value.
        if app_module is None and app_config_class is None:
            # If the last component of entry starts with an uppercase letter,
            # then it was likely intended to be an app config class; if not,
            # an app module. Provide a nice error message in both cases.
            mod_path, _, cls_name = entry.rpartition(".")
            if mod_path and cls_name[0].isupper():
                # We could simply re-trigger the string import exception, but
                # we're going the extra mile and providing a better error
                # message for typos in INSTALLED_APPS.
                # This may raise ImportError, which is the best exception
                # possible if the module at mod_path cannot be imported.
                mod = import_module(mod_path)
                candidates = [
                    repr(name)
                    for name, candidate in inspect.getmembers(mod, inspect.isclass)
                    if issubclass(candidate, cls) and candidate is not cls
                ]
                msg = "Module '%s' does not contain a '%s' class." % (
                    mod_path,
                    cls_name,
                )
                if candidates:
                    msg += " Choices are: %s." % ", ".join(candidates)
                raise ImportError(msg)
            else:
                # Re-trigger the module import exception.
                import_module(entry)

        # Check for obvious errors. (This check prevents duck typing, but
        # it could be removed if it became a problem in practice.)
        if not issubclass(app_config_class, AppConfig):
            raise ImproperlyConfigured("'%s' isn't a subclass of AppConfig." % entry)

        # Obtain app name here rather than in AppClass.__init__ to keep
        # all error checking for entries in INSTALLED_APPS in one place.
        if app_name is None:
            try:
                app_name = app_config_class.name
            except AttributeError as exc:
                raise ImproperlyConfigured("'%s' must supply a name attribute." % entry) from exc

        # Ensure app_name points to a valid module.
        try:
            app_module = import_module(app_name)
        except ImportError as exc:
            raise ImproperlyConfigured(
                "Cannot import '%s'. Check that '%s.%s.name' is correct."
                % (
                    app_name,
                    app_config_class.__module__,
                    app_config_class.__qualname__,
                )
            ) from exc

        # Entry is a path to an app config class.
        return app_config_class(app_name, app_module)

    def get_models(self):
        # params will be removed
        return self.models

    def import_models(self):
        if module_has_submodule(self.module, MODELS_MODULE_NAME):
            self.models = "%s.%s" % (self.name, MODELS_MODULE_NAME)
            self.models_module = import_module(self.models)

    def has_model(self, model_name: str) -> bool:
        """
        Check if a model class exists in the current app.
        """
        return self.models_module is not None and hasattr(self.models_module, model_name)
    
    def get_model(self, model_name: str):
        """
        Return the given model from the current app.
        """
        if not self.has_model(model_name):
            return None
        return getattr(self.models_module, model_name)
    
    def get_model_applink(self, model_name: str):
        """
        Return the application link for the given model name. e.g : User => "users.User"
        """
        return "%s.%s" % (self.name, model_name) if self.has_model(model_name) else None


    def ready(self):
        """
        Override this method in subclasses to run code when Oya starts.
        """
        


    def import_endpoints(self):
        if module_has_submodule(self.module, ENDPOINTS_MODULE_NAME):
            endpoints_module_name = "%s.%s" % (self.name, ENDPOINTS_MODULE_NAME)
            self.endpoints = import_module(endpoints_module_name)



    def get_endpoints(self):
        """
        Return a list of endpoints for this app.
        """
        endpoints = getattr(self.endpoints, '__handlers__', [])
        if isinstance(endpoints, dict):
            endpoints = list(endpoints.values())
        elif isinstance(endpoints, list) or isinstance(endpoints, tuple):
            pass
        else:
            raise ImproperlyConfigured("Endpoints must be a list, dict or tuple")
        return endpoints
    
    def get_migrations_path(self) -> str:
        return os.path.join(self.path, settings.APP_MIGRATIONS_FOLDER)