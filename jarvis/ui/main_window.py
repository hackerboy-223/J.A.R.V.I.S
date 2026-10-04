from __future__ import annotations

import faulthandler
import importlib.metadata
import os
import platform
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtGui import QAction, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QSystemTrayIcon,
    QStyle,
    QDialog,
    QVBoxLayout,
    QWidget,
)

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent
from jarvis.core.diagnostics import install_crash_hooks
from jarvis.core.preferences import Preferences
from jarvis.core.updater import UpdateService
from jarvis.profile import OWNER_PROFILE
from jarvis.ui.neural_widget import NeuralCoreWidget
from jarvis.ui.first_run import FirstRunWizard
from jarvis.ui.settings_dialog import SettingsDialog
from jarvis.ui.system_center import SystemCenterDialog
from jarvis.voice.vosk_stt import VoskHandsFreeListener as HandsFreeListener
from jarvis.voice.tts import Speaker


class Bridge(QObject):
    answer = Signal(str)
    partial = Signal(str)
    final_transcript = Signal(str)
    voice_state = Signal(str)
    voice_error = Signal(str)
    voice_level = Signal(float)
    agent_progress = Signal(str)
    barge_in = Signal()
    speech_finished = Signal()
    confirm_request = Signal(object)
    runtime_event = Signal(object)
    update_result = Signal(object)
    update_downloaded = Signal(object)
    update_error = Signal(str)


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
        self.bridge.agent_progress.connect(self._on_agent_progress)
        self.bridge.barge_in.connect(self._on_barge_in)
        self.bridge.speech_finished.connect(self._on_speech_finished)
        self.bridge.confirm_request.connect(self._handle_confirm_request)
        self.bridge.runtime_event.connect(self._on_runtime_event)
        self.bridge.update_result.connect(self._on_update_result)
        self.bridge.update_downloaded.connect(self._on_update_downloaded)
        self.bridge.update_error.connect(self._on_update_error)

        self.speaker = Speaker()
        self.agent = JarvisAgent(confirm=self._confirm_action)
        self.preferences = Preferences()
        self.updater = UpdateService()
        self._quitting = False
        self._active_job_id: str | None = None
        self._event_subscription = self.agent.runtime.events.subscribe()
        self.hands_free = False
        self.listener: HandsFreeListener | None = None

        self._typewriter_text = ""
        self._typewriter_index = 0
        self._typewriter_cursor: QTextCursor | None = None
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.setInterval(18)
        self._typewriter_timer.timeout.connect(self._typewriter_tick)

        self._build_ui()
        self._setup_tray()
        self._event_thread = threading.Thread(
            target=self._event_worker,
            name="jarvis-ui-events",
            daemon=True,
        )
        self._event_thread.start()
        QTimer.singleShot(2500, self._auto_check_update)

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

        center_button = QPushButton("CONTROL CENTER")
        center_button.clicked.connect(self._open_control_center)
        controls.addWidget(center_button)

        settings_button = QPushButton("SETTINGS")
        settings_button.clicked.connect(self._open_settings)
        controls.addWidget(settings_button)

        stop_button = QPushButton("STOP")
        stop_button.setStyleSheet("border-color:#ff5757; color:#ff8b8b;")
        stop_button.clicked.connect(self._stop_all)
        controls.addWidget(stop_button)

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
                on_status=lambda text: self.bridge.voice_state.emit(text),
                on_error=lambda text: self.bridge.voice_error.emit(text),
                on_level=lambda value: self.bridge.voice_level.emit(value),
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
            self.voice_button.setText("MAINS LIBRES : ON")
            self._set_voice_state("MIC · INITIALISATION…")
            self._ensure_listener().start()
        except Exception as exc:
            self.hands_free = False
            self.voice_button.setText("MAINS LIBRES : OFF")
            QMessageBox.critical(self, "Microphone", str(exc))

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

    def _on_voice_level(self, level: float) -> None:
        self.neural.set_audio_level(level)

    def _on_voice_error(self, message: str) -> None:
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
        mode = str(self.mode_select.currentData() or "standard")
        threading.Thread(
            target=self._ask_worker,
            args=(text, spoken, mode),
            daemon=True,
        ).start()

    def _ask_worker(self, text: str, spoken: bool, mode: str) -> None:
        del spoken
        job_id = self.agent.submit(
            text,
            mode=mode,
            on_progress=lambda status: self.bridge.agent_progress.emit(status),
        )
        self._active_job_id = job_id

        while True:
            job = self.agent.runtime.jobs.get(job_id)
            if job is None:
                answer = "Erreur agent : job introuvable."
                break
            status = str(job.get("status", ""))
            if status == "completed":
                result = job.get("result") or {}
                answer = str(result.get("answer") or "")
                break
            if status in {"failed", "cancelled"}:
                answer = (
                    "Opération annulée."
                    if status == "cancelled"
                    else f"Erreur agent : {job.get('error', 'inconnue')}"
                )
                break
            time.sleep(0.05)

        self._active_job_id = None
        self.bridge.answer.emit(answer)

        if self.hands_free and answer:
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

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("J.A.R.V.I.S. · Core local")

        menu = QMenu(self)
        open_action = QAction("Ouvrir J.A.R.V.I.S.", self)
        open_action.triggered.connect(self._show_from_tray)
        menu.addAction(open_action)

        control_action = QAction("Control Center", self)
        control_action.triggered.connect(self._open_control_center)
        menu.addAction(control_action)

        voice_action = QAction("Basculer mains libres", self)
        voice_action.triggered.connect(self._toggle_voice)
        menu.addAction(voice_action)

        update_action = QAction("Vérifier les mises à jour", self)
        update_action.triggered.connect(lambda: self._check_updates(manual=True))
        menu.addAction(update_action)

        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self._quit_application)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self._show_from_tray()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        tray.show()
        self.tray = tray

    def _event_worker(self) -> None:
        while not self._quitting:
            try:
                event = self._event_subscription.get(timeout=0.5)
            except queue.Empty:
                continue
            self.bridge.runtime_event.emit(event.as_dict())

    def _on_runtime_event(self, event: object) -> None:
        if not isinstance(event, dict):
            return
        event_type = str(event.get("type", ""))
        if not self.preferences.get_bool("desktop/notifications", True):
            return
        if self.tray is None:
            return

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "job.completed":
            self.tray.showMessage(
                "J.A.R.V.I.S.",
                "Tâche terminée.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        elif event_type == "job.failed":
            self.tray.showMessage(
                "J.A.R.V.I.S. · Erreur",
                str(payload.get("error", "Une tâche a échoué.")),
                QSystemTrayIcon.MessageIcon.Warning,
                7000,
            )

    @staticmethod
    def _current_version() -> str:
        try:
            return importlib.metadata.version("jarvis-desktop")
        except importlib.metadata.PackageNotFoundError:
            return "0.1.0"

    def _auto_check_update(self) -> None:
        if not self.preferences.get_bool("desktop/auto_update_check", True):
            return
        try:
            last = float(self.preferences.get("updates/last_check_epoch", 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if time.time() - last < 86400:
            return
        self._check_updates(manual=False)

    def _check_updates(self, manual: bool = False) -> None:
        self.preferences.set("updates/last_check_epoch", time.time())

        def worker() -> None:
            try:
                info = self.updater.latest(self._current_version())
                info["manual"] = manual
                self.bridge.update_result.emit(info)
            except Exception as exc:
                if manual:
                    self.bridge.update_error.emit(str(exc))

        threading.Thread(target=worker, name="jarvis-update-check", daemon=True).start()

    def _on_update_result(self, info: object) -> None:
        if not isinstance(info, dict):
            return
        if not info.get("available"):
            if info.get("manual"):
                QMessageBox.information(
                    self,
                    "Mises à jour",
                    f"J.A.R.V.I.S. {self._current_version()} est à jour.",
                )
            return

        installer = self.updater.pick_installer(info)
        latest = str(info.get("latest", "nouvelle version"))
        if installer is None:
            if self.tray is not None:
                self.tray.showMessage(
                    "Mise à jour J.A.R.V.I.S.",
                    f"{latest} est disponible sur GitHub Releases.",
                    QSystemTrayIcon.MessageIcon.Information,
                    7000,
                )
            return

        answer = QMessageBox.question(
            self,
            "Mise à jour disponible",
            f"J.A.R.V.I.S. {latest} est disponible.\n\n"
            "Télécharger l'installateur maintenant ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def download_worker() -> None:
            try:
                result = self.updater.download(installer)
                self.bridge.update_downloaded.emit(result)
            except Exception as exc:
                self.bridge.update_error.emit(str(exc))

        threading.Thread(
            target=download_worker,
            name="jarvis-update-download",
            daemon=True,
        ).start()

    def _on_update_downloaded(self, result: object) -> None:
        if not isinstance(result, dict):
            return
        path = str(result.get("path", ""))
        verified = "SHA-256 vérifié" if result.get("verified") else "SHA-256 calculé localement"
        answer = QMessageBox.question(
            self,
            "Mise à jour téléchargée",
            f"Installateur prêt. {verified}.\n\nLancer l'installation maintenant ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes and path:
            try:
                os.startfile(path)
            except Exception as exc:
                QMessageBox.critical(self, "Mise à jour", str(exc))
                return
            self._quit_application()

    def _on_update_error(self, message: str) -> None:
        QMessageBox.warning(self, "Mise à jour", message)

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _open_control_center(self) -> None:
        SystemCenterDialog(self.agent, self).exec()

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _stop_all(self) -> None:
        cancelled = self.agent.stop_all()
        self.speaker.stop()
        if self.listener is not None:
            self.listener.stop()
        self.live_caption.setText(f"STOP · {cancelled} job(s) en annulation")
        self.core_status.setText("STOP REQUESTED")

    def _shutdown(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self._typewriter_timer.stop()
        self._event_subscription.close()
        if self.listener is not None:
            self.listener.shutdown()
        self.speaker.stop()
        self.agent.shutdown()
        if self.tray is not None:
            self.tray.hide()

    def _quit_application(self) -> None:
        self._shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_answer(self, answer: str) -> None:
        self._start_typewriter(answer)
        self.input.setEnabled(True)
        self.input.setFocus()
        if not self.hands_free:
            self._set_voice_state("CORE ONLINE")

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
        if (
            not self._quitting
            and self.preferences.get_bool("desktop/background_mode", True)
            and self.tray is not None
        ):
            self.hide()
            self.tray.showMessage(
                "J.A.R.V.I.S.",
                "J.A.R.V.I.S. reste actif en arrière-plan.",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
            event.ignore()
            return

        self._shutdown()
        event.accept()


def run_app(*, diagnostic_seconds: float | None = None) -> int:
    """Launch the native Qt desktop UI with visible startup diagnostics."""

    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass
    install_crash_hooks()

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
        app.setQuitOnLastWindowClosed(False)

        if diagnostic_seconds is None:
            preferences = Preferences()
            if not preferences.first_run_complete:
                wizard = FirstRunWizard(preferences)
                if wizard.exec() != QDialog.DialogCode.Accepted:
                    return 0

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
                window.close()
                app.quit()

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
