import io
import json
import unittest
import urllib.error
from unittest.mock import patch

import mcp_server


class MCPRequestTests(unittest.TestCase):
    def test_http_validation_errors_are_useful(self):
        error = urllib.error.HTTPError(
            "http://test/press",
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(b'{"detail":"Unknown key"}'),
        )
        with patch("mcp_server.urllib.request.urlopen", side_effect=error):
            result = mcp_server.press_key("missing")
        self.assertIn("HTTP 422", result["error"])
        self.assertIn("Unknown key", result["error"])

    def test_unavailable_api_and_timeouts_are_reported(self):
        for error in [urllib.error.URLError("offline"), TimeoutError("timeout")]:
            with (
                self.subTest(error=error),
                patch("mcp_server.urllib.request.urlopen", side_effect=error),
            ):
                self.assertIn("error", mcp_server.get_state())

    def test_sequence_timeout_allows_full_animated_request(self):
        response = io.BytesIO(json.dumps({"result": "8"}).encode())
        with patch(
            "mcp_server.urllib.request.urlopen", return_value=response
        ) as urlopen:
            self.assertEqual(
                mcp_server.press_sequence(["5", "add", "3", "enter"])["result"], "8"
            )
            self.assertGreaterEqual(urlopen.call_args.kwargs["timeout"], 30)
            request = urlopen.call_args.args[0]
            self.assertEqual(
                json.loads(request.data)["keys"], ["5", "add", "3", "enter"]
            )

    def test_panel_without_selection_returns_guidance(self):
        with patch(
            "mcp_server.urllib.request.urlopen", return_value=io.BytesIO(b"null")
        ):
            self.assertIn(
                "Select an advanced workflow", mcp_server.get_panel()["message"]
            )

    def test_invalid_api_response_is_reported(self):
        with patch(
            "mcp_server.urllib.request.urlopen", return_value=io.BytesIO(b"<html>")
        ):
            self.assertIn("invalid JSON", mcp_server.get_state()["error"])


if __name__ == "__main__":
    unittest.main()
