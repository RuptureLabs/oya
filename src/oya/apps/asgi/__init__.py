"""
Expose the Application ASGI Factory

"""

from typing import Any, List, Sequence, Union, Mapping
from collections.abc import Callable
from pathlib import Path
from litestar.datastructures.response_header import ResponseHeader
from litestar.logging import LoggingConfig
from litestar.static_files.config import StaticFilesConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.config.response_cache import ResponseCacheConfig
from litestar.config.compression import CompressionConfig
from litestar.stores.registry import StoreRegistry
from litestar.template.config import TemplateConfig
from litestar.datastructures import State, ETag, CacheControlHeader
from litestar.dto import AbstractDTO
from litestar.types import (
    ParametersMap,
    TypeEncodersMap,
    TypeDecodersSequence,)
from litestar.events import BaseEventEmitterBackend
from litestar.openapi import OpenAPIConfig
from litestar.openapi.spec import SecurityRequirement
from litestar.connection import WebSocket, Request
from litestar import Litestar


from oya.core.exceptions import ImproperlyConfigured
from oya.core.management.utils import close_tortoise, init_tortoise_auto
from oya.core.serialization import TortoiseSerializationPlugin
from oya.conf import settings
from oya.apps import apps
from oya.middleware.builtins import (
    get_allowed_hosts_config,
    get_compression_config,
    get_cors_config,
    get_csrf_config,
    get_response_cache_config
)

from .utils import get_template_config, get_static_file_config, get_middleware



__all__ = ("Application",)




class Application:
    """
    ASGI Application Factory

    Call Application.get_asgi_application() to get the litestar
    """

    asgi_application : "Litestar" = None
    plugins: List[Any] = [TortoiseSerializationPlugin()]
    middlewares: List[Any] = []
    dependencies: dict[str, Any] = {}

    on_app_init: List[Callable[[Any], Any]] = []
    on_startup: List[Callable[[Any], Any]] = [init_tortoise_auto]   # default
    on_shutdown: List[Callable[[Any], Any]] = [close_tortoise]      # default

    route_handlers: List[Callable[[Any], Any]] = []

    state: dict[str, Any] = {}
    stores: Any = None

    before_send: List[Callable[[Any], Any]] = []
    after_exceptions: List[Callable[[Any], Any]] = []
    exception_hanlders: dict[str, Callable[[Any], Any]] = {}
    listeners : List[Callable[[Any], Any]] = []

    pdb_exceeption: bool = False

    before_request: Callable[[Any], Any] | None = None
    after_request: Callable[[Any], Any] | None = None
    after_response: Callable[[Any], Any] | None = None

    allowed_hosts: list[str] | None = get_allowed_hosts_config()

    logging_config:LoggingConfig = LoggingConfig()
    static_file_config: List[Any] = get_static_file_config()
    template_config: TemplateConfig | None = get_template_config()

    cache_control: CacheControlHeader | None = None
    compression_config: CompressionConfig| None = get_compression_config()
    cors_config: CORSConfig| None = get_cors_config()
    csrf_config: CSRFConfig | None = get_csrf_config()
    openapi_config: OpenAPIConfig | None = None
    dto: AbstractDTO | None = None
    return_dto: AbstractDTO | None = None
    etag: ETag | None = None
    tags: List[str] | None = None
    event_emitter_backend: BaseEventEmitterBackend | None = None
    guards: List[Any] = []

    parameters: type[ParametersMap] | None = None
    opt: dict[str, Any] = {}

    type_encoders: Union[TypeEncodersMap, None] = None
    type_decoders: Union[TypeDecodersSequence, None] = None
    websocket_class: type[WebSocket] | None = None
    multipart_form_part_limit: int = 1000

    request_class: type[Request] | None = None
    response_class: Any = None
    response_cookies: Any = None
    response_headers: Sequence[ResponseHeader] | None = None
    response_cache_config: ResponseCacheConfig | None = get_response_cache_config()

    security: list[SecurityRequirement] | None = None
    signature_namespace: dict[str, Any] | None = None
    signature_types: list[Any] | None = None

    api_version: str | None = "1.0.0"
    api_title:str | None = None

    _middlewares_loaded: bool = False


    @classmethod
    def get_asgi_application(cls, override: bool = False) -> Litestar:
        """Get ASGI application.

        Args:
            override (bool, optional): Whether to override default config. Defaults to False.
        Returns:
            Litestar: ASGI application
        """

        if cls.asgi_application and not override:
            return cls.asgi_application


        app_config : dict[str, Any] = {}
        app_config['debug'] = settings.DEBUG

        if cls.plugins:
            app_config["plugins"] = cls.plugins

        cls._load_middlewares()

        if cls.middlewares:
            app_config["middleware"] = cls.middlewares

        if cls.dependencies:
            app_config["dependencies"] = cls.dependencies

        if cls.on_app_init:
            app_config["on_app_init"] = cls.on_app_init 

        if cls.on_startup:
            app_config["on_startup"] = cls.on_startup

        if cls.on_shutdown:
            app_config["on_shutdown"] = cls.on_shutdown


        if cls.state:
            if isinstance(cls.state, dict):
                app_config["state"] = State(cls.state)
            elif isinstance(cls.state, State):
                app_config["state"] = cls.state
            else:
                raise ImproperlyConfigured("Application State must be a dict or State.")

        if cls.listeners:
            app_config["listeners"] = cls.listeners


        if cls.stores:
            if isinstance(cls.stores, StoreRegistry):
                app_config["stores"] = cls.stores
            else:
                raise ImproperlyConfigured("Application stores must be a StoreRegistry.")

        if cls.before_send:
            app_config["before_send"] = cls.before_send

        if cls.after_exceptions:
            app_config["after_exception"] = cls.after_exceptions

        if cls.exception_hanlders:
            app_config["exception_handlers"] = cls.exception_hanlders

        if cls.before_request:
            app_config["before_request"] = cls.before_request

        if cls.after_request:
            app_config["after_request"] = cls.after_request

        if cls.after_response:
            app_config["after_response"] = cls.after_response

        if cls.allowed_hosts:
            app_config["allowed_hosts"] = cls.allowed_hosts

        if cls.pdb_exceeption:
            app_config["pdb_on_exception"] = cls.pdb_exceeption

        if cls.logging_config:
            app_config["logging_config"] = cls.logging_config

        if cls.template_config:
            app_config["template_config"] = cls.template_config

        if cls.static_file_config:
            app_config["static_files_config"] = cls.static_file_config

        if cls.cache_control:
            app_config["cache_control"] = cls.cache_control

        if cls.compression_config:
            app_config["compression_config"] = cls.compression_config

        if cls.cors_config:
            app_config["cors_config"] = cls.cors_config

        if cls.csrf_config:
            app_config["csrf_config"] = cls.csrf_config

        if cls.openapi_config:
            app_config["openapi_config"] = cls.openapi_config

        if cls.dto:
            app_config["dto"] = cls.dto

        if cls.return_dto:
            app_config["return_dto"] = cls.return_dto

        if cls.etag:
            app_config["etag"] = cls.etag

        if cls.tags:
            app_config["tags"] = cls.tags

        if cls.event_emitter_backend:
            app_config["event_emitter_backend"] = cls.event_emitter_backend

        if cls.parameters:
            app_config["parameters"] = cls.parameters

        if cls.opt:
            app_config["opt"] = cls.opt

        if cls.guards:
            app_config["guards"] = cls.guards

        if cls.type_encoders:
            app_config["type_encoders"] = cls.type_encoders

        if cls.type_decoders:
            app_config["type_decoders"] = cls.type_decoders

        if cls.websocket_class:
            app_config["websocket_class"] = cls.websocket_class

        if cls.multipart_form_part_limit:
            app_config["multipart_form_part_limit"] = cls.multipart_form_part_limit

        if cls.request_class:
            app_config["request_class"] = cls.request_class
        
        if cls.response_class:
            app_config["response_class"] = cls.response_class

        if cls.response_cookies:
            app_config["response_cookies"] = cls.response_cookies

        if cls.response_headers:
            app_config["response_headers"] = cls.response_headers

        if cls.response_cache_config:
            app_config["response_cache_config"] = cls.response_cache_config

        if cls.security:
            app_config["security"] = cls.security

        if cls.signature_namespace:
            app_config["signature_namespace"] = cls.signature_namespace

        if cls.signature_types:
            app_config["signature_types"] = cls.signature_types


        routes = cls.route_handlers
        for app in apps.app_configs.values():
            routes.extend(app.get_endpoints())

        app_config["route_handlers"] = set(routes) # unique


        cls.asgi_application = Litestar(**app_config)

        return cls.asgi_application


    @classmethod
    def _extend_array(cls, to_extend: List, value: Union[List, Callable[[Any], Any], str]):
        """
        Extend the given array with the given value

        Args:
            to_extend : List 
            value : Union[List, Callable, str]
        """
        if isinstance(value, list):
            to_extend.extend(value)

        if isinstance(value, (str, Callable)):
            to_extend.extend([value])
    

    @classmethod
    def set_config(cls, attr_name: str, value: Any, is_dict=False, is_list=False):
        """
        Allow user to set up config attributes
        
        Args:
            attr_name: str
            value: Any
            is_dict: bool = False
            is_list: bool = False
        """
        if is_dict and is_list:
            raise ValueError('Application.set_config >> is_dict and is_list can\'t be True at same time.')

        if hasattr(cls, attr_name):
            if is_dict:
                _d: dict = getattr(cls, attr_name)
                if not isinstance(value, dict) or not isinstance(_d, dict):
                    raise ValueError(f"is_dict is True, '{attr_name}' value must be a dict")

                _d.update(value)

            elif is_list:
                _l: List = getattr(cls, attr_name)
                if not isinstance(value, list) or not isinstance(_d, list):
                    raise ValueError(f"is_dict is True, '{attr_name}' value must be a dict")

                _l.extend(value)

            else: setattr(cls, attr_name, value)

        else:
            raise AttributeError(f"Application has not attribute '{attr_name}'")




    @classmethod
    def _load_middlewares(cls):
        if cls._middlewares_loaded: # middlewares are loaded one time only to avoid redundancy
            return

        if cls.middlewares is None:
            cls.middlewares = []

        if not isinstance(cls.middlewares, (list, tuple)):
            raise ImproperlyConfigured("Application.middlewares must a list or tuple")

        settings_middlewares = get_middleware()
        if hasattr(settings, 'MIDDLEWARE_FROM_FACTORY_BEFORE') \
            and settings.MIDDLEWARE_FROM_FACTORY_BEFORE:
            cls.middlewares.extend(settings_middlewares)
        else:
            cls.middlewares = settings_middlewares + cls.middlewares

        cls._middlewares_loaded = True
