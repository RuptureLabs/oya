import argparse
import ctypes
import faulthandler
import hashlib
import io
import logging
import multiprocessing
import os
import pickle
import random
import sys
import textwrap
import unittest
from contextlib import contextmanager
from importlib import import_module
import pdb


from oya.core.management import call_command
from oya.tests import SimpleTestCase, TestCase
from oya.tests.utils import NullTimeKeeper, TimeKeeper, iter_test_cases
from oya.tests.utils import setup_test_environment
from oya.tests.utils import teardown_test_environment



tblib = None


class PDBDebugResult(unittest.TextTestResult):
    """
    Custom result class that triggers a PDB session when an error or failure
    occurs.
    """

    def addError(self, test, err):
        super().addError(test, err)
        self.debug(err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.debug(err)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.debug(err)
        super().addSubTest(test, subtest, err)

    def debug(self, error):
        self._restoreStdout()
        self.buffer = False
        exc_type, exc_value, traceback = error
        print("\nOpening PDB: %r" % exc_value)
        pdb.post_mortem(traceback)


class DummyList:
    """
    Dummy list class for faking storage of results in unittest.TestResult.
    """

    __slots__ = ()

    def append(self, item):
        pass


class RemoteTestResult(unittest.TestResult):
    """
    Extend unittest.TestResult to record events in the child processes so they
    can be replayed in the parent process. Events include things like which
    tests succeeded or failed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fake storage of results to reduce memory usage. These are used by the
        # unittest default methods, but here 'events' is used instead.
        dummy_list = DummyList()
        self.failures = dummy_list
        self.errors = dummy_list
        self.skipped = dummy_list
        self.expectedFailures = dummy_list
        self.unexpectedSuccesses = dummy_list

        if tblib is not None:
            tblib.pickling_support.install()
        self.events = []

    def __getstate__(self):
        # Make this class picklable by removing the file-like buffer
        # attributes. This is possible since they aren't used after unpickling
        # after being sent to ParallelTestSuite.
        state = self.__dict__.copy()
        state.pop("_stdout_buffer", None)
        state.pop("_stderr_buffer", None)
        state.pop("_original_stdout", None)
        state.pop("_original_stderr", None)
        return state

    @property
    def test_index(self):
        return self.testsRun - 1

    def _confirm_picklable(self, obj):
        """
        Confirm that obj can be pickled and unpickled as multiprocessing will
        need to pickle the exception in the child process and unpickle it in
        the parent process. Let the exception rise, if not.
        """
        pickle.loads(pickle.dumps(obj))

    def _print_unpicklable_subtest(self, test, subtest, pickle_exc):
        print(
            """
Subtest failed:

    test: {}
 subtest: {}

Unfortunately, the subtest that failed cannot be pickled, so the parallel
test runner cannot handle it cleanly. Here is the pickling error:

> {}

You should re-run this test with --parallel=1 to reproduce the failure
with a cleaner failure message.
""".format(
                test, subtest, pickle_exc
            )
        )

    def check_picklable(self, test, err):
        # Ensure that sys.exc_info() tuples are picklable. This displays a
        # clear multiprocessing.pool.RemoteTraceback generated in the child
        # process instead of a multiprocessing.pool.MaybeEncodingError, making
        # the root cause easier to figure out for users who aren't familiar
        # with the multiprocessing module. Since we're in a forked process,
        # our best chance to communicate with them is to print to stdout.
        try:
            self._confirm_picklable(err)
        except Exception as exc:
            original_exc_txt = repr(err[1])
            original_exc_txt = textwrap.fill(
                original_exc_txt, 75, initial_indent="    ", subsequent_indent="    "
            )
            pickle_exc_txt = repr(exc)
            pickle_exc_txt = textwrap.fill(
                pickle_exc_txt, 75, initial_indent="    ", subsequent_indent="    "
            )
            if tblib is None:
                print(
                    """

{} failed:

{}

Unfortunately, tracebacks cannot be pickled, making it impossible for the
parallel test runner to handle this exception cleanly.

In order to see the traceback, you should install tblib:

    python -m pip install tblib
""".format(
                        test, original_exc_txt
                    )
                )
            else:
                print(
                    """

{} failed:

{}

Unfortunately, the exception it raised cannot be pickled, making it impossible
for the parallel test runner to handle it cleanly.

Here's the error encountered while trying to pickle the exception:

{}

You should re-run this test with the --parallel=1 option to reproduce the
failure and get a correct traceback.
""".format(
                        test, original_exc_txt, pickle_exc_txt
                    )
                )
            raise

    def check_subtest_picklable(self, test, subtest):
        try:
            self._confirm_picklable(subtest)
        except Exception as exc:
            self._print_unpicklable_subtest(test, subtest, exc)
            raise

    def startTestRun(self):
        super().startTestRun()
        self.events.append(("startTestRun",))

    def stopTestRun(self):
        super().stopTestRun()
        self.events.append(("stopTestRun",))

    def startTest(self, test):
        super().startTest(test)
        self.events.append(("startTest", self.test_index))

    def stopTest(self, test):
        super().stopTest(test)
        self.events.append(("stopTest", self.test_index))

    def addDuration(self, test, elapsed):
        super().addDuration(test, elapsed)
        self.events.append(("addDuration", self.test_index, elapsed))

    def addError(self, test, err):
        self.check_picklable(test, err)
        self.events.append(("addError", self.test_index, err))
        super().addError(test, err)

    def addFailure(self, test, err):
        self.check_picklable(test, err)
        self.events.append(("addFailure", self.test_index, err))
        super().addFailure(test, err)

    def addSubTest(self, test, subtest, err):
        # Follow Python's implementation of unittest.TestResult.addSubTest() by
        # not doing anything when a subtest is successful.
        if err is not None:
            # Call check_picklable() before check_subtest_picklable() since
            # check_picklable() performs the tblib check.
            self.check_picklable(test, err)
            self.check_subtest_picklable(test, subtest)
            self.events.append(("addSubTest", self.test_index, subtest, err))
        super().addSubTest(test, subtest, err)

    def addSuccess(self, test):
        self.events.append(("addSuccess", self.test_index))
        super().addSuccess(test)

    def addSkip(self, test, reason):
        self.events.append(("addSkip", self.test_index, reason))
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        # If tblib isn't installed, pickling the traceback will always fail.
        # However we don't want tblib to be required for running the tests
        # when they pass or fail as expected. Drop the traceback when an
        # expected failure occurs.
        if tblib is None:
            err = err[0], err[1], None
        self.check_picklable(test, err)
        self.events.append(("addExpectedFailure", self.test_index, err))
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.events.append(("addUnexpectedSuccess", self.test_index))
        super().addUnexpectedSuccess(test)

    def wasSuccessful(self):
        """Tells whether or not this result was a success."""
        failure_types = {"addError", "addFailure", "addSubTest", "addUnexpectedSuccess"}
        return all(e[0] not in failure_types for e in self.events)

    def _exc_info_to_string(self, err, test):
        # Make this method no-op. It only powers the default unittest behavior
        # for recording errors, but this class pickles errors into 'events'
        # instead.
        return ""


class RemoteTestRunner:
    """
    Run tests and record everything but don't display anything.

    The implementation matches the unpythonic coding style of unittest2.
    """

    resultclass = RemoteTestResult

    def __init__(self, failfast=False, resultclass=None, buffer=False):
        self.failfast = failfast
        self.buffer = buffer
        if resultclass is not None:
            self.resultclass = resultclass

    def run(self, test):
        result = self.resultclass()
        unittest.registerResult(result)
        result.failfast = self.failfast
        result.buffer = self.buffer
        test(result)
        return result


def get_max_test_processes():
    """
    The maximum number of test processes when using the --parallel option.
    """
    # The current implementation of the parallel test runner requires
    # multiprocessing to start subprocesses with fork() or spawn().
    if multiprocessing.get_start_method() not in {"fork", "spawn"}:
        return 1
    try:
        return int(os.environ["DJANGO_TEST_PROCESSES"])
    except KeyError:
        return multiprocessing.cpu_count()


def parallel_type(value):
    """Parse value passed to the --parallel option."""
    if value == "auto":
        return value
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not an integer or the string 'auto'"
        )


_worker_id = 0


def _init_worker(
    counter,
    initial_settings=None,
    serialized_contents=None,
    process_setup=None,
    process_setup_args=None,
    debug_mode=None,
    used_aliases=None,
):
    """
    Switch to databases dedicated to this worker.

    This helper lives at module-level because of the multiprocessing module's
    requirements.
    """

    global _worker_id

    with counter.get_lock():
        counter.value += 1
        _worker_id = counter.value

    start_method = multiprocessing.get_start_method()

    if start_method == "spawn":
        if process_setup and callable(process_setup):
            if process_setup_args is None:
                process_setup_args = ()
            process_setup(*process_setup_args)
        setup_test_environment(debug=debug_mode)


def _run_subsuite(args):
    """
    Run a suite of tests with a RemoteTestRunner and return a RemoteTestResult.

    This helper lives at module-level and its arguments are wrapped in a tuple
    because of the multiprocessing module's requirements.
    """
    runner_class, subsuite_index, subsuite, failfast, buffer = args
    runner = runner_class(failfast=failfast, buffer=buffer)
    result = runner.run(subsuite)
    return subsuite_index, result.events


def _process_setup_stub(*args):
    """Stub method to simplify run() implementation."""
    pass


class ParallelTestSuite(unittest.TestSuite):
    """
    Run a series of tests in parallel in several processes.

    While the unittest module's documentation implies that orchestrating the
    execution of tests is the responsibility of the test runner, in practice,
    it appears that TestRunner classes are more concerned with formatting and
    displaying test results.

    Since there are fewer use cases for customizing TestSuite than TestRunner,
    implementing parallelization at the level of the TestSuite improves
    interoperability with existing custom test runners. A single instance of a
    test runner can still collect results from all tests without being aware
    that they have been run in parallel.
    """

    # In case someone wants to modify these in a subclass.
    init_worker = _init_worker
    process_setup = _process_setup_stub
    process_setup_args = ()
    run_subsuite = _run_subsuite
    runner_class = RemoteTestRunner

    def __init__(
        self, subsuites, processes, failfast=False, debug_mode=False, buffer=False
    ):
        self.subsuites = subsuites
        self.processes = processes
        self.failfast = failfast
        self.debug_mode = debug_mode
        self.buffer = buffer
        self.initial_settings = None
        self.serialized_contents = None
        self.used_aliases = None
        super().__init__()

    def run(self, result):
        """
        Distribute TestCases across workers.

        Return an identifier of each TestCase with its result in order to use
        imap_unordered to show results as soon as they're available.

        To minimize pickling errors when getting results from workers:

        - pass back numeric indexes in self.subsuites instead of tests
        - make tracebacks picklable with tblib, if available

        Even with tblib, errors may still occur for dynamically created
        exception classes which cannot be unpickled.
        """
        self.initialize_suite()
        counter = multiprocessing.Value(ctypes.c_int, 0)
        pool = multiprocessing.Pool(
            processes=self.processes,
            initializer=self.init_worker.__func__,
            initargs=[
                counter,
                self.initial_settings,
                self.serialized_contents,
                self.process_setup.__func__,
                self.process_setup_args,
                self.debug_mode,
                self.used_aliases,
            ],
        )
        args = [
            (self.runner_class, index, subsuite, self.failfast, self.buffer)
            for index, subsuite in enumerate(self.subsuites)
        ]
        test_results = pool.imap_unordered(self.run_subsuite.__func__, args)

        while True:
            if result.shouldStop:
                pool.terminate()
                break

            try:
                subsuite_index, events = test_results.next(timeout=0.1)
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                pool.close()
                break

            tests = list(self.subsuites[subsuite_index])
            for event in events:
                event_name = event[0]
                handler = getattr(result, event_name, None)
                if handler is None:
                    continue
                test = tests[event[1]]
                args = event[2:]
                handler(test, *args)

        pool.join()

        return result

    def __iter__(self):
        return iter(self.subsuites)

    def initialize_suite(self):
        pass


class Shuffler:
    """
    This class implements shuffling with a special consistency property.
    Consistency means that, for a given seed and key function, if two sets of
    items are shuffled, the resulting order will agree on the intersection of
    the two sets. For example, if items are removed from an original set, the
    shuffled order for the new set will be the shuffled order of the original
    set restricted to the smaller set.
    """

    # This doesn't need to be cryptographically strong, so use what's fastest.
    hash_algorithm = "md5"

    @classmethod
    def _hash_text(cls, text):
        h = hashlib.new(cls.hash_algorithm, usedforsecurity=False)
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    def __init__(self, seed=None):
        if seed is None:
            # Limit seeds to 10 digits for simpler output.
            seed = random.randint(0, 10**10 - 1)
            seed_source = "generated"
        else:
            seed_source = "given"
        self.seed = seed
        self.seed_source = seed_source

    @property
    def seed_display(self):
        return f"{self.seed!r} ({self.seed_source})"

    def _hash_item(self, item, key):
        text = "{}{}".format(self.seed, key(item))
        return self._hash_text(text)

    def shuffle(self, items, key):
        """
        Return a new list of the items in a shuffled order.

        The `key` is a function that accepts an item in `items` and returns
        a string unique for that item that can be viewed as a string id. The
        order of the return value is deterministic. It depends on the seed
        and key function but not on the original order.
        """
        hashes = {}
        for item in items:
            hashed = self._hash_item(item, key)
            if hashed in hashes:
                msg = "item {!r} has same hash {!r} as item {!r}".format(
                    item,
                    hashed,
                    hashes[hashed],
                )
                raise RuntimeError(msg)
            hashes[hashed] = item
        return [hashes[hashed] for hashed in sorted(hashes)]


class DiscoverRunner:
    """A Django test runner that uses unittest2 test discovery."""

    test_suite = unittest.TestSuite
    parallel_test_suite = ParallelTestSuite
    test_runner = unittest.TextTestRunner
    test_loader = unittest.defaultTestLoader
    reorder_by = (TestCase, SimpleTestCase)

    def __init__(
        self,
        pattern=None,
        top_level=None,
        verbosity=1,
        interactive=True,
        failfast=False,
        keepdb=False,
        reverse=False,
        debug_mode=False,
        debug_sql=False,
        parallel=0,
        tags=None,
        exclude_tags=None,
        test_name_patterns=None,
        pdb=False,
        buffer=False,
        enable_faulthandler=True,
        timing=False,
        shuffle=False,
        logger=None,
        durations=None,
        **kwargs,
    ):
        self.pattern = pattern
        self.top_level = top_level
        self.verbosity = verbosity
        self.interactive = interactive
        self.failfast = failfast
        self.keepdb = keepdb
        self.reverse = reverse
        self.debug_mode = debug_mode
        self.debug_sql = debug_sql
        self.parallel = parallel
        self.tags = set(tags or [])
        self.exclude_tags = set(exclude_tags or [])
        if not faulthandler.is_enabled() and enable_faulthandler:
            try:
                faulthandler.enable(file=sys.stderr.fileno())
            except (AttributeError, io.UnsupportedOperation):
                faulthandler.enable(file=sys.__stderr__.fileno())
        self.pdb = pdb
        if self.pdb and self.parallel > 1:
            raise ValueError(
                "You cannot use --pdb with parallel tests; pass --parallel=1 to use it."
            )
        self.buffer = buffer
        self.test_name_patterns = None
        self.time_keeper = TimeKeeper() if timing else NullTimeKeeper()
        if test_name_patterns:
            # unittest does not export the _convert_select_pattern function
            # that converts command-line arguments to patterns.
            self.test_name_patterns = {
                pattern if "*" in pattern else "*%s*" % pattern
                for pattern in test_name_patterns
            }
        self.shuffle = shuffle
        self._shuffler = None
        self.logger = logger
        self.durations = durations

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument(
            "-t",
            "--top-level-directory",
            dest="top_level",
            help="Top level of project for unittest discovery.",
        )
        parser.add_argument(
            "-p",
            "--pattern",
            default="test*.py",
            help="The test matching pattern. Defaults to test*.py.",
        )
        
        parser.add_argument(
            "--debug-mode",
            action="store_true",
            help="Sets settings.DEBUG to True.",
        )
        
        parser.add_argument(
            "--pdb",
            action="store_true",
            default=False,
            help="Runs a debugger (pdb, or ipdb if installed) on error or failure.",
        )
        parser.add_argument(
            "-b",
            "--buffer",
            action="store_true",
            help="Discard output from passing tests.",
        )
        parser.add_argument(
            "--no-faulthandler",
            action="store_false",
            dest="enable_faulthandler",
            help="Disables the Python faulthandler module during tests.",
        )
        parser.add_argument(
            "--timing",
            action="store_true",
            help=("Output timings, including database set up and total run time."),
        )
        parser.add_argument(
            "-k",
            action="append",
            dest="test_name_patterns",
            help=(
                "Only run test methods and classes that match the pattern "
                "or substring. Can be used multiple times. Same as "
                "unittest -k option."
            ),
        )

    @property
    def shuffle_seed(self):
        if self._shuffler is None:
            return None
        return self._shuffler.seed

    def log(self, msg, level=None):
        """
        Log the message at the given logging level (the default is INFO).

        If a logger isn't set, the message is instead printed to the console,
        respecting the configured verbosity. A verbosity of 0 prints no output,
        a verbosity of 1 prints INFO and above, and a verbosity of 2 or higher
        prints all levels.
        """
        if level is None:
            level = logging.INFO
        if self.logger is None:
            if self.verbosity <= 0 or (self.verbosity == 1 and level < logging.INFO):
                return
            print(msg)
        else:
            self.logger.log(level, msg)

    def setup_test_environment(self, **kwargs):
        setup_test_environment(debug=self.debug_mode)
        unittest.installHandler()

    def setup_shuffler(self):
        if self.shuffle is False:
            return
        shuffler = Shuffler(seed=self.shuffle)
        self.log(f"Using shuffle seed: {shuffler.seed_display}")
        self._shuffler = shuffler

    @contextmanager
    def load_with_patterns(self):
        original_test_name_patterns = self.test_loader.testNamePatterns
        self.test_loader.testNamePatterns = self.test_name_patterns
        try:
            yield
        finally:
            # Restore the original patterns.
            self.test_loader.testNamePatterns = original_test_name_patterns

    def load_tests_for_label(self, label, discover_kwargs):
        label_as_path = os.path.abspath(label)
        tests = None

        # If a module, or "module.ClassName[.method_name]", just run those.
        if not os.path.exists(label_as_path):
            with self.load_with_patterns():
                tests = self.test_loader.loadTestsFromName(label)
            if tests.countTestCases():
                return tests
        # Try discovery if "label" is a package or directory.
        is_importable, is_package = try_importing(label)
        if is_importable:
            if not is_package:
                return tests
        elif not os.path.isdir(label_as_path):
            if os.path.exists(label_as_path):
                assert tests is None
                raise RuntimeError(
                    f"One of the test labels is a path to a file: {label!r}, "
                    f"which is not supported. Use a dotted module name or "
                    f"path to a directory instead."
                )
            return tests

        kwargs = discover_kwargs.copy()
        if os.path.isdir(label_as_path) and not self.top_level:
            kwargs["top_level_dir"] = find_top_level(label_as_path)

        with self.load_with_patterns():
            tests = self.test_loader.discover(start_dir=label, **kwargs)

        # Make unittest forget the top-level dir it calculated from this run,
        # to support running tests from two different top-levels.
        self.test_loader._top_level_dir = None
        return tests

    def build_suite(self, test_labels=None, **kwargs):
        test_labels = test_labels or ["."]

        discover_kwargs = {}
        if self.pattern is not None:
            discover_kwargs["pattern"] = self.pattern
        if self.top_level is not None:
            discover_kwargs["top_level_dir"] = self.top_level
        self.setup_shuffler()

        all_tests = []
        for label in test_labels:
            tests = self.load_tests_for_label(label, discover_kwargs)
            all_tests.extend(iter_test_cases(tests))
        
        self.log("Found %d test(s)." % len(all_tests))
        suite = self.test_suite(all_tests)
        return suite

    def setup_databases(self, **kwargs):
        pass

    def get_resultclass(self):
        if self.pdb:
            return PDBDebugResult

    def get_test_runner_kwargs(self):
        kwargs = {
            "failfast": self.failfast,
            "resultclass": self.get_resultclass(),
            "verbosity": self.verbosity,
            "buffer": self.buffer,
        }
        return kwargs

    def run_checks(self, databases):
        pass

    def run_suite(self, suite, **kwargs):
        kwargs = self.get_test_runner_kwargs()
        runner = self.test_runner(**kwargs)
        try:
            return runner.run(suite)
        finally:
            if self._shuffler is not None:
                seed_display = self._shuffler.seed_display
                self.log(f"Used shuffle seed: {seed_display}")

    def teardown_databases(self, old_config, **kwargs):
        """Destroy all the non-mirror databases."""
        pass

    def teardown_test_environment(self, **kwargs):
        unittest.removeHandler()
        teardown_test_environment()

    def suite_result(self, suite, result, **kwargs):
        return (
            len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses)
        )

    def _get_databases(self, suite):
        databases = {}
        return databases

    def get_databases(self, suite):
        databases = self._get_databases(suite)
        return databases

    def run_tests(self, test_labels, **kwargs):
        """
        Run the unit tests for all the test labels in the provided list.

        Test labels should be dotted Python paths to test modules, test
        classes, or test methods.

        Return the number of tests that failed.
        """
        self.setup_test_environment()
        suite = self.build_suite(test_labels)
        databases = self.get_databases(suite)
        suite.serialized_aliases = set(
            alias for alias, serialize in databases.items() if serialize
        )
        suite.used_aliases = set(databases)
        with self.time_keeper.timed("Total database setup"):
            old_config = self.setup_databases(
                aliases=databases,
                serialized_aliases=suite.serialized_aliases,
            )
        run_failed = False
        try:
            self.run_checks(databases)
            result = self.run_suite(suite)
        except Exception:
            run_failed = True
            raise
        finally:
            try:
                with self.time_keeper.timed("Total database teardown"):
                    self.teardown_databases(old_config)
                self.teardown_test_environment()
            except Exception:
                # Silence teardown exceptions if an exception was raised during
                # runs to avoid shadowing it.
                if not run_failed:
                    raise
        self.time_keeper.print_results()
        return self.suite_result(suite, result)

def try_importing(label):
    """
    Try importing a test label, and return (is_importable, is_package).

    Relative labels like "." and ".." are seen as directories.
    """
    try:
        mod = import_module(label)
    except (ImportError, TypeError):
        return (False, False)

    return (True, hasattr(mod, "__path__"))


def find_top_level(top_level):
    # Try to be a bit smarter than unittest about finding the default top-level
    # for a given directory path, to avoid breaking relative imports.
    # (Unittest's default is to set top-level equal to the path, which means
    # relative imports will result in "Attempted relative import in
    # non-package.").

    # We'd be happy to skip this and require dotted module paths (which don't
    # cause this problem) instead of file paths (which do), but in the case of
    # a directory in the cwd, which would be equally valid if considered as a
    # top-level module or as a directory path, unittest unfortunately prefers
    # the latter.
    while True:
        init_py = os.path.join(top_level, "__init__.py")
        if not os.path.exists(init_py):
            break
        try_next = os.path.dirname(top_level)
        if try_next == top_level:
            # __init__.py all the way down? give up.
            break
        top_level = try_next
    return top_level

      