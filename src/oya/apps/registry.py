import functools
import sys, os
from typing import Iterable
import warnings
from collections import Counter, defaultdict

from oya.core.exceptions import ImproperlyConfigured
from oya.conf import settings
from .config import AppConfig


class Apps:
    """
    A registry that stores the configuration of installed applications.

    It also keeps track of models, e.g. to provide reverse relations.
    """

    def __init__(self, installed_apps:set[str | AppConfig]=()):
        """
        Args:
        installed_apps (Optional[Iterable[str]]): is set to None when creating the main registry
                because it cannot be populated at that point. Other registries must
                provide a list of installed apps and are populated immediately.
        """
        if installed_apps is None and hasattr(sys.modules[__name__], "apps"):
            raise RuntimeError("You must supply an installed_apps argument.")

        
        self.all_models = defaultdict(dict[str, AppConfig])
        self.tortoise_apps_config : dict[str, dict[str, str | list[str]]] = {}
        self.tortoise_prepared = False

        # Mapping of labels to AppConfig instances for installed apps.
        self.app_configs : dict[str, AppConfig] = {}

        # Stack of app_configs. Used to store the current state in
        # set_available_apps and set_installed_apps.
        self.stored_app_configs = []

        # Whether the registry is populated.
        self.apps_ready = self.models_ready = self.ready = False

        # Maps ("app_label", "modelname") tuples to lists of functions to be
        # called when the corresponding model is ready. Used by this class's
        # `lazy_model_operation()` and `do_pending_operations()` methods.
        self._pending_operations = defaultdict(list)

        # Populate apps and models, unless it's the main registry.
        if installed_apps is not None:
            self.populate(installed_apps)

        

    def populate(self, installed_apps=None):
        """
        Load application configurations and models.

        Import each application module and then each model module.

        It is thread-safe and idempotent, but not reentrant.
        """

        # Phase 1: initialize app configs and import app modules.
        for entry in installed_apps:
            if isinstance(entry, AppConfig):
                app_config = entry
            else:
                app_config = AppConfig.create(entry)
            if app_config.label in self.app_configs:
                raise ImproperlyConfigured(
                    "Application labels aren't unique, "
                    "duplicates: %s" % app_config.label
                )
            
            self.stored_app_configs.append(app_config)
            self.app_configs[app_config.label] = app_config
            app_config.apps = self

        # Check for duplicate app names.
        counts = Counter(
            app_config.name for app_config in self.app_configs.values()
        )
        duplicates = [name for name, count in counts.most_common() if count > 1]
        if duplicates:
            raise ImproperlyConfigured(
                "Application names aren't unique, "
                "duplicates: %s" % ", ".join(duplicates)
            )

        self.apps_ready = True

        # Phase 2: import models modules.
        for app_config in self.app_configs.values():
            app_config.import_models()
            app_config.import_endpoints()

        self.clear_cache()

        self.models_ready = True # will be removed later if necessary

        # Phase 3: run ready() methods of app configs.
        for app_config in self.get_app_configs():
            app_config.ready()

        init = os.environ.get('INITIALISER', None)

        if not init:
            self.prepare_toirtoise_config()


    def get_app_configs(self) -> Iterable[AppConfig]:
        """Import applications and return an iterable of app configs."""
        return self.app_configs.values()
    

    def prepare_toirtoise_config(self):
        for app_config in self.get_app_configs():
            self.tortoise_apps_config[app_config.label] = {
                'models' : [app_config.get_models()], # will support many models in the future, like is designed by toirtoise
                "default_connection": "default",       # Connection too will be added on the App Config
            }

        self.tortoise_prepared = True
        settings.TORTOISE_ORM['apps'].update(self.tortoise_apps_config)


    def get_toirtoise_app_config(self):
        if not self.tortoise_prepared:
            self.prepare_toirtoise_config()
        return self.tortoise_apps_config

    def get_app_config(self, app_label) -> AppConfig:
        """
        Import applications and returns an app config for the given label.

        Raise LookupError if no application exists with this label.
        """
        try:
            return self.app_configs[app_label]
        except KeyError as exc:
            message = "No installed app with label '%s'." % app_label
            for app_config in self.get_app_configs():
                if app_config.name == app_label:
                    message += " Did you mean '%s'?" % app_config.label
                    break
            raise LookupError(message) from exc

    
    @functools.cache
    def get_models(self):
        """
        Return a list of all installed models.

        By default, the following models aren't included:

        - auto-created models for many-to-many relations without
          an explicit intermediate table,
        - models that have been swapped out.

        Set the corresponding keyword argument to True to include such models.
        """

        result = []
        for app_config in self.app_configs.values():
            result.extend(app_config.get_models())
        return result

    def get_model(self, app_label, model_name=None, require_ready=True):
        """
        Return the model matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        model exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """

        if model_name is None:
            app_label, model_name = app_label.split(".")

        app_config = self.get_app_config(app_label)

        if not require_ready and app_config.models is None:
            app_config.import_models()

        return app_config.get_model(model_name)

    def register_model(self, app_label, model):
        # Since this method is called when models are imported, it cannot
        # perform imports because of the risk of import loops. It mustn't
        # call get_app_config().
        model_name = model._meta.model_name     # pylint: disable=W0212
        app_models = self.all_models[app_label]
        if model_name in app_models:
            if (
                model.__name__ == app_models[model_name].__name__
                and model.__module__ == app_models[model_name].__module__
            ):
                warnings.warn(
                    "Model '%s.%s' was already registered. Reloading models is not "
                    "advised as it can lead to inconsistencies, most notably with "
                    "related models." % (app_label, model_name),
                    RuntimeWarning,
                    stacklevel=2,
                )
            else:
                raise RuntimeError(
                    "Conflicting '%s' models in application '%s': %s and %s."
                    % (model_name, app_label, app_models[model_name], model)
                )
        app_models[model_name] = model
        self.clear_cache()

    def is_installed(self, app_name:str):
        """
        Check whether an application with this name exists in the registry.

        app_name is the full name of the app.
        """
        return any(ac.name == app_name for ac in self.app_configs.values())

    def get_containing_app_config(self, object_name):
        """
        Look for an app config containing a given object.

        object_name is the dotted Python path to the object.

        Return the app config for the inner application in case of nesting.
        Return None if the object isn't in any registered app config.
        """
        candidates = []
        for app_config in self.app_configs.values():
            if object_name.startswith(app_config.name):
                subpath = object_name.removeprefix(app_config.name)
                if subpath == "" or subpath[0] == ".":
                    candidates.append(app_config)
        if candidates:
            return sorted(candidates, key=lambda ac: -len(ac.name))[0]

    def get_registered_model(self, app_label, model_name):
        """
        Similar to get_model(), but doesn't require that an app exists with
        the given app_label.

        It's safe to call this method at import time, even while the registry
        is being populated.
        """
        model = self.all_models[app_label].get(model_name.lower())
        if model is None:
            raise LookupError("Model '%s.%s' not registered." % (app_label, model_name))
        return model


    def clear_cache(self):
        """
        Clear all internal caches, for methods that alter the app registry.

        This is mostly used in tests.
        """
        # the relation tree and the fields cache.
        # pylint: disable=no-member
        self.get_models.cache_clear()


    def get_model_app(self, model_name : str):
        """
        Return the application link for the given model name. e.g : User => "users.User"
        """
        applink = None
        for app_config in self.app_configs.values():
            applink = app_config.get_model_applink(model_name)
            if applink:
                break
        if applink is None:
            raise LookupError(f"Model {model_name} not found in any app")
        return applink


apps = Apps(installed_apps=settings.INSTALLED_APPS)
