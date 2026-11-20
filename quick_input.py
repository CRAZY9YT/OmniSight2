"""
quick_input.py
--------------
Minimal floating input bar for OmniSight.
Appears on hotkey, disappears before screenshot.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit,
    QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QKeyEvent


class QuickInputBar(QWidget):

    submitted = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 48)

        self._place_center()

        self.setStyleSheet("""
            QWidget {
                background: rgba(14, 18, 26, 0.97);
                border: 1px solid rgba(101, 213, 255, 0.35);
                border-radius: 24px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask OmniSight...")
        self.input.setFont(QFont("Segoe UI", 12))
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #e8edf2;
                border: none;
                font-size: 13px;
            }
        """)
        self.input.setFixedHeight(48)

        self.input.returnPressed.connect(self._on_submit)

        layout.addWidget(self.input)

    def _place_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - 250,
            screen.center().y() - 24
        )

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def _on_submit(self):
        question = self.input.text().strip()
        if question:
            self.hide()
            self.input.clear()
            self.submitted.emit(question)
        else:
            self.hide()
            self.cancelled.emit()

    def popup(self):
        self.input.clear()
        self._place_center()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()