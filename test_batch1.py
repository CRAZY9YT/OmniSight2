"""
test_batch1.py: automated checks for Batch 1. Run:  python test_batch1.py

Needs NO network, NO real screen and NO API key. It uses fake Gemini
errors, a fake screen and Qt's headless ("offscreen") mode. That means
it proves the LOGIC, not the real Gemini service or your real screen.
Those still need your manual test (see README).
"""
import csv
import os
import tempfile
import threading
import time
import types as pytypes
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # Qt without a visible window

import numpy as np
from google.genai import errors

import delta_engine
import gemini_client
from ask_pipeline import AskPipeline
from gemini_client import GeminiClient, GeminiRequestError


def api_error(code, message="boom"):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


def fake_response(text):
    return pytypes.SimpleNamespace(text=text, candidates=[])


def client_with(fake_generate):
    c = GeminiClient(api_key="test-key", sleep_fn=lambda s: None)  # no real waiting
    c.client = pytypes.SimpleNamespace(models=pytypes.SimpleNamespace(generate_content=fake_generate))
    return c


class TestGeminiClient(unittest.TestCase):
    def ask(self, c):
        return c.ask_direct_mode(b"jpeg", "q")

    def test_success(self):
        c = client_with(lambda **k: fake_response("hello"))
        self.assertEqual(self.ask(c), "hello")
        self.assertEqual(c.last_attempts, 1)

    def test_503_twice_then_success_is_retried(self):
        calls = []
        def gen(**k):
            calls.append(1)
            if len(calls) < 3:
                raise api_error(503, "overloaded")
            return fake_response("ok")
        c = client_with(gen)
        self.assertEqual(self.ask(c), "ok")
        self.assertEqual((len(calls), c.last_attempts), (3, 3))

    def test_503_forever_gives_up_after_max_attempts(self):
        calls = []
        def gen(**k):
            calls.append(1)
            raise api_error(503)
        c = client_with(gen)
        with self.assertRaises(GeminiRequestError) as cm:
            self.ask(c)
        self.assertEqual(len(calls), gemini_client.MAX_ATTEMPTS)
        self.assertIn("gave up after 3 attempts", str(cm.exception))

    def test_bad_key_http400_not_retried(self):
        calls = []
        def gen(**k):
            calls.append(1)
            raise api_error(400, "API key not valid. Please pass a valid API key.")
        with self.assertRaises(GeminiRequestError) as cm:
            self.ask(client_with(gen))
        self.assertEqual(len(calls), 1)
        self.assertIn("API key", str(cm.exception))

    def test_401_not_retried(self):
        calls = []
        def gen(**k):
            calls.append(1)
            raise api_error(401, "unauthenticated")
        with self.assertRaises(GeminiRequestError):
            self.ask(client_with(gen))
        self.assertEqual(len(calls), 1)

    def test_429_is_retried(self):
        calls = []
        def gen(**k):
            calls.append(1)
            if len(calls) == 1:
                raise api_error(429, "quota")
            return fake_response("ok")
        self.assertEqual(self.ask(client_with(gen)), "ok")
        self.assertEqual(len(calls), 2)

    def test_timeout_not_retried_and_readable(self):
        calls = []
        def gen(**k):
            calls.append(1)
            raise TimeoutError("read timed out")
        with self.assertRaises(GeminiRequestError) as cm:
            self.ask(client_with(gen))
        self.assertEqual(len(calls), 1)
        self.assertIn("timed out", str(cm.exception))

    def test_network_error_is_retried(self):
        calls = []
        def gen(**k):
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionError("reset")
            return fake_response("ok")
        self.assertEqual(self.ask(client_with(gen)), "ok")

    def test_empty_response_raises_readable_error_not_none(self):
        for empty in (None, "", "   "):
            with self.assertRaises(GeminiRequestError) as cm:
                self.ask(client_with(lambda **k: fake_response(empty)))
            self.assertIn("no text", str(cm.exception))

    def test_missing_key_raises_valueerror(self):
        with self.assertRaises(ValueError):
            GeminiClient(api_key="PASTE_YOUR_KEY_HERE")


class FakeUI:
    def __init__(self):
        self.events, self.lock = [], threading.Lock()
    def _add(self, *e):
        with self.lock:
            self.events.append(e)
    def show_thinking(self): self._add("thinking")
    def show_response(self, t): self._add("response", t)
    def show_status(self, t): self._add("status", t)
    def kinds(self): return [e[0] for e in self.events]


class FakeEngine:
    def capture_frame(self): return np.zeros((10, 10, 3), np.uint8)
    def encode_for_ai(self, f): return b"x" * 2048


class FakeClient:
    last_attempts = 1
    def __init__(self, behaviour=None):
        self.calls, self.behaviour = 0, behaviour
    def ask_direct_mode(self, jpeg, q):
        self.calls += 1
        return self.behaviour(jpeg, q) if self.behaviour else "answer"


def wait_until(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "lat.csv")

    def make(self, client=None, engine=None):
        ui = FakeUI()
        return AskPipeline(engine or FakeEngine(), client or FakeClient(), ui, log_path=self.log), ui

    def idle(self, p):
        return wait_until(lambda: not p._busy.locked())

    def rows(self):
        with open(self.log, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_success_flow_events_and_csv(self):
        p, ui = self.make()
        self.assertTrue(p.submit())
        self.assertTrue(self.idle(p))
        self.assertEqual(ui.kinds(), ["thinking", "response", "status"])
        self.assertEqual(ui.events[1][1], "answer")
        self.assertIn("Done in", ui.events[2][1])
        rows = self.rows()
        self.assertEqual((len(rows), rows[0]["outcome"], rows[0]["image_kb"]), (1, "ok", "2"))

    def test_submit_returns_immediately_while_request_is_slow(self):
        gate = threading.Event()
        p, ui = self.make(FakeClient(lambda j, q: (gate.wait(5), "late")[1]))
        t0 = time.time()
        self.assertTrue(p.submit())
        self.assertLess(time.time() - t0, 0.5)  # the hotkey thread is not blocked
        gate.set()
        self.assertTrue(self.idle(p))

    def test_busy_guard_ignores_presses_and_makes_one_request(self):
        gate = threading.Event()
        client = FakeClient(lambda j, q: (gate.wait(5), "slow")[1])
        p, ui = self.make(client)
        self.assertTrue(p.submit())
        self.assertTrue(wait_until(lambda: client.calls == 1))
        self.assertFalse(p.submit())
        self.assertFalse(p.submit())
        self.assertTrue(any(e[0] == "status" and "ignored" in e[1] for e in ui.events))
        gate.set()
        self.assertTrue(self.idle(p))
        self.assertEqual(client.calls, 1)           # no backlog, no duplicates
        self.assertTrue(p.submit())                  # and works again afterwards
        self.assertTrue(self.idle(p))
        self.assertEqual(client.calls, 2)

    def test_gemini_error_is_shown_and_pipeline_recovers(self):
        def boom(j, q): raise GeminiRequestError("Gemini is overloaded (HTTP 503)")
        p, ui = self.make(FakeClient(boom))
        p.submit(); self.assertTrue(self.idle(p))
        resp = [e for e in ui.events if e[0] == "response"][0][1]
        self.assertTrue(resp.startswith("⚠") and "overloaded" in resp)
        self.assertIn("Failed after", [e for e in ui.events if e[0] == "status"][-1][1])
        self.assertEqual(self.rows()[0]["outcome"], "error")
        self.assertTrue(p.submit()); self.assertTrue(self.idle(p))

    def test_capture_crash_does_not_kill_worker_or_leave_lock_held(self):
        class BadEngine(FakeEngine):
            def capture_frame(self): raise RuntimeError("no display")
        p, ui = self.make(engine=BadEngine())
        p.submit(); self.assertTrue(self.idle(p))
        self.assertTrue(any(e[0] == "response" and "Unexpected error" in e[1] for e in ui.events))
        self.assertFalse(p._busy.locked())

    def test_log_failure_never_breaks_request(self):
        p, ui = self.make()
        p.log_path = os.path.join(self.tmp, "no_such_dir", "x.csv")
        p.submit(); self.assertTrue(self.idle(p))
        self.assertIn("response", ui.kinds())


class TestDeltaEngine(unittest.TestCase):
    def make_fake_mss(self, w=1920, h=1080):
        created = []
        class FakeMSS:
            monitors = [{}, {"left": 0, "top": 0, "width": w, "height": h}]
            def __init__(self): created.append(threading.current_thread().name)
            def grab(self, mon): return np.zeros((h, w, 4), np.uint8)
        return FakeMSS, created

    def test_each_thread_gets_its_own_mss_instance(self):
        fake, created = self.make_fake_mss()
        with mock.patch.object(delta_engine, "mss", fake):
            eng = delta_engine.DeltaEngine()
            t = threading.Thread(target=eng.capture_frame, name="worker")
            t.start(); t.join()
            eng.capture_frame()  # same thread again: must reuse, not recreate
        self.assertEqual(sorted(created), sorted([threading.current_thread().name, "worker"]))

    def test_encode_downscales_wide_frames_to_max_width_and_returns_jpeg(self):
        import cv2
        fake, _ = self.make_fake_mss()
        with mock.patch.object(delta_engine, "mss", fake):
            eng = delta_engine.DeltaEngine()
            jpeg = eng.encode_for_ai(np.zeros((1080, 1920, 3), np.uint8))
        self.assertEqual(jpeg[:2], b"\xff\xd8")
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(img.shape[:2], (720, 1280))

    def test_small_frames_are_not_upscaled(self):
        import cv2
        fake, _ = self.make_fake_mss()
        with mock.patch.object(delta_engine, "mss", fake):
            eng = delta_engine.DeltaEngine()
            jpeg = eng.encode_for_ai(np.zeros((400, 800, 3), np.uint8))
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(img.shape[:2], (400, 800))

    def test_has_changed_detects_change_and_ignores_identical_frames(self):
        frames = [np.zeros((50, 50, 4), np.uint8)] * 2 + [np.full((50, 50, 4), 200, np.uint8)]
        it = iter(frames)
        class FakeMSS:
            monitors = [{}, {}]
            def grab(self, m): return next(it)
        with mock.patch.object(delta_engine, "mss", FakeMSS):
            eng = delta_engine.DeltaEngine()          # consumes frame 0 as baseline
            self.assertFalse(eng.has_changed()[0])     # frame 1 identical
            self.assertTrue(eng.has_changed()[0])      # frame 2 very different


class TestSidecarUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_updates_from_worker_thread_reach_widgets_safely(self):
        from sidecar_ui import SidecarWindow
        w = SidecarWindow()
        def worker():
            w.show_thinking()
            w.show_response("the answer")
            w.show_status("Done in 1.0s")
        t = threading.Thread(target=worker); t.start(); t.join()
        end = time.time() + 3
        while time.time() < end and w.status_label.text() != "Done in 1.0s":
            self.app.processEvents(); time.sleep(0.01)
        self.assertEqual(w.response_box.toPlainText(), "the answer")
        self.assertEqual(w.status_label.text(), "Done in 1.0s")  # status set last, so it wins

    def test_status_update_leaves_answer_text_alone(self):
        from sidecar_ui import SidecarWindow
        w = SidecarWindow()
        w.show_response("keep me"); self.app.processEvents()
        w.show_status("Still working..."); self.app.processEvents()
        self.assertEqual(w.response_box.toPlainText(), "keep me")


if __name__ == "__main__":
    unittest.main(verbosity=2)
