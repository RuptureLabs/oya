import collections
import os
import sys
import time
from contextlib import contextmanager
from itertools import chain
from types import SimpleNamespace
from unittest import TestCase


from oya.conf import settings


try:
    import jinja2
except ImportError:
    jinja2 = None


__all__ = (
    "Approximate",
    "ContextList",
    "isolate_lru_cache",
    "get_runner",
    "CaptureQueriesContext",
    "ignore_warnings",
    "isolate_apps",
    "modify_settings",
    "override_settings",
    "override_system_checks",
    "tag",
    "requires_tz_support",
    "setup_databases",
    "setup_test_environment",
    "teardown_test_environment",
)

TZ_SUPPORT = hasattr(time, "tzset")


class Approximate:
    def __init__(self, val, places=7):
        self.val = val
        self.places = places

    def __repr__(self):
        return repr(self.val)

    def __eq__(self, other):
        return self.val == other or round(abs(self.val - other), self.places) == 0


class ContextList(list):
    """
    A wrapper that provides direct key access to context items contained
    in a list of context objects.
    """

    def __getitem__(self, key):
        if isinstance(key, str):
            for subcontext in self:
                if key in subcontext:
                    return subcontext[key]
            raise KeyError(key)
        else:
            return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        return True

    def keys(self):
        """
        Flattened keys of subcontexts.
        """
        return set(chain.from_iterable(d for subcontext in self for d in subcontext))



class _TestState:
    pass


def setup_test_environment(debug=None):
    """
    Perform global pre-test setup, such as installing the instrumented template
    renderer and setting the email backend to the locmem email backend.
    """
    if hasattr(_TestState, "saved_data"):
        # Executing this function twice would overwrite the saved values.
        raise RuntimeError(
            "setup_test_environment() was already called and can't be called "
            "again without first calling teardown_test_environment()."
        )

    if debug is None:
        debug = settings.DEBUG

    saved_data = SimpleNamespace()
    _TestState.saved_data = saved_data

    saved_data.allowed_hosts = settings.ALLOWED_HOSTS
    # Add the default host of the test client.
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "testserver"]

    saved_data.debug = settings.DEBUG
    settings.DEBUG = debug


def teardown_test_environment():
    """
    Perform any global post-test teardown, such as restoring the original
    template renderer and restoring the email sending functions.
    """
    saved_data = _TestState.saved_data

    settings.ALLOWED_HOSTS = saved_data.allowed_hosts
    settings.DEBUG = saved_data.debug
    

    del _TestState.saved_data


def iter_test_cases(tests):
    """
    Return an iterator over a test suite's unittest.TestCase objects.

    The tests argument can also be an iterable of TestCase objects.
    """
    for test in tests:
        if isinstance(test, str):
            # Prevent an unfriendly RecursionError that can happen with
            # strings.
            raise TypeError(
                f"Test {test!r} must be a test case or test suite not string "
                f"(was found in {tests!r})."
            )
        if isinstance(test, TestCase):
            yield test
        else:
            # Otherwise, assume it is a test suite.
            yield from iter_test_cases(test)



def get_runner(settings, test_runner_class=None):
    test_runner_class = test_runner_class or settings.TEST_RUNNER
    test_path = test_runner_class.split(".")
    # Allow for relative paths
    if len(test_path) > 1:
        test_module_name = ".".join(test_path[:-1])
    else:
        test_module_name = "."
    test_module = __import__(test_module_name, {}, {}, test_path[-1])
    return getattr(test_module, test_path[-1])




class TimeKeeper:
    def __init__(self):
        self.records = collections.defaultdict(list)

    @contextmanager
    def timed(self, name):
        self.records[name]
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter() - start_time
            self.records[name].append(end_time)

    def print_results(self):
        for name, end_times in self.records.items():
            for record_time in end_times:
                record = "%s took %.3fs" % (name, record_time)
                sys.stderr.write(record + os.linesep)


class NullTimeKeeper:
    @contextmanager
    def timed(self, name):
        yield

    def print_results(self):
        pass


