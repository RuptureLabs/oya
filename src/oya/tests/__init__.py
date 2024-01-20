import json
import logging
import sys
import unittest




logger = logging.getLogger("Oya.test")

__all__ = (
    "TestCase",
    "SimpleTestCase",
)


def to_list(value):
    """Put value into a list if it's not already one."""
    if not isinstance(value, list):
        value = [value]
    return value


class SimpleTestCase(unittest.TestCase):
    # The class we'll use for the test client self.client.
    # Can be overridden in derived classes.
    
    _overridden_settings = None
    _modified_settings = None

    databases = set()
    _disallowed_database_msg = (
        "Database %(operation)s to %(alias)r are not allowed in SimpleTestCase "
        "subclasses. Either subclass TestCase or TransactionTestCase to ensure "
        "proper test isolation or add %(alias)r to %(test)s.databases to silence "
        "this failure."
    )
    _disallowed_connection_methods = [
        ("connect", "connections"),
        ("temporary_connection", "connections"),
        ("cursor", "queries"),
        ("chunked_cursor", "queries"),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

  
    
    
    def __call__(self, result=None):
        """
        Wrapper around default __call__ method to perform common Django test
        set up. This means that user-defined TestCases aren't required to
        include a call to super().setUp().
        """
        self._setup_and_call(result)



    def _setup_and_call(self, result, debug=False):
        """
        Perform the following in order: pre-setup, run test, post-teardown,
        skipping pre/post hooks if test is set to be skipped.

        If debug=True, reraise any errors in setup and use super().debug()
        instead of __call__() to run the test.
        """
        testMethod = getattr(self, self._testMethodName)
        skipped = getattr(self.__class__, "__unittest_skip__", False) or getattr(
            testMethod, "__unittest_skip__", False
        )


        if not skipped:
            try:
                self._pre_setup()
            except Exception:
                if debug:
                    raise
                result.addError(self, sys.exc_info())
                return
        if debug:
            super().debug()
        else:
            super().__call__(result)
        if not skipped:
            try:
                self._post_teardown()
            except Exception:
                if debug:
                    raise
                result.addError(self, sys.exc_info())
                return

    def _pre_setup(self):
        pass

    def _post_teardown(self):
        """Perform post-test things."""
        pass

        
    def assertContains(
        self, response, text, count=None, status_code=200, msg_prefix="", html=False
    ):
        """
        Assert that a response indicates that some content was retrieved
        successfully, (i.e., the HTTP status code was as expected) and that
        ``text`` occurs ``count`` times in the content of the response.
        If ``count`` is None, the count doesn't matter - the assertion is true
        if the text occurs at least once in the response.
        """
        text_repr, real_count, msg_prefix, content_repr = self._assert_contains(
            response, text, status_code, msg_prefix, html
        )

        if count is not None:
            self.assertEqual(
                real_count,
                count,
                (
                    f"{msg_prefix}Found {real_count} instances of {text_repr} "
                    f"(expected {count}) in the following response\n{content_repr}"
                ),
            )
        else:
            self.assertTrue(
                real_count != 0,
                (
                    f"{msg_prefix}Couldn't find {text_repr} in the following response\n"
                    f"{content_repr}"
                ),
            )

    def assertNotContains(
        self, response, text, status_code=200, msg_prefix="", html=False
    ):
        """
        Assert that a response indicates that some content was retrieved
        successfully, (i.e., the HTTP status code was as expected) and that
        ``text`` doesn't occur in the content of the response.
        """
        text_repr, real_count, msg_prefix, content_repr = self._assert_contains(
            response, text, status_code, msg_prefix, html
        )

        self.assertEqual(
            real_count,
            0,
            (
                f"{msg_prefix}{text_repr} unexpectedly found in the following response"
                f"\n{content_repr}"
            ),
        )

    def _check_test_client_response(self, response, attribute, method_name):
        """
        Raise a ValueError if the given response doesn't have the required
        attribute.
        """
        if not hasattr(response, attribute):
            raise ValueError(
                f"{method_name}() is only usable on responses fetched using "
                "the Oya test Client."
            )

    def assertJSONEqual(self, raw, expected_data, msg=None):
        """
        Assert that the JSON fragments raw and expected_data are equal.
        Usual JSON non-significant whitespace rules apply as the heavyweight
        is delegated to the json library.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.fail("First argument is not valid JSON: %r" % raw)
        if isinstance(expected_data, str):
            try:
                expected_data = json.loads(expected_data)
            except ValueError:
                self.fail("Second argument is not valid JSON: %r" % expected_data)
        self.assertEqual(data, expected_data, msg=msg)

    def assertJSONNotEqual(self, raw, expected_data, msg=None):
        """
        Assert that the JSON fragments raw and expected_data are not equal.
        Usual JSON non-significant whitespace rules apply as the heavyweight
        is delegated to the json library.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.fail("First argument is not valid JSON: %r" % raw)
        if isinstance(expected_data, str):
            try:
                expected_data = json.loads(expected_data)
            except json.JSONDecodeError:
                self.fail("Second argument is not valid JSON: %r" % expected_data)
        self.assertNotEqual(data, expected_data, msg=msg)


class TestCase(SimpleTestCase):
    pass