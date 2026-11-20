import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QDialog, QLineEdit,
    QGraphicsDropShadowEffect, QTabWidget
)

from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtProperty
)

from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath,
    QLinearGradient, QBrush, QPen
)

from voice_input import VoiceWorker


# ==========================================
# THEME
# ==========================================

GLASS_BG = "rgba(18, 22, 30, 0.82)"
GLASS_BORDER = "rgba(255, 255, 255, 0.09)"
ACCENT = "#65d5ff"
ACCENT_DIM = "rgba(101, 213, 255, 0.18)"
TEXT = "#e8edf2"
MUTED = "#6b7a8d"
SUCCESS = "#4ade80"
PANEL_BG = "rgba(255, 255, 255, 0.04)"


# ==========================================
# GLOW PILL
# ==========================================

class GlowPill(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._glow_alpha = 60

        self._anim = QPropertyAnimation(
            self, b"glowAlpha", self
        )
        self._anim.setDuration(2200)
        self._anim.setStartValue(30)
        self._anim.setEndValue(140)
        self._anim.setEasingCurve(
            QEasingCurve.Type.SineCurve
        )
        self._anim.setLoopCount(-1)
        self._anim.start()

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self._wave_offset = 0.0

        self._wave_timer = QTimer(self)
        self._wave_timer.timeout.connect(self._tick_wave)
        self._wave_timer.start(16)

    def _tick_wave(self):
        self._wave_offset = (
            self._wave_offset + 0.003
        ) % 1.0
        self.update()

    def _get_glow(self):
        return self._glow_alpha

    def _set_glow(self, value):
        self._glow_alpha = value
        self.update()

    glowAlpha = pyqtProperty(
        int, _get_glow, _set_glow
    )

    def stop_pulse(self):
        self._anim.stop()
        self._glow_alpha = 0
        self.update()

    def start_pulse(self):
        self._anim.start()

    def paintEvent(self, event):

        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QRadialGradient

        p = QPainter(self)
        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        r = self.rect()
        rf = QRectF(r)

        if self._glow_alpha > 10:

            glow_strength = self._glow_alpha / 255.0

            cx = rf.center().x()
            cy = rf.center().y()

            grad = QRadialGradient(
                cx,
                cy,
                max(rf.width(), rf.height()) * 0.72
            )

            grad.setColorAt(
                0.55, QColor(101, 213, 255, 0)
            )
            grad.setColorAt(
                0.78,
                QColor(
                    101, 213, 255,
                    int(28 * glow_strength)
                )
            )
            grad.setColorAt(
                1.0, QColor(101, 213, 255, 0)
            )

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))

            p.drawRoundedRect(
                rf.adjusted(-8, -8, 8, 8),
                26, 26
            )

        w = rf.width()
        wave = self._wave_offset

        aurora = QLinearGradient(0, 0, w, 0)

        def stop_color(phase):

            colors = [
                QColor(20, 10, 40, 230),
                QColor(80, 20, 120, 220),
                QColor(50, 160, 220, 200),
                QColor(120, 40, 180, 210),
                QColor(20, 10, 40, 230),
            ]

            t = phase % 1.0
            scaled = t * (len(colors) - 1)

            i = int(scaled)
            frac = scaled - i

            c1 = colors[i]
            c2 = colors[min(i + 1, len(colors) - 1)]

            return QColor(
                int(c1.red() + frac * (c2.red() - c1.red())),
                int(c1.green() + frac * (c2.green() - c1.green())),
                int(c1.blue() + frac * (c2.blue() - c1.blue())),
                int(c1.alpha() + frac * (c2.alpha() - c1.alpha()))
            )

        aurora.setColorAt(0.0, stop_color(wave))
        aurora.setColorAt(0.4, stop_color(wave + 0.25))
        aurora.setColorAt(0.7, stop_color(wave + 0.5))
        aurora.setColorAt(1.0, stop_color(wave + 0.75))

        p.setBrush(QBrush(aurora))
        p.setPen(Qt.PenStyle.NoPen)

        p.drawRoundedRect(
            QRectF(r.adjusted(1, 1, -1, -1)),
            20, 20
        )

        shimmer = QLinearGradient(
            0, 0, 0, r.height() * 0.5
        )

        shimmer.setColorAt(
            0, QColor(255, 255, 255, 18)
        )
        shimmer.setColorAt(
            1, QColor(255, 255, 255, 0)
        )

        p.setBrush(QBrush(shimmer))

        p.drawRoundedRect(
            QRectF(r.adjusted(1, 1, -1, -1)),
            20, 20
        )

        p.setPen(
            QPen(QColor(255, 255, 255, 40), 1)
        )
        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawRoundedRect(
            QRectF(r.adjusted(1, 1, -1, -1)),
            20, 20
        )

        p.end()


# ==========================================
# QUESTION DIALOG
# ==========================================

class QuestionDialog(QDialog):

    def __init__(self, parent=None, auto_record=False):
        super().__init__(parent)

        self.voice_worker = None
        self.voice_used = False
        self.auto_record = auto_record

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setWindowModality(
            Qt.WindowModality.ApplicationModal
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setFixedWidth(480)

        outer = QWidget(self)
        outer.setObjectName("outer")

        outer.setStyleSheet("""
            QWidget#outer {
                background-color: rgba(14, 18, 26, 0.96);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))

        outer.setGraphicsEffect(shadow)

        layout = QVBoxLayout(outer)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Ask OmniSight")
        title.setStyleSheet(
            f"color: {ACCENT}; font-weight: 700;"
            "letter-spacing: 0.5px;"
        )
        title.setFont(QFont("Segoe UI", 14))

        subtitle = QLabel(
            "What do you want to know about your screen?"
        )
        subtitle.setStyleSheet(
            f"color: {MUTED}; font-size: 11px;"
        )

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Type your question..."
        )
        self.input.setFont(QFont("Segoe UI", 11))
        self.input.setFixedHeight(44)

        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(255,255,255,0.05);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 10px;
                padding: 0 14px;
            }}

            QLineEdit:focus {{
                border: 1px solid rgba(101,213,255,0.55);
                background-color: rgba(101,213,255,0.04);
            }}
        """)

        self.input.returnPressed.connect(self.accept)

        self.mic_button = QPushButton("⏺  Record")
        self.mic_button.setFixedHeight(40)

        self.mic_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(180, 40, 180, 0.45),
                    stop:1 rgba(120, 20, 200, 0.45)
                );
                color: #f0c0ff;
                border: 1px solid rgba(200, 80, 220, 0.45);
                border-radius: 9px;
                padding: 0 16px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(220, 60, 200, 0.65),
                    stop:1 rgba(150, 30, 240, 0.65)
                );
                border-color: rgba(230, 100, 255, 0.75);
            }}

            QPushButton:disabled {{
                color: {MUTED};
            }}
        """)

        self.mic_button.clicked.connect(
            self._toggle_recording
        )

        self.voice_status = QLabel(
            "Ready for your question."
        )
        self.voice_status.setStyleSheet(
            f"color: {MUTED}; font-size: 10px;"
        )
        self.voice_status.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.mic_button)
        buttons.addStretch()

        submit_button = QPushButton("Ask  →")
        submit_button.setFixedHeight(40)

        submit_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b428b4, stop:1 #e040c8
                );
                color: #ffffff;
                border: none;
                border-radius: 9px;
                padding: 0 22px;
                font-weight: 700;
                font-size: 12px;
            }

            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d040d0, stop:1 #ff60e0
                );
            }
        """)

        submit_button.clicked.connect(self.accept)
        buttons.addWidget(submit_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.input)
        layout.addWidget(self.voice_status)
        layout.addLayout(buttons)

        dlg_layout = QVBoxLayout(self)
        dlg_layout.setContentsMargins(12, 12, 12, 12)
        dlg_layout.addWidget(outer)

        screen = QApplication.primaryScreen().availableGeometry()

        self.adjustSize()

        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

    def _toggle_recording(self):

        if (
            self.voice_worker is not None
            and self.voice_worker.isRunning()
        ):
            self.mic_button.setEnabled(False)
            self.mic_button.setText("Transcribing...")
            self.voice_worker.stop_recording()
            return

        self._start_recording()

    def _start_recording(self):

        self.mic_button.setEnabled(False)
        self.mic_button.setText("Starting...")

        self.voice_worker = VoiceWorker(self)

        self.voice_worker.status_changed.connect(
            self._on_voice_status
        )

        self.voice_worker.transcription_ready.connect(
            self._on_transcription
        )

        self.voice_worker.error_occurred.connect(
            self._on_voice_error
        )

        self.voice_worker.finished.connect(
            self._on_voice_finished
        )

        self.voice_worker.start()

    def _on_voice_status(self, status):

        self.voice_status.setText(status)

        if status == "Listening...":
            self.mic_button.setEnabled(True)
            self.mic_button.setText("⏹  Stop")

        elif status == "Transcribing...":
            self.mic_button.setEnabled(False)
            self.mic_button.setText("Transcribing...")

        else:
            self.mic_button.setEnabled(False)
            self.mic_button.setText("Loading...")

    def _on_transcription(self, text):

        if text:
            self.voice_used = True
            self.input.setText(text)

            self.voice_status.setText(
                "Voice recognized. Press Ask to continue."
            )

        else:
            self.voice_status.setText(
                "No speech detected. Try again."
            )

    def _on_voice_error(self, error):
        self.voice_status.setText(
            f"Voice error: {error}"
        )

    def _on_voice_finished(self):

        self.mic_button.setEnabled(True)
        self.mic_button.setText("⏺  Record")
        self.voice_worker = None

    def showEvent(self, event):

        super().showEvent(event)

        self.raise_()
        self.activateWindow()

        if self.auto_record:
            QTimer.singleShot(
                250, self._start_recording
            )
        else:
            QTimer.singleShot(
                100, self._focus_input
            )

    def _focus_input(self):

        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def get_question(self):
        return self.input.text().strip()


# ==========================================
# AURORA PANEL
# ==========================================

class AuroraPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("panel")

        self._wave_offset = 0.0

        self._wave_timer = QTimer(self)
        self._wave_timer.timeout.connect(self._tick)
        self._wave_timer.start(16)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

    def _tick(self):

        self._wave_offset = (
            self._wave_offset + 0.002
        ) % 1.0

        self.update()

    def _aurora_color(self, phase):

        colors = [
            QColor(20, 10, 40, 255),
            QColor(80, 20, 120, 255),
            QColor(50, 160, 220, 255),
            QColor(120, 40, 180, 255),
            QColor(20, 10, 40, 255),
        ]

        t = phase % 1.0
        scaled = t * (len(colors) - 1)

        i = int(scaled)
        frac = scaled - i

        c1 = colors[i]
        c2 = colors[min(i + 1, len(colors) - 1)]

        return QColor(
            int(c1.red() + frac * (c2.red() - c1.red())),
            int(c1.green() + frac * (c2.green() - c1.green())),
            int(c1.blue() + frac * (c2.blue() - c1.blue())),
            255
        )

    def paintEvent(self, event):

        from PyQt6.QtCore import QRectF

        p = QPainter(self)

        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        r = self.rect()
        rf = QRectF(r)

        w = rf.width()
        wave = self._wave_offset

        p.setBrush(
            QBrush(QColor(10, 8, 20, 250))
        )
        p.setPen(Qt.PenStyle.NoPen)

        p.drawRoundedRect(rf, 18, 18)

        bar_height = 52

        aurora = QLinearGradient(0, 0, w, 0)

        aurora.setColorAt(
            0.0, self._aurora_color(wave)
        )
        aurora.setColorAt(
            0.35, self._aurora_color(wave + 0.25)
        )
        aurora.setColorAt(
            0.65, self._aurora_color(wave + 0.5)
        )
        aurora.setColorAt(
            1.0, self._aurora_color(wave + 0.75)
        )

        p.setBrush(QBrush(aurora))
        p.setPen(Qt.PenStyle.NoPen)

        path = QPainterPath()
        path.addRoundedRect(rf, 18, 18)

        p.setClipPath(path)

        p.drawRect(
            QRectF(0, 0, w, bar_height)
        )

        p.setClipping(False)

        fade = QLinearGradient(
            0, bar_height * 0.4,
            0, bar_height
        )

        fade.setColorAt(
            0, QColor(0, 0, 0, 0)
        )
        fade.setColorAt(
            1, QColor(10, 8, 20, 255)
        )

        p.setBrush(QBrush(fade))
        p.setPen(Qt.PenStyle.NoPen)

        p.drawRect(
            QRectF(
                0,
                bar_height * 0.4,
                w,
                bar_height * 0.6
            )
        )

        border_grad = QLinearGradient(0, 0, w, 0)

        border_grad.setColorAt(
            0.0, self._aurora_color(wave + 0.1)
        )
        border_grad.setColorAt(
            0.5, self._aurora_color(wave + 0.4)
        )
        border_grad.setColorAt(
            1.0, self._aurora_color(wave + 0.7)
        )

        p.setPen(
            QPen(QBrush(border_grad), 1.2)
        )

        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawRoundedRect(
            rf.adjusted(0.6, 0.6, -0.6, -0.6),
            18, 18
        )

        p.end()


# ==========================================
# MAIN SIDECAR WINDOW
# ==========================================

class SidecarWindow(QWidget):

    new_response = pyqtSignal(str)
    thinking_started = pyqtSignal()
    status_changed = pyqtSignal(str)
    ask_requested = pyqtSignal()

    scan_requested = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self._drag_pos = None
        self._drag_started = False
        self._question_callback = None

        self.collapsed = True

        self._scan_overlay = None

        self._setup_window()
        self._setup_layout()

        self.new_response.connect(
            self._on_new_response
        )

        self.thinking_started.connect(
            self._on_thinking_started
        )

        self.status_changed.connect(
            self._on_status_changed
        )

        self.ask_requested.connect(
            self._on_ask_requested
        )

        self.scan_requested.connect(
            self._on_scan_requested
        )

    def _setup_window(self):

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.setFixedSize(120, 46)

        screen = QApplication.primaryScreen().availableGeometry()

        self.move(
            screen.center().x() - 60,
            screen.bottom() - 110
        )

    def _setup_layout(self):

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        # ---------- PILL ----------

        self.pill = GlowPill(self)
        self.pill.setFixedSize(120, 46)

        pill_inner = QHBoxLayout(self.pill)
        pill_inner.setContentsMargins(10, 0, 10, 0)
        pill_inner.setSpacing(6)

        self.logo_lbl = QLabel("◈")

        self.logo_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 17px;"
            "background: transparent; border: none;"
        )

        self.pill_label = QLabel("OmniSight")

        self.pill_label.setStyleSheet(
            f"color: {TEXT}; font-size: 10px;"
            "font-weight: 700; background: transparent;"
            "border: none; letter-spacing: 0.5px;"
        )

        self.expand_arrow = QLabel("⌃")

        self.expand_arrow.setStyleSheet(
            f"color: {MUTED}; font-size: 13px;"
            "background: transparent; border: none;"
        )

        pill_inner.addWidget(self.logo_lbl)
        pill_inner.addWidget(self.pill_label)
        pill_inner.addStretch()
        pill_inner.addWidget(self.expand_arrow)

        # ---------- EXPANDED PANEL ----------

        self.panel = AuroraPanel(self)
        self.panel.setFixedSize(400, 310)

        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))

        self.panel.setGraphicsEffect(shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(14, 11, 14, 14)
        panel_layout.setSpacing(10)

        top = QHBoxLayout()

        icon_title = QLabel("◈")

        icon_title.setStyleSheet(
            f"color: {ACCENT}; font-size: 16px;"
            "border: none;"
        )

        title_lbl = QLabel("OMNISIGHT")

        title_lbl.setFont(
            QFont("Segoe UI", 10, QFont.Weight.Bold)
        )

        title_lbl.setStyleSheet(
            f"color: {TEXT}; letter-spacing: 2px;"
            "border: none;"
        )

        collapse_btn = QPushButton("⌄")
        collapse_btn.setFixedSize(28, 26)

        collapse_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255,255,255,0.75);
                background: transparent;
                border: none;
                font-size: 17px;
            }

            QPushButton:hover {
                color: #ffffff;
            }
        """)

        collapse_btn.clicked.connect(self.collapse)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 26)

        close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255,255,255,0.75);
                background: transparent;
                border: none;
                font-size: 12px;
            }

            QPushButton:hover {
                color: #ff6b6b;
            }
        """)

        close_btn.clicked.connect(QApplication.quit)

        top.addWidget(icon_title)
        top.addSpacing(4)
        top.addWidget(title_lbl)
        top.addStretch()
        top.addWidget(collapse_btn)
        top.addWidget(close_btn)

        sep = QWidget()
        sep.setFixedHeight(1)

        sep.setStyleSheet(
            "background: rgba(255,255,255,0.07);"
            "border: none;"
        )

        # ---------- CONTROLS ----------

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.voice_btn = QPushButton("🎙  Voice")
        self.text_btn = QPushButton("⌨  Text")

        for btn in (self.voice_btn, self.text_btn):

            btn.setFixedHeight(40)

            btn.setFont(
                QFont("Segoe UI", 10, QFont.Weight.Bold)
            )

        self.voice_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(180, 40, 180, 0.45),
                    stop:1 rgba(120, 20, 200, 0.45)
                );
                color: #f0c0ff;
                border: 1px solid rgba(200, 80, 220, 0.45);
                border-radius: 10px;
            }

            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(220, 60, 200, 0.65),
                    stop:1 rgba(150, 30, 240, 0.65)
                );
                border-color: rgba(230, 100, 255, 0.75);
            }
        """)

        self.text_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(160, 20, 160, 0.35),
                    stop:1 rgba(220, 60, 180, 0.35)
                );
                color: #f0c0ff;
                border: 1px solid rgba(200, 60, 180, 0.40);
                border-radius: 10px;
            }

            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(190, 30, 190, 0.60),
                    stop:1 rgba(240, 80, 200, 0.60)
                );
                border-color: rgba(255, 100, 220, 0.75);
            }
        """)

        self.voice_btn.clicked.connect(
            lambda: self._open_question_dialog(True)
        )

        self.text_btn.clicked.connect(
            lambda: self._open_question_dialog(False)
        )

        controls.addWidget(self.voice_btn)
        controls.addWidget(self.text_btn)

        # ---------- STATUS ----------

        self.status_lbl = QLabel("●  Ready")

        self.status_lbl.setFont(
            QFont("Segoe UI", 9)
        )

        self.status_lbl.setStyleSheet(
            f"color: {SUCCESS}; border: none;"
        )

        # ---------- ANSWERS & LIVE TABS ----------

        self.response_box = QTextEdit()
        self.response_box.setReadOnly(True)

        self.response_box.setPlaceholderText(
            "Your answers will appear here..."
        )

        self.live_box = QTextEdit()
        self.live_box.setReadOnly(True)

        self.live_box.setPlaceholderText(
            "LIVE observations will appear here..."
        )

        for box in (self.response_box, self.live_box):

            box.setFont(
                QFont("Segoe UI", 10)
            )

            box.document().setDocumentMargin(8)

            box.setStyleSheet("""
                QTextEdit {
                    background-color: transparent;
                    color: #dde3ea;
                    border: none;
                    border-radius: 10px;
                    padding: 12px 14px;
                    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui;
                    font-size: 13px;
                    selection-background-color: rgba(180,40,180,0.35);
                }

                QScrollBar:vertical {
                    width: 3px;
                    background: transparent;
                }

                QScrollBar::handle:vertical {
                    background: rgba(180,80,220,0.3);
                    border-radius: 2px;
                }

                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)

        self.output_tabs = QTabWidget()

        self.output_tabs.addTab(
            self.response_box,
            "ANSWERS"
        )

        self.output_tabs.addTab(
            self.live_box,
            "LIVE MONITOR"
        )

        self.output_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 8px;
                background: rgba(255,255,255,0.02);
            }

            QTabBar::tab {
                color: #6b7a8d;
                background: transparent;
                padding: 7px 14px;
                font-size: 10px;
                font-weight: 600;
                border-bottom: 2px solid transparent;
            }

            QTabBar::tab:selected {
                color: #65d5ff;
                border-bottom: 2px solid #65d5ff;
            }

            QTabBar::tab:hover {
                color: #e8edf2;
            }
        """)

        panel_layout.addLayout(top)
        panel_layout.addWidget(sep)
        panel_layout.addLayout(controls)
        panel_layout.addWidget(self.status_lbl)
        panel_layout.addWidget(self.output_tabs)

        self.root.addWidget(self.pill)
        self.root.addWidget(self.panel)

        self.panel.hide()

    # ==========================================
    # EXPAND / COLLAPSE
    # ==========================================

    def expand(self):

        if not self.collapsed:
            return

        self.collapsed = False

        self.pill.stop_pulse()
        self.pill.hide()

        self.setFixedSize(400, 310)

        self.panel.show()
        self.raise_()

    def collapse(self):

        if self.collapsed:
            return

        self.panel.hide()

        self.collapsed = True

        self.setFixedSize(120, 46)

        self.pill.show()
        self.pill.start_pulse()

        self.raise_()

    # ==========================================
    # DRAGGING
    # ==========================================

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

            self._drag_started = False
            event.accept()

    def mouseMoveEvent(self, event):

        if (
            self._drag_pos is not None
            and event.buttons() == Qt.MouseButton.LeftButton
        ):

            delta = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
                - self._drag_pos
            )

            if not self._drag_started and (
                abs(delta.x()) > 4
                or abs(delta.y()) > 4
            ):
                self._drag_started = True

            if self._drag_started:

                self.move(
                    event.globalPosition().toPoint()
                    - self._drag_pos
                )

                event.accept()

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            if not self._drag_started and self.collapsed:
                self.expand()

            self._drag_pos = None
            self._drag_started = False

    # ==========================================
    # THINKING / STATUS / RESPONSE
    # ==========================================

    def show_thinking(self):
        self.thinking_started.emit()

    def _on_thinking_started(self):

        self.expand()

        self.status_lbl.setText("●  Thinking...")

        self.status_lbl.setStyleSheet(
            f"color: {ACCENT}; border: none;"
        )

    def show_status(self, text):
        self.status_changed.emit(text)

    def _on_status_changed(self, text):

        self.status_lbl.setText(f"●  {text}")

        self.status_lbl.setStyleSheet(
            f"color: {MUTED}; border: none;"
        )

    def show_response(self, text):
        self.new_response.emit(text)

    def _on_new_response(self, text):

        self.status_lbl.setText("●  Ready")

        self.status_lbl.setStyleSheet(
            f"color: {SUCCESS}; border: none;"
        )

        self.response_box.append(
            '<span style="color:#9b6dff; font-size:11px; '
            'font-weight:600; letter-spacing:1px;">OMNI</span>'
        )

        self.response_box.append(
            f'<span style="color:#dde3ea; font-size:13px; '
            f'line-height:1.7;">{text}</span>'
        )

        self.response_box.append(
            '<span style="color:rgba(255,255,255,0.08); '
            'font-size:11px;">──────────────────────</span>'
        )

        self.response_box.verticalScrollBar().setValue(
            self.response_box.verticalScrollBar().maximum()
        )

    # ==========================================
    # LIVE OBSERVATIONS
    # ==========================================

    def show_live_update(self, text):

        self.live_box.append(
            '<span style="color:#65d5ff; '
            'font-size:11px; font-weight:600;">'
            'OMNISIGHT LIVE</span>'
        )

        self.live_box.append(
            f'<span style="color:#dde3ea; '
            f'font-size:13px;">{text}</span>'
        )

        self.live_box.append(
            '<span style="color:rgba(255,255,255,0.08);">'
            '──────────────────────</span>'
        )

        self.live_box.verticalScrollBar().setValue(
            self.live_box.verticalScrollBar().maximum()
        )

    # ==========================================
    # QUESTION DIALOG
    # ==========================================

    def _open_question_dialog(self, auto_record=False):
        self._show_question_dialog(auto_record)

    def _on_ask_requested(self):

        self.expand()
        self._show_question_dialog(False)

    def _show_question_dialog(self, auto_record=False):

        dialog = QuestionDialog(
            self,
            auto_record=auto_record
        )

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:

            question = dialog.get_question()

            if (
                question
                and self._question_callback is not None
            ):
                self._question_callback(
                    question,
                    dialog.voice_used
                )

            elif self._question_callback is not None:
                self._question_callback(None, False)

        else:

            if self._question_callback is not None:
                self._question_callback(None, False)

    # ==========================================
    # SCREEN SCAN OVERLAY
    # ==========================================

    def show_scan(self, on_complete):

        self.scan_requested.emit(on_complete)

    def _on_scan_requested(self, on_complete):

        from scan_overlay import ScanOverlay

        self._scan_overlay = ScanOverlay(
            on_complete=on_complete
        )

        self._scan_overlay.show()

    # ==========================================
    # QUESTION CALLBACK
    # ==========================================

    def set_question_callback(self, callback):
        self._question_callback = callback


# ==========================================
# STANDALONE TEST
# ==========================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = SidecarWindow()
    w.show()

    sys.exit(app.exec())
