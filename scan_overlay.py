"""
scan_overlay.py
---------------
Fullscreen scan animation overlay.
A purple gradient wave sweeps across the screen twice, then closes.
"""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QBrush


class ScanOverlay(QWidget):

    def __init__(self, on_complete):
        super().__init__()

        self._on_complete = on_complete
        self._progress = 0.0      # 0.0 to 1.0 per sweep
        self._sweep = 0           # which sweep we're on (0 or 1)
        self._done = False

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowOpacity(1.0)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # 60fps

    def _tick(self):
        self._progress += 0.018  # speed of sweep

        if self._progress >= 1.0:
            self._progress = 0.0
            self._sweep += 1

        if self._sweep >= 2:
            self._timer.stop()
            self._done = True
            self.update()
            QTimer.singleShot(120, self._finish)
            return

        self.update()

    def _finish(self):
        self.close()
        if self._on_complete:
            self._on_complete()

    def paintEvent(self, event):
        if self._done:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        w = r.width()
        h = r.height()

        # Faint dark purple screen tint
        p.fillRect(r, QColor(20, 5, 40, 18))

        # Scan beam — a soft vertical gradient band
        beam_width = w * 0.18
        beam_x = (self._progress * (w + beam_width)) - beam_width

        beam = QLinearGradient(beam_x, 0, beam_x + beam_width, 0)
        beam.setColorAt(0.0,  QColor(120, 40, 200, 0))
        beam.setColorAt(0.3,  QColor(140, 50, 220, 28))
        beam.setColorAt(0.5,  QColor(180, 80, 255, 55))
        beam.setColorAt(0.7,  QColor(140, 50, 220, 28))
        beam.setColorAt(1.0,  QColor(120, 40, 200, 0))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(beam))
        p.drawRect(QRectF(beam_x, 0, beam_width, h))

        # Horizontal scan line at center of beam
        line_x = beam_x + beam_width * 0.5
        line_grad = QLinearGradient(beam_x, 0, beam_x + beam_width, 0)
        line_grad.setColorAt(0.0, QColor(180, 100, 255, 0))
        line_grad.setColorAt(0.5, QColor(200, 120, 255, 90))
        line_grad.setColorAt(1.0, QColor(180, 100, 255, 0))
        p.setBrush(QBrush(line_grad))
        p.drawRect(QRectF(beam_x, 0, beam_width, h))

        p.end()