from __future__ import annotations

import sys
import threading

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QFont
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

from jarvis.core.agent import JarvisAgent
from jarvis.voice.tts import Speaker


class Bridge(QObject):
    answer = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — H@CKERBOY")
        self.resize(1100, 720)
        self.bridge = Bridge()
        self.bridge.answer.connect(self._on_answer)
        self.speaker = Speaker()
        self.agent = JarvisAgent(confirm=self._confirm_action)
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
        status = QLabel("CORE ONLINE · PYTHON DESKTOP AGENT")
        status.setStyleSheet("color:#ffc864")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(status)
        layout.addLayout(header)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.append(
            "<b style='color:#00d4ff'>J.A.R.V.I.S.</b><br>"
            "Systèmes nominaux. À votre service, H@CKERBOY."
        )
        layout.addWidget(self.chat, 1)

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
        answer = QMessageBox.question(
            self,
            "Autorisation J.A.R.V.I.S.",
            summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.chat.append(f"<br><b style='color:#ffc864'>H@CKERBOY</b><br>{text}")
        self.input.setEnabled(False)
        threading.Thread(target=self._ask_worker, args=(text,), daemon=True).start()

    def _ask_worker(self, text: str) -> None:
        answer = self.agent.ask(text)
        self.bridge.answer.emit(answer)

    def _on_answer(self, answer: str) -> None:
        self.chat.append(f"<br><b style='color:#00d4ff'>J.A.R.V.I.S.</b><br>{answer}")
        self.input.setEnabled(True)
        self.input.setFocus()
        self.speaker.speak_async(answer)


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("J.A.R.V.I.S.")
    window = MainWindow()
    window.show()
    return app.exec()
