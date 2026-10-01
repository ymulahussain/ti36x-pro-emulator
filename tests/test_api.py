import asyncio
import unittest

import httpx
from fastapi.testclient import TestClient

from ti36x.api import app, CALC, SUBSCRIBERS, _broadcast


class APITests(unittest.TestCase):
    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        self.client.post("/reset")

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_web_assets_and_metadata(self):
        for path, marker in [
            ("/", "viewport"),
            ("/static/calc.js", "EventSource"),
            ("/static/calc.css", ".calc"),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.text)
        data = self.client.get("/keys").json()
        self.assertEqual(len(data["grid"]), 7)
        self.assertEqual(len(data["grid"][0]), 5)
        self.assertTrue(data["keys"]["data"]["enabled"])
        self.assertIn("sqrt", data["shortcuts"])
        self.assertIn("sqrt", data["functions"])

    def test_calculation_sequence_and_reset(self):
        state = self.client.post(
            "/press_seq", json={"keys": ["5", "add", "3", "enter"]}
        ).json()
        self.assertEqual(state["result"], "8")
        self.assertIsNone(state["error"])
        state = self.client.post("/expr", json={"expression": "root(3,-8)"}).json()
        self.assertEqual(state["result"], "-2")
        state = self.client.post("/reset").json()
        self.assertEqual(state["history"], [])
        self.assertEqual(state["result"], "0")

    def test_invalid_inputs_do_not_mutate_state(self):
        invalid = [
            ("/press", {"key": "missing"}),
            ("/press", {"key": "1", "extra": 1}),
            ("/press_seq", {"keys": ["1", "missing", "enter"]}),
            ("/press_seq", {"keys": []}),
            ("/press_seq", {"keys": ["1"] * 129}),
            ("/expr", {"expression": ""}),
            ("/expr", {"expression": "  "}),
            ("/expr", {"expression": "1" * 513}),
        ]
        before = self.client.get("/state").json()
        for path, body in invalid:
            with self.subTest(path=path, body=body):
                self.assertEqual(self.client.post(path, json=body).status_code, 422)
                self.assertEqual(self.client.get("/state").json(), before)

    def test_math_error_is_state_and_recovers(self):
        response = self.client.post("/expr", json={"expression": "1/0"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "Error")
        response = self.client.post("/expr", json={"expression": "2+2"})
        self.assertEqual(response.json()["result"], "4")
        self.assertIsNone(response.json()["error"])

    def test_advanced_panel_and_system_workflow(self):
        self.client.post("/press_seq", json={"keys": ["2nd", "sin"]})
        panel = self.client.get("/panel").json()
        self.assertEqual(panel["operation"], "solver")
        result = self.client.post(
            "/feature",
            json={
                "operation": "system",
                "parameters": {"coefficients": [[1, 1], [1, -2]], "rhs": [1, 3]},
            },
        ).json()
        self.assertIsNone(result["error"])
        self.assertEqual(result["feature_result"], {"x": "5/3", "y": "-2/3"})
        self.assertEqual(result["memory"]["x"], "5/3")

    def test_advanced_mode_and_domain_error(self):
        state = self.client.post(
            "/feature", json={"operation": "modes", "parameters": {"angle": "GRAD"}}
        ).json()
        self.assertEqual(state["angle"], "GRAD")
        self.assertEqual(
            self.client.post("/expr", json={"expression": "sin(100)"}).json()["result"],
            "1",
        )
        state = self.client.post(
            "/feature",
            json={"operation": "distribution:invNorm", "parameters": {"area": 2}},
        ).json()
        self.assertIn("0<area<1", state["error"])

    def test_slow_event_subscriber_retains_latest_update(self):
        queue = asyncio.Queue(maxsize=2)
        SUBSCRIBERS.add(queue)
        try:
            for key in ["1", "2", "3"]:
                CALC.press(key)
                _broadcast(key)
            self.assertIn(queue, SUBSCRIBERS)
            self.assertEqual(queue.get_nowait()["entry"], "12")
            latest = queue.get_nowait()
            self.assertEqual(latest["entry"], "123")
            self.assertEqual(latest["last_key"], "3")
        finally:
            SUBSCRIBERS.discard(queue)


class ConcurrentAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_sequence_cannot_be_interleaved_by_reset_or_expression(self):
        CALC.reset()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                sequence = asyncio.create_task(
                    client.post("/press_seq", json={"keys": ["5", "add", "3", "enter"]})
                )
                # Wait until the sequence has acquired the mutation lock.
                for _ in range(100):
                    if app.state.mutation_lock.locked():
                        break
                    await asyncio.sleep(0.001)
                self.assertTrue(app.state.mutation_lock.locked())
                expression = asyncio.create_task(
                    client.post("/expr", json={"expression": "9+1"})
                )
                reset = asyncio.create_task(client.post("/reset"))
                sequence_result, expression_result, reset_result = await asyncio.gather(
                    sequence, expression, reset
                )
                self.assertEqual(sequence_result.json()["result"], "8")
                self.assertEqual(expression_result.json()["result"], "10")
                self.assertEqual(reset_result.json()["result"], "0")
                self.assertEqual(CALC.state.history, [])


if __name__ == "__main__":
    unittest.main()
