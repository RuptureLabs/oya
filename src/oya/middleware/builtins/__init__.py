from typing import Any, Dict, Type
from functools import cache

from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.config.allowed_hosts import AllowedHostsConfig
from litestar.config.compression import CompressionConfig
from litestar.config.response_cache import ResponseCacheConfig


from oya.conf import settings
from oya.core.exceptions import ImproperlyConfigured


@cache
def get_cors_config() -> Type[CORSConfig] | None :
    """
    Load CORS Config from settings

    Returns:
        CORSConfig | None
    """
    _conf: Dict[str, Any] = {}

    if hasattr(settings, 'ALLOW_ORIGINS'):
        _conf['allow_origins'] = settings.ALLOW_ORIGINS

    if hasattr(settings, 'ALLOW_METHODS'):
        _conf['allow_methods'] = settings.ALLOW_METHODS

    if hasattr(settings, 'ALLOW_HEADERS'):
        _conf['allow_headers'] = settings.ALLOW_HEADERS

    if hasattr(settings, 'ALLOW_CREDENTIALS'):
        _conf['allow_credentials'] = settings.ALLOW_CREDENTIALS

    if hasattr(settings, 'ALLOW_ORIGIN_REGEX'):
        _conf['allow_origin_regex'] = settings.ALLOW_ORIGIN_REGEX

    if hasattr(settings, 'EXPOSE_HEADERS'):
        _conf['expose_headers'] = settings.EXPOSE_HEADERS

    if hasattr(settings, 'CORS_MAX_AGE'):
        _conf['max_age'] = settings.CORS_MAX_AGE

    if _conf:
        return CORSConfig(**_conf)

    return None


@cache
def get_csrf_config() -> Type[CSRFConfig] | None:
    """
    Load CSRF Config from settings

    Returns:
        CSRFConfig | None
    """
    _conf: Dict[str, Any] = {}

    if hasattr(settings, 'CSRF_COOKIE_NAME'):
        _conf['cookie_name'] = settings.CSRF_COOKIE_NAME

    if hasattr(settings, 'CSRF_COOKIE_PATH'):
        _conf['cookie_path'] = settings.CSRF_COOKIE_PATH

    if hasattr(settings, 'CSRF_HEADER_NAME'):
        _conf['header_name'] = settings.CSRF_HEADER_NAME

    if hasattr(settings, 'CSRF_COOKIE_SECURE'):
        _conf['cookie_secure'] = settings.CSRF_COOKIE_SECURE

    if hasattr(settings, 'CSRF_COOKIE_HTTPONLY'):
        _conf['cookie_httponly'] = settings.CSRF_COOKIE_HTTPONLY

    if hasattr(settings, 'CSRF_COOKIE_SAMESITE'):
        _conf['cookie_samesite'] = settings.CSRF_COOKIE_SAMESITE

    if hasattr(settings, 'CSRF_COOKIE_DOMAIN'):
        _conf['cookie_domain'] = settings.CSRF_COOKIE_DOMAIN

    if hasattr(settings, 'CSRF_SAFE_METHODS'):
        _conf['safe_methods'] = settings.CSRF_SAFE_METHODS

    if hasattr(settings, 'CSRF_EXCLUDE'):
        _conf['exclude'] = settings.CSRF_EXCLUDE

    if hasattr(settings, 'EXCLUDE_FROM_CSRF_KEY'):
        _conf['exclude_from_csrf_key'] = settings.EXCLUDE_FROM_CSRF_KEY

    if _conf:
        if hasattr(settings, 'SECRET'):
            _conf['secret'] = settings.SECRET
        else:
            raise ImproperlyConfigured("SECRET key must be defined in settings file")

        return CSRFConfig(**_conf)

    return None


@cache
def get_allowed_hosts_config() -> Type[AllowedHostsConfig] | None:
    """
    Load Allowed hosts config from settings

    Returns:
        AllowedHostsConfig | None
    """
    _conf: Dict[str, Any] = {}
    
    if hasattr(settings, 'ALLOWED_HOSTS'):
        _conf['allowed_hosts'] = settings.ALLOWED_HOSTS
    else:
        return None

    if hasattr(settings, 'EXCLUDE_HOSTS'):
        _conf['exclude'] = settings.EXCLUDE_HOSTS

    if hasattr(settings, 'ALLOWED_HOSTS_EXCLUDE_OPT_KEY'):
        _conf['exclude_opt_key'] = settings.ALLOWED_HOSTS_EXCLUDE_OPT_KEY

    if hasattr(settings, 'ALLOWED_HOSTS_SCOPES'):
        _conf['scopes'] = settings.ALLOWED_HOSTS_SCOPES

    if hasattr(settings, 'WWW_REDIRECT'):
        _conf['www_redirect'] = settings.WWW_REDIRECT

    return AllowedHostsConfig(**_conf)

@cache
def get_compression_config() -> Type[CompressionConfig] | None:
    """
    Load Conpression config from settings
    """
    _conf: Dict[str, Any] = {}

    if hasattr(settings, 'COMPRESSION_BACKEND'):
        _conf['backend'] = settings.COMPRESSION_BACKEND

    if hasattr(settings, 'COMPRESSION_MINIMUM_SIZE'):
        _conf['minimum_size'] = settings.COMPRESSION_MINIMUM_SIZE

    if hasattr(settings, 'GZIP_COMPRESS_LEVEL'):
        _conf['gzip_compress_level'] = settings.GZIP_COMPRESS_LEVEL

    if hasattr(settings, 'BROTLI_QUALITY'):
        _conf['brotli_quality'] = settings.BROTLI_QUALITY

    if hasattr(settings, 'BROTLI_MODE'):
        _conf['brotli_mode'] = settings.BROTLI_MODE

    if hasattr(settings, 'BROTLI_LGWIN'):
        _conf['brotli_lgwin'] = settings.BROTLI_LGWIN

    if hasattr(settings, ''):
        _conf['brotli_lgblock'] = settings.BROTLI_LGBLOCK

    if hasattr(settings, 'COMPRESSION_MIDDLEWARE_CLASS'):
        _conf['middleware_class'] = settings.COMPRESSION_MIDDLEWARE_CLASS

    if hasattr(settings, 'COMPRESSION_EXCLUDE'):
        _conf['exclude'] = settings.COMPRESSION_EXCLUDE

    if hasattr(settings, 'COMPRESSION_EXCLUDE_OPT_KEY'):
        _conf['exclude_opt_key'] = settings.COMPRESSION_EXCLUDE_OPT_KEY

    if _conf:
        return CompressionConfig(**_conf)
    else: return None


@cache
def get_response_cache_config() -> Type[ResponseCacheConfig] | None:
    """
    Load Response Cache Middleware config from settings

    Returns:
        ResponseCacheConfig | None
    """
    _conf: Dict[str, Any] = {}

    if hasattr(settings, 'RESPONSE_CACHE_DEFAULT_EXPIRATION'):
        _conf['default_expiration'] = settings.RESPONSE_CACHE_DEFAULT_EXPIRATION

    if hasattr(settings, 'RESPONSE_CACHE_STORE_NAME'):
        _conf['store'] = settings.RESPONSE_CACHE_STORE_NAME

    if _conf:
        return ResponseCacheConfig(**_conf)

    return None
