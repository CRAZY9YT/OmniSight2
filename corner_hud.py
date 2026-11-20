"""
corner_hud.py
-------------
OmniSight corner HUD indicators.
Four animated corners that show thinking/ready state.
"""

import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtProperty
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen
)


ACCENT = QColor(101, 213, 255)
SUCCESS = QColor(74, 222, 128)
ERROR = QColor(255, 100, 100)


class CornerWidget(QWidget):

    def __init__(self, corner, parent=None):
        super().__init__(parent)

        # corner: "tl", "tr", "bl", "br"
        self.corner = corner

        self._alpha = 180
        self._wave = 0.0
        self._mode = "idle"  # idle, thinking, done, error

        self.setFixedSize(60, 60)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        if self._mode == "thinking":
            self._wave = (self._wave + 0.08) % 1.0
        elif self._mode == "idle":
            self._wave = (self._wave + 0.015) % 1.0
        elif self._mode == "done":
            self._wave = (self._wave + 0.03) % 1.0
        self.update()

    def set_mode(self, mode):
        self._mode = mode
        self.update()

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._mode == "thinking":
            pulse = (math.sin(self._wave * math.pi * 2) + 1) / 2
            color = QColor(
                int(ACCENT.red()),
                int(ACCENT.green()),
                int(ACCENT.blue()),
                int(120 + pulse * 135)
            )
            width = 2.5 + pulse * 2.5
        elif self._mode == "done":
            pulse = (math.sin(self._wave * math.pi * 2) + 1) / 2
            color = QColor(
                SUCCESS.red(), SUCCESS.green(), SUCCESS.blue(),
                int(100 + pulse * 100)
            )
            width = 2.0
        elif self._mode == "error":
            color = QColor(ERROR.red(), ERROR.green(), ERROR.blue(), 180)
            width = 2.0
        else:
            # idle — slow gentle breathing
            pulse = (math.sin(self._wave * math.pi * 2) + 1) / 2
            color = QColor(
                ACCENT.red(), ACCENT.green(), ACCENT.blue(),
                int(40 + pulse * 60)
            )
            width = 1.5

        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        size = 22
        pad = 6

        r = self.rect()

        if self.corner == "tl":
            p.drawLine(pad, pad + size, pad, pad)
            p.drawLine(pad, pad, pad + size, pad)
        elif self.corner == "tr":
            p.drawLine(r.right() - pad - size, pad, r.right() - pad, pad)
            p.drawLine(r.right() - pad, pad, r.right() - pad, pad + size)
        elif self.corner == "bl":
            p.drawLine(pad, r.bottom() - pad - size, pad, r.bottom() - pad)
            p.drawLine(pad, r.bottom() - pad, pad + size, r.bottom() - pad)
        elif self.corner == "br":
            p.drawLine(r.right() - pad - size, r.bottom() - pad, r.right() - pad, r.bottom() - pad)
            p.drawLine(r.right() - pad, r.bottom() - pad, r.right() - pad, r.bottom() - pad - size)

        p.end()


class CornerHUD:

    def __init__(self):

        self._corners = {}
        self._visible = False

        screen = QApplication.primaryScreen().availableGeometry()

        positions = {
            "tl": (0, 0),
            "tr": (screen.right() - 60, 0),
            "bl": (0, screen.bottom() - 60),
            "br": (screen.right() - 60, screen.bottom() - 60),
        }

        for name, (x, y) in positions.items():
            w = CornerWidget(name)
            w.move(x, y)
            self._corners[name] = w

    def show(self):
        for w in self._corners.values():
            w.show()
        self._visible = True

    def hide(self):
        for w in self._corners.values():
            w.hide()
        self._visible = False

    def set_mode(self, mode):
        for w in self._corners.values():
            w.set_mode(mode)

    def thinking(self):
        self.show()
        self.set_mode("thinking")

    def ready(self):
        self.set_mode("done")
        QTimer.singleShot(2000, self._back_to_idle)

    def error(self):
        self.set_mode("error")
        QTimer.singleShot(2000, self._back_to_idle)

    def _back_to_idle(self):
        self.set_mode("idle")

    def idle(self):
        self.show()
        self.set_mode("idle")