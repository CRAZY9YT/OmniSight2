
import sys
import math
import ctypes

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QRadialGradient


class LiveOverlay(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("OmniSight LIVE")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.phase = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def showEvent(self, event):
        super().showEvent(event)

        hwnd = int(self.winId())

        # Exclude LIVE overlay from Windows screen capture.
        WDA_EXCLUDEFROMCAPTURE = 0x00000011

        result = ctypes.windll.user32.SetWindowDisplayAffinity(
            hwnd,
            WDA_EXCLUDEFROMCAPTURE
        )

        if result:
            print(
                "[OmniSight] LIVE overlay capture exclusion enabled."
            )
        else:
            print(
                "[OmniSight] WARNING: Capture exclusion failed:",
                ctypes.get_last_error()
            )

        # Keep overlay click-through.
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020

        get_style = ctypes.windll.user32.GetWindowLongW
        set_style = ctypes.windll.user32.SetWindowLongW

        style = get_style(hwnd, GWL_EXSTYLE)

        set_style(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )

    def toggle_live(self):

        if self.isVisible():
            self.hide()
            print("[OmniSight] LIVE mode deactivated.")

        else:
            self.showFullScreen()
            self.raise_()
            print("[OmniSight] LIVE mode activated.")

    def animate(self):
        self.phase += 1
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        w = self.width()
        h = self.height()

        # Slow breathing cycle: approximately 7 seconds.
        breath = (
            0.5 - 0.5 * math.cos(
                self.phase * 0.03
            )
        )

        # Smoothly transition between dim and bright.
        pulse = 0.72 + 0.28 * breath

        corners = [
            (0, 0),
            (w, 0),
            (0, h),
            (w, h)
        ]

        radius = min(w, h) * 0.42

        for x, y in corners:

            gradient = QRadialGradient(
                x, y, radius
            )

            gradient.setColorAt(
                0.0,
                QColor(240, 30, 45, int(100 * pulse))
            )

            gradient.setColorAt(
                0.30,
                QColor(175, 35, 95, int(58 * pulse))
            )

            gradient.setColorAt(
                0.65,
                QColor(115, 45, 175, int(30 * pulse))
            )

            gradient.setColorAt(
                1.0,
                QColor(0, 0, 0, 0)
            )

            painter.fillRect(
                self.rect(),
                gradient
            )

        painter.end()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    overlay = LiveOverlay()
    overlay.showFullScreen()

    sys.exit(app.exec())
