import threading
import ctypes
from ctypes import wintypes

import cv2
import numpy as np
from mss import mss


CHANGE_THRESHOLD = 2.0
MAX_WIDTH_FOR_AI = 1280
JPEG_QUALITY = 70


class DeltaEngine:

    def __init__(self, monitor_index: int = 1):

        self.monitor_index = monitor_index
        self._local = threading.local()

        # Windows belonging to OmniSight that should be excluded.
        self._excluded_windows = set()
        self._exclusion_lock = threading.Lock()

        self.last_frame_gray = self._capture_grayscale()

    def _sct(self):

        sct = getattr(self._local, "sct", None)

        if sct is None:
            sct = mss()
            self._local.sct = sct

        return sct

    def add_excluded_window(self, hwnd: int):

        with self._exclusion_lock:
            self._excluded_windows.add(int(hwnd))

        print(f"[OmniSight] Capture exclusion registered: {hwnd}")

    def _get_exclusion_rectangles(self):

        rectangles = []

        with self._exclusion_lock:
            windows = list(self._excluded_windows)

        monitor = self._sct().monitors[self.monitor_index]

        monitor_left = monitor["left"]
        monitor_top = monitor["top"]

        monitor_right = monitor_left + monitor["width"]
        monitor_bottom = monitor_top + monitor["height"]

        for hwnd in windows:

            rect = wintypes.RECT()

            success = ctypes.windll.user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect)
            )

            if not success:
                continue

            # Convert desktop coordinates to monitor coordinates.
            left = max(rect.left, monitor_left)
            top = max(rect.top, monitor_top)

            right = min(rect.right, monitor_right)
            bottom = min(rect.bottom, monitor_bottom)

            if right <= left or bottom <= top:
                continue

            rectangles.append((
                left - monitor_left,
                top - monitor_top,
                right - monitor_left,
                bottom - monitor_top
            ))

        return rectangles

    def _grab_bgra(self) -> np.ndarray:

        sct = self._sct()
        monitor = sct.monitors[self.monitor_index]

        return np.array(sct.grab(monitor))

    def _capture_grayscale(self) -> np.ndarray:

        frame = self._grab_bgra()

        return cv2.cvtColor(
            frame,
            cv2.COLOR_BGRA2GRAY
        )

    def capture_frame(self) -> np.ndarray:

        frame = cv2.cvtColor(
            self._grab_bgra(),
            cv2.COLOR_BGRA2BGR
        )

        # Replace excluded OmniSight window regions.
        rectangles = self._get_exclusion_rectangles()

        if rectangles:

            mask = np.zeros(
                frame.shape[:2],
                dtype=np.uint8
            )

            for x1, y1, x2, y2 in rectangles:

                cv2.rectangle(
                    mask,
                    (x1, y1),
                    (x2 - 1, y2 - 1),
                    255,
                    -1
                )

            frame = cv2.inpaint(
                frame,
                mask,
                5,
                cv2.INPAINT_TELEA
            )

        return frame

    def encode_for_ai(self, frame_bgr: np.ndarray) -> bytes:

        height, width = frame_bgr.shape[:2]

        if width > MAX_WIDTH_FOR_AI:

            scale = MAX_WIDTH_FOR_AI / width

            frame_bgr = cv2.resize(
                frame_bgr,
                (
                    MAX_WIDTH_FOR_AI,
                    int(height * scale)
                ),
                interpolation=cv2.INTER_AREA
            )

        ok, buffer = cv2.imencode(
            ".jpg",
            frame_bgr,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )

        if not ok:
            raise RuntimeError(
                "Failed to encode screenshot as JPEG"
            )

        return buffer.tobytes()

    def grab_screenshot_for_ai(self) -> bytes:

        return self.encode_for_ai(
            self.capture_frame()
        )

    def has_changed(self) -> tuple[bool, float]:

        current_gray = self._capture_grayscale()

        diff = cv2.absdiff(
            self.last_frame_gray,
            current_gray
        )

        # Ignore excluded window regions during change detection.
        valid_mask = np.ones(
            current_gray.shape,
            dtype=np.uint8
        )

        rectangles = self._get_exclusion_rectangles()

        for x1, y1, x2, y2 in rectangles:

            valid_mask[y1:y2, x1:x2] = 0

        valid_pixels = diff[valid_mask == 1]

        if valid_pixels.size == 0:
            change_score = 0.0
        else:
            change_score = float(
                np.mean(valid_pixels)
            )

        changed = change_score > CHANGE_THRESHOLD

        self.last_frame_gray = current_gray

        return changed, change_score