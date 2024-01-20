"""
Global Oya exception and warning classes.
"""


class OyaException(Exception):
    pass


class ImproperlyConfigured(OyaException):
    pass


class LoadMiddlewareError(OyaException):
    pass


class AppRegistryNotReady(OyaException):
    pass

class SuspiciousFileOperation(OyaException):
    pass


class NotSupportError(Exception):
    """
    raise when features not support
    """


class DowngradeError(Exception):
    """
    raise when downgrade error
    """
