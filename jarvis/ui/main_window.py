from __future__ import annotations

import faulthandler
import platform
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, Signal, Slot, QObject, QTimer
from PySide6.QtGui import QAction, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMenu,
    QStyle,
)

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent
from jarvis.profile import OWNER_PROFILE
from jarvis.ui.first_run import FirstRunWizard, setup_completed
from jarvis.ui.neural_widget import NeuralCoreWidget
from jarvis.ui.platform_dialogs import PlatformCenterDialog
from jarvis.voice.vosk_stt import VoskHandsFreeListener as HandsFreeListener
from jarvis.voice.tts import Speaker


class Bridge(QObject):
    answer = Signal(str)
    partial = Signal(str)
    final_transcript = Signal(str)
    voice_state = Signal(str)
    voice_error = Signal(str)
    voice_level = Signal(float)
    voice_start_finished = Signal(bool, str)
    agent_progress = Signal(str)
    barge_in = Signal()
    speech_finished = Signal()
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
        self.bridge.voice_error.connect(self._on_voice_error)
        self.bridge.voice_level.connect(self._on_voice_level)
        self.bridge.voice_start_finished.connect(self._on_voice_start_finished)
        self.bridge.agent_progress.connect(self._on_agent_progress)
        self.bridge.barge_in.connect(self._on_barge_in)
        self.bridge.speech_finished.connect(self._on_speech_finished)
        self.bridge.confirm_request.connect(self._handle_confirm_request)

        self.speaker = Speaker()
        self.agent = JarvisAgent(confirm=self._confirm_action)
        self.hands_free = False
        self._voice_starting = False
        self._quitting = False
        self._tray: QSystemTrayIcon | None = None
        self.listener: HandsFreeListener | None = None

        self._typewriter_text = ""
        self._typewriter_index = 0
        self._typewriter_cursor: QTextCursor | None = None
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.setInterval(18)
        self._typewriter_timer.timeout.connect(self._typewriter_tick)

        self._build_ui()
        self._setup_tray()
        QTimer.singleShot(700, self._offer_resume_missions)

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

        if settings.llm_provider in {"openrouter", "open_router"}:
            provider_label = f"OPENROUTER · {settings.llm_model}"
        elif settings.llm_provider in {"huggingface", "hf"}:
            provider_label = f"HF · {settings.hf_model}"
        elif settings.llm_provider in {"ollama", "local"}:
            provider_label = f"OLLAMA · {settings.ollama_model}"
        else:
            provider_label = f"{settings.llm_provider.upper()} · {settings.llm_model}"
        self.core_status = QLabel(f"CORE ONLINE · {provider_label}")
        self.core_status.setStyleSheet("color:#ffc864")

        header.addWidget(title)
        header.addStretch(1)
        platform_button = QPushButton("PLATFORM")
        platform_button.setToolTip("Health, permissions, jobs, tasks, activity, workspaces et missions")
        platform_button.clicked.connect(self._open_platform_center)
        header.addWidget(platform_button)
        header.addWidget(self.core_status)
        layout.addLayout(header)

        self.neural = NeuralCoreWidget()
        self.neural.set_state("idle")
        layout.addWidget(self.neural, 3)

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

        self.mode_select = QComboBox()
        self.mode_select.addItem("STANDARD", "standard")
        self.mode_select.addItem("PARALLEL AGENTS", "parallel")
        self.mode_select.addItem("SEQUENTIAL CHAIN", "sequential")
        self.mode_select.addItem("AI DEBATE", "debate")
        self.mode_select.addItem("DEEP RESEARCH", "research")
        self.mode_select.addItem("OPERATIVE", "operative")
        self.mode_select.setMinimumWidth(180)
        controls.addWidget(self.mode_select)

        self.voice_button = QPushButton("MAINS LIBRES : OFF")
        self.voice_button.clicked.connect(self._toggle_voice)
        controls.addWidget(self.voice_button)

        diagnostic_button = QPushButton("DIAGNOSTIC MICRO")
        diagnostic_button.clicked.connect(self._diagnose_microphone)
        controls.addWidget(diagnostic_button)

        test_voice_button = QPushButton("TEST VOIX")
        test_voice_button.clicked.connect(self._test_voice)
        controls.addWidget(test_voice_button)

        add_knowledge_button = QPushButton("AJOUTER DOCUMENT")
        add_knowledge_button.clicked.connect(self._add_knowledge_files)
        controls.addWidget(add_knowledge_button)

        knowledge_button = QPushButton("KNOWLEDGE")
        knowledge_button.clicked.connect(self._show_knowledge)
        controls.addWidget(knowledge_button)

        profile_button = QPushButton("PROFILE")
        profile_button.clicked.connect(self._show_profile)
        controls.addWidget(profile_button)

        memory_button = QPushButton("AGENT MEMORY")
        memory_button.clicked.connect(self._show_agent_memory)
        controls.addWidget(memory_button)

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

    def _offer_resume_missions(self) -> None:
        missions = self.agent.platform.missions(status="active")
        resumable = [
            mission
            for mission in missions
            if self.agent.platform.latest_checkpoint(str(mission.get("id", "")))
        ]
        if not resumable:
            return

        titles = "\n".join(f"• {item.get('title', 'Mission')}" for item in resumable[:6])
        answer = QMessageBox.question(
            self,
            "Reprendre une mission",
            "J.A.R.V.I.S. a trouvé des missions actives avec checkpoint :\n\n"
            + titles
            + "\n\nOuvrir le Platform Center ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._open_platform_center()

    def _open_platform_center(self) -> None:
        dialog = PlatformCenterDialog(self.agent, self)
        dialog.exec()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        app = QApplication.instance()
        if app is None:
            return

        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("J.A.R.V.I.S. · Core online")
        menu = QMenu(self)

        show_action = QAction("Ouvrir J.A.R.V.I.S.", self)
        show_action.triggered.connect(self._restore_from_tray)
        menu.addAction(show_action)

        platform_action = QAction("Platform Center", self)
        platform_action.triggered.connect(self._open_platform_center)
        menu.addAction(platform_action)

        voice_action = QAction("Basculer mains libres", self)
        voice_action.triggered.connect(self._toggle_voice)
        menu.addAction(voice_action)

        stop_action = QAction("STOP global", self)
        stop_action.triggered.connect(self._stop_global)
        menu.addAction(stop_action)

        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.shutdown_and_quit)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self._restore_from_tray()
            if reason in {
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick,
            }
            else None
        )
        tray.show()
        self._tray = tray

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _stop_global(self) -> None:
        cancelled = self.agent.jobs.cancel_all()
        self.speaker.stop()
        if self.listener is not None:
            self.listener.stop()
        self._typewriter_timer.stop()
        self.agent.events.publish(
            "core.stop_requested",
            {"jobs": cancelled, "source": "desktop"},
        )
        self.core_status.setText(f"STOP · {cancelled} JOB(S) ANNULÉ(S)")

    def shutdown_and_quit(self) -> None:
        self._quitting = True
        self._typewriter_timer.stop()
        if self.listener is not None:
            self.listener.shutdown()
        self.speaker.stop()
        self.agent.shutdown()
        if self._tray is not None:
            self._tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _confirm_action(self, summary: str) -> bool:
        request = {
            "summary": summary,
            "event": threading.Event(),
            "allowed": False,
        }
        self.bridge.confirm_request.emit(request)
        request["event"].wait(timeout=60)
        return bool(request["allowed"])

    @Slot(object)
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
                on_status=lambda text: self.bridge.voice_state.emit(text),
                on_error=lambda text: self.bridge.voice_error.emit(text),
                on_level=lambda value: self.bridge.voice_level.emit(value),
            )
        return self.listener

    def _toggle_voice(self) -> None:
        if self._voice_starting:
            return

        if self.hands_free:
            self.hands_free = False
            if self.listener is not None:
                self.listener.stop()
            self.voice_button.setText("MAINS LIBRES : OFF")
            self._set_voice_state("VOICE LINK OFFLINE")
            return

        self.hands_free = True
        self._voice_starting = True
        self.voice_button.setEnabled(False)
        self.voice_button.setText("MAINS LIBRES : DÉMARRAGE…")
        self._set_voice_state("MIC · INITIALISATION…")

        def worker() -> None:
            try:
                self._ensure_listener().start()
            except Exception as exc:
                self.bridge.voice_start_finished.emit(False, str(exc))
                return
            self.bridge.voice_start_finished.emit(True, "")

        threading.Thread(
            target=worker,
            name="jarvis-voice-start",
            daemon=True,
        ).start()

    @Slot(bool, str)
    def _on_voice_start_finished(self, success: bool, message: str) -> None:
        self._voice_starting = False
        self.voice_button.setEnabled(True)

        if not success:
            self.hands_free = False
            self.voice_button.setText("MAINS LIBRES : OFF")
            self._set_voice_state("VOICE ERROR")
            QMessageBox.critical(
                self,
                "Microphone",
                message or "Impossible de démarrer le mode mains libres.",
            )
            return

        if not self.hands_free:
            if self.listener is not None:
                self.listener.stop()
            self.voice_button.setText("MAINS LIBRES : OFF")
            self._set_voice_state("VOICE LINK OFFLINE")
            return

        self.voice_button.setText("MAINS LIBRES : ON")

    def _add_knowledge_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Ajouter à la Knowledge Base",
            "",
            "Documents texte (*.txt *.md *.csv *.json *.py *.js *.ts *.tsx *.jsx *.html *.xml *.log *.yaml *.yml *.sql *.ps1);;Tous les fichiers (*)",
        )
        if not paths:
            return

        imported = []
        errors = []
        for raw in paths:
            try:
                result = self.agent.knowledge.add_file(Path(raw))
                imported.append(f"{result['name']} · {result['chunks']} chunks")
            except Exception as exc:
                errors.append(f"{Path(raw).name}: {exc}")

        if imported:
            self.chat.append(
                "<br><b style='color:#00d4ff'>KNOWLEDGE BASE</b><br>"
                + "<br>".join(imported)
            )
        if errors:
            QMessageBox.warning(
                self,
                "Knowledge Base",
                "Certains fichiers n'ont pas été importés:\n\n" + "\n".join(errors),
            )

    def _show_knowledge(self) -> None:
        docs = self.agent.knowledge.list_documents()
        if not docs:
            QMessageBox.information(
                self,
                "Knowledge Base",
                "Aucun document indexé pour le moment.",
            )
            return

        lines = [f"{len(docs)} document(s) indexé(s)", ""]
        for doc in docs[:30]:
            lines.append(
                f"• {doc['name']} · {doc['chunks']} chunks · {doc['size_chars']} caractères"
            )
        QMessageBox.information(self, "Knowledge Base", "\n".join(lines))

    def _show_profile(self) -> None:
        dynamic = self.agent.memory.facts()
        lines = ["PROFIL PRINCIPAL", "", OWNER_PROFILE]
        if dynamic:
            lines.extend(["", "MÉMOIRE PERSONNALISÉE"])
            for key, value in sorted(dynamic.items()):
                lines.append(f"• {key}: {value}")
        else:
            lines.extend(["", "Aucun fait dynamique mémorisé pour le moment."])
        QMessageBox.information(self, "Profile Memory", "\n".join(lines))

    def _show_agent_memory(self) -> None:
        items = self.agent.memory.recent_agent_results(limit=20)
        if not items:
            QMessageBox.information(
                self,
                "Agent Memory",
                "Aucune tâche multi-agent enregistrée pour le moment.",
            )
            return

        lines = []
        for item in reversed(items):
            lines.append(
                f"[{item['workflow'].upper()}] {item['task']}\n"
                f"{item['summary'][:500]}\n"
            )
        QMessageBox.information(self, "Agent Memory", "\n".join(lines))

    @Slot(str)
    def _on_agent_progress(self, status: str) -> None:
        self.neural.set_state("thinking")
        self.core_status.setText(status)
        self.live_caption.setText(status)

    def _start_typewriter(self, answer: str) -> None:
        self._typewriter_timer.stop()
        self._typewriter_text = answer
        self._typewriter_index = 0

        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml("<br><b style='color:#00d4ff'>J.A.R.V.I.S.</b><br>")
        self._typewriter_cursor = cursor
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()
        self._typewriter_timer.start()

    def _typewriter_tick(self) -> None:
        cursor = self._typewriter_cursor
        if cursor is None:
            self._typewriter_timer.stop()
            return

        if self._typewriter_index >= len(self._typewriter_text):
            self._typewriter_timer.stop()
            self._typewriter_cursor = None
            return

        remaining = len(self._typewriter_text) - self._typewriter_index
        chunk_size = 1 if remaining < 40 else 2
        end = min(
            len(self._typewriter_text),
            self._typewriter_index + chunk_size,
        )
        chunk = self._typewriter_text[self._typewriter_index:end]
        cursor.insertText(chunk)
        self._typewriter_index = end
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def _finish_typewriter(self) -> None:
        cursor = self._typewriter_cursor
        if cursor is None:
            return

        if self._typewriter_index < len(self._typewriter_text):
            cursor.insertText(self._typewriter_text[self._typewriter_index:])
            self._typewriter_index = len(self._typewriter_text)

        self._typewriter_timer.stop()
        self._typewriter_cursor = None
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    @Slot()
    def _on_barge_in(self) -> None:
        if not self.hands_free:
            return

        self.speaker.stop()
        if self.listener is not None:
            self.listener.stop_keyword_monitor()

        self.neural.set_state("listening")
        self.core_status.setText("INTERRUPTED · LISTENING")
        self.live_caption.setText(
            "JARVIS · Interruption détectée. Je vous écoute, H@CKERBOY."
        )

        try:
            self._ensure_listener().start()
        except Exception as exc:
            self.bridge.voice_error.emit(
                f"Erreur reprise microphone après interruption : {exc}"
            )

    @Slot()
    def _on_speech_finished(self) -> None:
        if self.listener is not None:
            self.listener.stop_keyword_monitor()

    def _test_voice(self) -> None:
        was_hands_free = self.hands_free
        if was_hands_free and self.listener is not None:
            self.listener.stop()

        self._set_voice_state("SPEAKING")

        def worker() -> None:
            try:
                self.speaker.test()
                if was_hands_free and self.hands_free:
                    self._ensure_listener().start()
                elif not self.hands_free:
                    self.bridge.voice_state.emit("CORE ONLINE")
            except Exception as exc:
                self.bridge.voice_error.emit(f"Erreur test voix : {exc}")

        threading.Thread(target=worker, name="jarvis-tts-test", daemon=True).start()

    def _diagnose_microphone(self) -> None:
        try:
            devices = HandsFreeListener.input_devices()
        except Exception as exc:
            QMessageBox.critical(self, "Diagnostic microphone", str(exc))
            return

        if not devices:
            QMessageBox.warning(
                self,
                "Diagnostic microphone",
                "Aucun périphérique d'entrée audio n'a été détecté.",
            )
            return

        lines = ["Entrées audio détectées :", ""]
        for dev in devices:
            lines.append(
                f"[{dev['index']}] {dev['name']} · "
                f"{dev['channels']} canal(aux) · {dev['sample_rate']} Hz"
            )

        lines.extend(
            [
                "",
                "Micro configuré : "
                + (settings.audio_device or "périphérique Windows par défaut"),
                "",
                "Pour forcer un micro : JARVIS_AUDIO_DEVICE=\"index ou partie du nom\"",
            ]
        )
        QMessageBox.information(
            self,
            "Diagnostic microphone",
            "\n".join(lines),
        )

    @Slot(float)
    def _on_voice_level(self, level: float) -> None:
        self.neural.set_audio_level(level)

    @Slot(str)
    def _on_voice_error(self, message: str) -> None:
        self._voice_starting = False
        self.voice_button.setEnabled(True)
        self.neural.set_audio_level(0.0)
        self._set_voice_state("VOICE ERROR")
        self.live_caption.setText(f"VOICE ERROR · {message}")
        self.chat.append(
            f"<br><b style='color:#ff5757'>VOICE DIAGNOSTIC</b><br>{message}"
        )

        lower_message = message.lower()
        fatal = (
            "whisper" in lower_message
            or "vosk" in lower_message
            or "microphone" in lower_message
            or "périphérique" in lower_message
            or "mémoire insuffisante" in lower_message
            or "memory" in lower_message
        )
        if fatal:
            self.hands_free = False
            self.voice_button.setText("MAINS LIBRES : OFF")
            if self.listener is not None:
                self.listener.stop()

    @Slot(str)
    def _on_partial(self, text: str) -> None:
        if self.hands_free:
            self.live_caption.setText(f"LISTENING · {text}")

    @Slot(str)
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
        mode = str(self.mode_select.currentData() or "standard")
        threading.Thread(
            target=self._ask_worker,
            args=(text, spoken, mode),
            daemon=True,
        ).start()

    def _ask_worker(self, text: str, spoken: bool, mode: str) -> None:
        del spoken
        answer = self.agent.ask(
            text,
            mode=mode,
            progress=lambda status: self.bridge.agent_progress.emit(status),
        )
        self.bridge.answer.emit(answer)

        if self.hands_free:
            self.bridge.voice_state.emit("SPEAKING")
            try:
                listener = self._ensure_listener()
                listener.start_keyword_monitor(
                    lambda: self.bridge.barge_in.emit()
                )
                self.speaker.speak(answer)
            except Exception as exc:
                self.bridge.voice_error.emit(f"Erreur synthèse vocale : {exc}")
            finally:
                self.bridge.speech_finished.emit()
                if self.hands_free:
                    try:
                        self._ensure_listener().start()
                    except Exception as exc:
                        self.bridge.voice_error.emit(
                            f"Erreur reprise microphone : {exc}"
                        )

    @Slot(str)
    def _on_answer(self, answer: str) -> None:
        self._start_typewriter(answer)
        self.input.setEnabled(True)
        self.input.setFocus()
        if not self.hands_free:
            self._set_voice_state("CORE ONLINE")

        preferences = QSettings("HACKERBOY", "JARVIS")
        notifications = preferences.value("desktop/notifications", True, type=bool)
        if notifications and not self.isActiveWindow() and self._tray is not None:
            self._tray.showMessage(
                "J.A.R.V.I.S.",
                "La réponse est prête.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    @Slot(str)
    def _set_voice_state(self, state: str) -> None:
        self.neural.set_state(state)
        self.core_status.setText(state)
        if state.startswith("LISTENING"):
            if "VOIX DÉTECTÉE" not in state:
                self.live_caption.setText("LISTENING · Parlez naturellement, H@CKERBOY.")
        elif state.startswith("WHISPER") or state.startswith("VOSK"):
            self.live_caption.setText(state)
        elif state.startswith("TRANSCRIBING"):
            self.live_caption.setText(state)
        elif state.startswith("SPEAKING"):
            self.live_caption.setText(
                "SPEAKING · Dites « Jarvis » pour interrompre."
            )
        elif state.startswith("MIC"):
            self.live_caption.setText(state)

    def closeEvent(self, event) -> None:
        preferences = QSettings("HACKERBOY", "JARVIS")
        background = preferences.value("desktop/background", True, type=bool)
        if (
            not self._quitting
            and background
            and self._tray is not None
            and self._tray.isVisible()
        ):
            self.hide()
            if preferences.value("desktop/notifications", True, type=bool):
                self._tray.showMessage(
                    "J.A.R.V.I.S.",
                    "J.A.R.V.I.S. continue de fonctionner en arrière-plan.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            event.ignore()
            return

        self._quitting = True
        self._typewriter_timer.stop()
        if self.listener is not None:
            self.listener.shutdown()
        self.speaker.stop()
        self.agent.shutdown()
        event.accept()


def run_app(*, diagnostic_seconds: float | None = None) -> int:
    """Launch the native Qt desktop UI with visible startup diagnostics."""

    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass

    started = time.monotonic()
    print(
        f"[JARVIS] Desktop startup · Python {platform.python_version()} · "
        f"{platform.system()} {platform.release()} · {platform.machine()}",
        flush=True,
    )

    try:
        print("[JARVIS] Qt: creating application…", flush=True)
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("J.A.R.V.I.S.")
        app.setQuitOnLastWindowClosed(True)

        if diagnostic_seconds is None and not setup_completed():
            wizard = FirstRunWizard()
            wizard.exec()

        print("[JARVIS] UI: constructing MainWindow…", flush=True)
        window = MainWindow()

        print("[JARVIS] UI: showing window…", flush=True)
        window.show()
        window.raise_()
        window.activateWindow()

        if diagnostic_seconds is not None:
            delay_ms = max(500, int(float(diagnostic_seconds) * 1000))

            def _finish_diagnostic() -> None:
                print("[JARVIS] UI doctor: event loop is alive.", flush=True)
                window.shutdown_and_quit()

            QTimer.singleShot(delay_ms, _finish_diagnostic)

        print("[JARVIS] Qt event loop: running.", flush=True)
        exit_code = int(app.exec())
        elapsed = time.monotonic() - started
        print(
            f"[JARVIS] Qt event loop stopped · code={exit_code} · "
            f"uptime={elapsed:.2f}s",
            flush=True,
        )

        if diagnostic_seconds is None and elapsed < 1.0:
            print(
                "[JARVIS] WARNING: the desktop UI stopped almost immediately. "
                "Run python -m jarvis doctor and inspect the console output.",
                flush=True,
            )
        return exit_code
    except Exception:
        print("[JARVIS] Python exception during desktop startup:", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1
