from __future__ import annotations

import sys
import threading

from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent
from jarvis.ui.neural_widget import NeuralCoreWidget
from jarvis.voice.stt import HandsFreeListener
from jarvis.voice.tts import Speaker


class Bridge(QObject):
    answer = Signal(str)
    partial = Signal(str)
    final_transcript = Signal(str)
    voice_state = Signal(str)
    confirm_request = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — H@CKERBOY")
        self.resize(1100, 720)

        self.bridge = Bridge()
        self.bridge.answer.connect(self._on_answer)
        self.bridge.partial.connect(self._on_partial)
        self.bridge.final_transcript.connect(self._on_final_transcript)
        self.bridge.voice_state.connect(self._set_voice_state)
        self.bridge.confirm_request.connect(self._handle_confirm_request)

        self.speaker = Speaker()
        self.agent = JarvisAgent(confirm=self._confirm_action)
        self.hands_free = False
        self.listener: HandsFreeListener | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setStyleSheet(
            """
            QWidget { background: #03070d; color: #dff8ff; }
            QTextEdit, QLineEdit {
                background: #07111b;
                border: 1px solid #00c8ff;
                color: #e9fbff;
                padding: 10px;
            }
            QPushButton {
                background: #062738;
                border: 1px solid #00d4ff;
                color: #7cecff;
                padding: 10px 16px;
                font-weight: 700;
            }
            QPushButton:hover { background: #0a3c51; }
            """
        )
        layout = QVBoxLayout(root)

        header = QHBoxLayout()
        title = QLabel("J.A.R.V.I.S.")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color:#00d4ff")

        provider_label = (
            f"HF · {settings.hf_model}"
            if settings.llm_provider in {"huggingface", "hf"}
            else f"{settings.llm_provider.upper()} · {settings.llm_model}"
        )
        self.core_status = QLabel(f"CORE ONLINE · {provider_label}")
        self.core_status.setStyleSheet("color:#ffc864")

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.core_status)
        layout.addLayout(header)

        self.neural = NeuralCoreWidget()
        self.neural.set_state("idle")
        layout.addWidget(self.neural)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.append(
            "<b style='color:#00d4ff'>J.A.R.V.I.S.</b><br>"
            "Systèmes nominaux. À votre service, H@CKERBOY."
        )
        layout.addWidget(self.chat, 1)

        self.live_caption = QLabel("VOICE LINK OFFLINE")
        self.live_caption.setWordWrap(True)
        self.live_caption.setStyleSheet(
            "border:1px solid #14536a; padding:10px; color:#7cecff; "
            "font-family:Consolas; background:#051019;"
        )
        layout.addWidget(self.live_caption)

        controls = QHBoxLayout()
        self.voice_button = QPushButton("MAINS LIBRES : OFF")
        self.voice_button.clicked.connect(self._toggle_voice)
        controls.addWidget(self.voice_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        composer = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Donnez une instruction à J.A.R.V.I.S...")
        self.input.returnPressed.connect(self._send)

        send = QPushButton("ENVOYER")
        send.clicked.connect(self._send)

        composer.addWidget(self.input, 1)
        composer.addWidget(send)
        layout.addLayout(composer)

        self.setCentralWidget(root)

    def _confirm_action(self, summary: str) -> bool:
        request = {
            "summary": summary,
            "event": threading.Event(),
            "allowed": False,
        }
        self.bridge.confirm_request.emit(request)
        request["event"].wait(timeout=60)
        return bool(request["allowed"])

    def _handle_confirm_request(self, request: object) -> None:
        if not isinstance(request, dict):
            return
        summary = str(request.get("summary", "Autoriser cette action ?"))
        answer = QMessageBox.question(
            self,
            "Autorisation J.A.R.V.I.S.",
            summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        request["allowed"] = answer == QMessageBox.StandardButton.Yes
        event = request.get("event")
        if isinstance(event, threading.Event):
            event.set()

    def _ensure_listener(self) -> HandsFreeListener:
        if self.listener is None:
            self.listener = HandsFreeListener(
                on_partial=lambda text: self.bridge.partial.emit(text),
                on_final=lambda text: self.bridge.final_transcript.emit(text),
            )
        return self.listener

    def _toggle_voice(self) -> None:
        if self.hands_free:
            self.hands_free = False
            if self.listener is not None:
                self.listener.stop()
            self.voice_button.setText("MAINS LIBRES : OFF")
            self._set_voice_state("VOICE LINK OFFLINE")
            return

        try:
            self.hands_free = True
            self._ensure_listener().start()
            self.voice_button.setText("MAINS LIBRES : ON")
            self._set_voice_state("LISTENING · TRANSCRIPTION LOCALE")
        except Exception as exc:
            self.hands_free = False
            self.voice_button.setText("MAINS LIBRES : OFF")
            QMessageBox.critical(self, "Microphone", str(exc))

    def _on_partial(self, text: str) -> None:
        if self.hands_free:
            self.live_caption.setText(f"LISTENING · {text}")

    def _on_final_transcript(self, text: str) -> None:
        if not self.hands_free or not text.strip():
            return
        if self.listener is not None:
            self.listener.stop()
        self.live_caption.setText(f"HEARD · {text}")
        self._submit(text, spoken=True)

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._submit(text, spoken=False)

    def _submit(self, text: str, spoken: bool) -> None:
        self.chat.append(f"<br><b style='color:#ffc864'>H@CKERBOY</b><br>{text}")
        self.input.setEnabled(False)
        self._set_voice_state("THINKING")
        threading.Thread(
            target=self._ask_worker,
            args=(text, spoken),
            daemon=True,
        ).start()

    def _ask_worker(self, text: str, spoken: bool) -> None:
        del spoken
        answer = self.agent.ask(text)
        self.bridge.answer.emit(answer)

        if self.hands_free:
            self.bridge.voice_state.emit("SPEAKING")
            self.speaker.speak(answer)
            if self.hands_free:
                try:
                    self._ensure_listener().start()
                    self.bridge.voice_state.emit("LISTENING · TRANSCRIPTION LOCALE")
                except Exception as exc:
                    self.bridge.voice_state.emit(f"VOICE ERROR · {exc}")

    def _on_answer(self, answer: str) -> None:
        self.chat.append(f"<br><b style='color:#00d4ff'>J.A.R.V.I.S.</b><br>{answer}")
        self.input.setEnabled(True)
        self.input.setFocus()
        if not self.hands_free:
            self._set_voice_state("CORE ONLINE")

    def _set_voice_state(self, state: str) -> None:
        self.neural.set_state(state)
        self.core_status.setText(state)
        if state.startswith("LISTENING"):
            self.live_caption.setText("LISTENING · Parlez naturellement, H@CKERBOY.")
        elif state == "SPEAKING":
            self.live_caption.setText("SPEAKING · J.A.R.V.I.S. répond…")

    def closeEvent(self, event) -> None:
        if self.listener is not None:
            self.listener.stop()
        self.speaker.stop()
        event.accept()


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("J.A.R.V.I.S.")
    window = MainWindow()
    window.show()
    return app.exec()
