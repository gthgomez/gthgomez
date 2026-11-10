"""Unit tests for tools/check_links.py.

Verifies that injected HTTP 200, 404, 429, 500, and 504 responses are classified
correctly and that neither 504 nor 429 can ever be treated as verified success.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request

from tools.check_links import (
    STATUS_FAIL,
    STATUS_INCONCLUSIVE,
    STATUS_PASS,
    check_url,
    classify_http_response,
    extract_external_links_from_file,
)


class TestClassifyHttpResponse(unittest.TestCase):
    def test_pass_200(self):
        status, msg = classify_http_response(200, "OK")
        self.assertEqual(status, STATUS_PASS)
        self.assertIn("200", msg)

    def test_pass_301(self):
        status, msg = classify_http_response(301, "Moved Permanently")
        self.assertEqual(status, STATUS_PASS)

    def test_fail_404_not_found(self):
        status, msg = classify_http_response(404, "Not Found")
        self.assertEqual(status, STATUS_FAIL)
        self.assertIn("404", msg)

    def test_fail_410_gone(self):
        status, msg = classify_http_response(410, "Gone")
        self.assertEqual(status, STATUS_FAIL)

    def test_fail_400_bad_request(self):
        status, msg = classify_http_response(400, "Bad Request")
        self.assertEqual(status, STATUS_FAIL)

    def test_inconclusive_429_rate_limited(self):
        status, msg = classify_http_response(429, "Too Many Requests")
        self.assertEqual(status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(status, STATUS_PASS, "429 must NEVER be classified as PASS")
        self.assertIn("429", msg)

    def test_inconclusive_500_server_error(self):
        status, msg = classify_http_response(500, "Internal Server Error")
        self.assertEqual(status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(status, STATUS_PASS, "500 must NEVER be classified as PASS")

    def test_inconclusive_504_gateway_timeout(self):
        status, msg = classify_http_response(504, "Gateway Timeout")
        self.assertEqual(status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(status, STATUS_PASS, "504 must NEVER be classified as PASS")
        self.assertIn("504", msg)


class TestCheckUrlMocked(unittest.TestCase):
    def test_injected_200_is_pass(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.reason = "OK"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        res = check_url("https://example.com/valid", opener=mock_opener, max_retries=1)
        self.assertEqual(res.status, STATUS_PASS)
        self.assertEqual(res.http_code, 200)

    def test_injected_404_is_fail_no_retry(self):
        mock_opener = MagicMock()
        err = urllib.error.HTTPError(
            url="https://example.com/missing",
            code=404,
            msg="Not Found",
            hdrs={},  # type: ignore
            fp=None,  # type: ignore
        )
        mock_opener.open.side_effect = err

        res = check_url("https://example.com/missing", opener=mock_opener, max_retries=3)
        self.assertEqual(res.status, STATUS_FAIL)
        self.assertEqual(res.http_code, 404)
        # 404 is definitive, should NOT retry
        self.assertEqual(res.attempts, 1)

    def test_injected_429_is_inconclusive_and_retries(self):
        mock_opener = MagicMock()
        err = urllib.error.HTTPError(
            url="https://example.com/rate-limited",
            code=429,
            msg="Too Many Requests",
            hdrs={},  # type: ignore
            fp=None,  # type: ignore
        )
        mock_opener.open.side_effect = err

        res = check_url(
            "https://example.com/rate-limited",
            opener=mock_opener,
            max_retries=3,
            backoff_factor=0.01,
        )
        self.assertEqual(res.status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(res.status, STATUS_PASS)
        self.assertEqual(res.http_code, 429)
        self.assertEqual(res.attempts, 3)

    def test_injected_504_is_inconclusive_and_retries(self):
        mock_opener = MagicMock()
        err = urllib.error.HTTPError(
            url="https://example.com/gateway-timeout",
            code=504,
            msg="Gateway Timeout",
            hdrs={},  # type: ignore
            fp=None,  # type: ignore
        )
        mock_opener.open.side_effect = err

        res = check_url(
            "https://example.com/gateway-timeout",
            opener=mock_opener,
            max_retries=3,
            backoff_factor=0.01,
        )
        self.assertEqual(res.status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(res.status, STATUS_PASS)
        self.assertEqual(res.http_code, 504)
        self.assertEqual(res.attempts, 3)

    def test_injected_500_is_inconclusive(self):
        mock_opener = MagicMock()
        err = urllib.error.HTTPError(
            url="https://example.com/server-error",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore
            fp=None,  # type: ignore
        )
        mock_opener.open.side_effect = err

        res = check_url(
            "https://example.com/server-error",
            opener=mock_opener,
            max_retries=2,
            backoff_factor=0.01,
        )
        self.assertEqual(res.status, STATUS_INCONCLUSIVE)
        self.assertNotEqual(res.status, STATUS_PASS)
        self.assertEqual(res.http_code, 500)


class TestExtractExternalLinks(unittest.TestCase):
    def test_extract_markdown_links(self):
        content = """# Header
Check [Babel](https://github.com/gthgomez/Babel) for agent runtime.
Also see [Live Demo](https://prismatix-app.vercel.app/test).
Exclude [LinkedIn](https://linkedin.com/in/gthgomez).
Relative link: [Case Study](docs/case-studies/babel.md).
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            links = extract_external_links_from_file(temp_path)
            self.assertIn("https://github.com/gthgomez/Babel", links)
            self.assertIn("https://prismatix-app.vercel.app/test", links)
            # Relative links must not be returned
            self.assertNotIn("docs/case-studies/babel.md", links)
            # Excluded linkedin links must not be returned
            self.assertNotIn("https://linkedin.com/in/gthgomez", links)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
