from __future__ import annotations

import json

from PySide6.QtCore import QSettings, Qt
from jarvis.config import settings
from jarvis.core.secrets import SecretStore

from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PlatformCenterDialog(QDialog):
    def __init__(self, agent, parent=None) -> None:
        super().__init__(parent)
        self.agent = agent
        self.setWindowTitle("J.A.R.V.I.S. — Platform Center")
        self.resize(920, 650)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.health_text = QTextEdit()
        self.health_text.setReadOnly(True)
        self.tabs.addTab(self.health_text, "HEALTH")

        permissions_page = QWidget()
        permissions_layout = QVBoxLayout(permissions_page)
        self.permissions_table = QTableWidget(0, 3)
        self.permissions_table.setHorizontalHeaderLabels(["Capability", "Decision", "Source"])
        self.permissions_table.horizontalHeader().setStretchLastSection(True)
        permissions_layout.addWidget(self.permissions_table)
        perm_actions = QHBoxLayout()
        for decision in ("allow", "ask", "deny"):
            button = QPushButton(decision.upper())
            button.clicked.connect(lambda _, value=decision: self._set_permission(value))
            perm_actions.addWidget(button)
        perm_actions.addStretch(1)
        permissions_layout.addLayout(perm_actions)
        self.tabs.addTab(permissions_page, "PERMISSIONS")

        self.jobs_table = QTableWidget(0, 5)
        self.jobs_table.setHorizontalHeaderLabels(["ID", "Titre", "État", "Progression", "Erreur"])
        self.jobs_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.jobs_table, "JOBS")

        self.tasks_table = QTableWidget(0, 5)
        self.tasks_table.setHorizontalHeaderLabels(["ID", "Prompt", "Type", "Valeur", "Actif"])
        self.tasks_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tasks_table, "TASKS")

        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.tabs.addTab(self.activity_text, "ACTIVITY")

        self.workspace_text = QTextEdit()
        self.workspace_text.setReadOnly(True)
        self.tabs.addTab(self.workspace_text, "WORKSPACES")

        self.missions_text = QTextEdit()
        self.missions_text.setReadOnly(True)
        self.tabs.addTab(self.missions_text, "MISSIONS")

        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        self.file_query = QLineEdit()
        self.file_query.setPlaceholderText("Rechercher un fichier indexé…")
        self.file_query.returnPressed.connect(self._search_files)
        files_layout.addWidget(self.file_query)
        file_actions = QHBoxLayout()
        search_button = QPushButton("RECHERCHER")
        search_button.clicked.connect(self._search_files)
        index_button = QPushButton("INDEXER LE WORKSPACE")
        index_button.clicked.connect(self._index_workspace)
        file_actions.addWidget(search_button)
        file_actions.addWidget(index_button)
        file_actions.addStretch(1)
        files_layout.addLayout(file_actions)
        self.file_results = QTextEdit()
        self.file_results.setReadOnly(True)
        files_layout.addWidget(self.file_results)
        self.tabs.addTab(files_page, "FILES")

        settings_page = QWidget()
        settings_form = QFormLayout(settings_page)
        preferences = QSettings("HACKERBOY", "JARVIS")
        self.background_check = QCheckBox()
        self.background_check.setChecked(
            preferences.value("desktop/background", True, type=bool)
        )
        self.notifications_check = QCheckBox()
        self.notifications_check.setChecked(
            preferences.value("desktop/notifications", True, type=bool)
        )
        self.exa_secret = QLineEdit()
        self.exa_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.exa_secret.setPlaceholderText("laisser vide pour ne pas modifier")
        self.groq_secret = QLineEdit()
        self.groq_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_secret.setPlaceholderText("laisser vide pour ne pas modifier")
        self.openrouter_secret = QLineEdit()
        self.openrouter_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_secret.setPlaceholderText("laisser vide pour ne pas modifier")
        settings_form.addRow("Arrière-plan", self.background_check)
        settings_form.addRow("Notifications", self.notifications_check)
        settings_form.addRow("Exa API key", self.exa_secret)
        settings_form.addRow("Groq API key", self.groq_secret)
        settings_form.addRow("OpenRouter API key", self.openrouter_secret)
        save_settings = QPushButton("ENREGISTRER")
        save_settings.clicked.connect(self._save_settings)
        settings_form.addRow("", save_settings)
        self.tabs.addTab(settings_page, "SETTINGS")

        actions = QHBoxLayout()
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(self.refresh)
        stop = QPushButton("STOP GLOBAL")
        stop.setStyleSheet("color:#ff7777; border-color:#ff5757;")
        stop.clicked.connect(self._stop_all)
        actions.addWidget(refresh)
        actions.addWidget(stop)
        actions.addStretch(1)
        close = QPushButton("FERMER")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        health = self.agent.health.snapshot()
        lines = [
            f"ÉTAT GLOBAL : {'HEALTHY' if health['healthy'] else 'DEGRADED'}",
            "",
        ]
        for item in health["checks"]:
            lines.append(
                f"[{'PASS' if item['ok'] else 'FAIL'}] {item['name']}: {item['detail']}"
            )
        self.health_text.setPlainText("\n".join(lines))

        permissions = self.agent.permissions.list()
        self.permissions_table.setRowCount(len(permissions))
        for row, item in enumerate(permissions):
            for col, key in enumerate(("capability", "decision", "source")):
                self.permissions_table.setItem(row, col, QTableWidgetItem(str(item[key])))

        jobs = self.agent.jobs.list(100)
        self.jobs_table.setRowCount(len(jobs))
        for row, item in enumerate(jobs):
            values = (
                item["id"],
                item["title"],
                item["state"],
                f"{float(item.get('progress', 0)) * 100:.0f}%",
                item.get("error") or "",
            )
            for col, value in enumerate(values):
                self.jobs_table.setItem(row, col, QTableWidgetItem(str(value)))

        tasks = self.agent.scheduler.list(100)
        self.tasks_table.setRowCount(len(tasks))
        for row, item in enumerate(tasks):
            values = (
                item.get("id", ""),
                item.get("prompt", ""),
                item.get("schedule_type", ""),
                item.get("schedule_value", ""),
                "YES" if item.get("enabled") else "NO",
            )
            for col, value in enumerate(values):
                self.tasks_table.setItem(row, col, QTableWidgetItem(str(value)))

        activity = self.agent.platform.activity(120)
        self.activity_text.setPlainText(
            "\n".join(
                f"{item['created_at']} · {item['category'].upper()} · "
                f"{item['action']} · {json.dumps(item.get('detail', {}), ensure_ascii=False)}"
                for item in activity
            )
        )

        self.workspace_text.setPlainText(
            json.dumps(self.agent.platform.workspaces(), ensure_ascii=False, indent=2)
        )
        self.missions_text.setPlainText(
            json.dumps(self.agent.platform.missions(), ensure_ascii=False, indent=2)
        )

    def _search_files(self) -> None:
        query = self.file_query.text().strip()
        if not query:
            self.file_results.clear()
            return
        try:
            results = self.agent.file_index.search(query, 80)
        except Exception as exc:
            self.file_results.setPlainText(str(exc))
            return
        self.file_results.setPlainText(
            "\n".join(
                f"{item['name']}\n  {item['path']}"
                for item in results
            ) or "Aucun résultat."
        )

    def _index_workspace(self) -> None:
        def run(ctx):
            ctx.progress(0.1, "Indexation du workspace")
            result = self.agent.file_index.rebuild(
                settings.workspace_root,
                workspace_id="default",
            )
            ctx.progress(1.0, "Indexation terminée")
            return result

        job_id = self.agent.jobs.submit("Indexation fichiers", run)
        QMessageBox.information(
            self,
            "File Index",
            f"Indexation lancée en arrière-plan. Job: {job_id}",
        )
        self.refresh()

    def _save_settings(self) -> None:
        preferences = QSettings("HACKERBOY", "JARVIS")
        preferences.setValue("desktop/background", self.background_check.isChecked())
        preferences.setValue("desktop/notifications", self.notifications_check.isChecked())
        preferences.sync()

        try:
            secrets_store = SecretStore()
            pairs = (
                ("EXA_API_KEY", self.exa_secret.text().strip()),
                ("GROQ_API_KEY", self.groq_secret.text().strip()),
                ("OPENROUTER_API_KEY", self.openrouter_secret.text().strip()),
            )
            for name, value in pairs:
                if value:
                    secrets_store.set(name, value)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Secrets",
                f"Préférences enregistrées, mais Credential Manager est indisponible : {exc}",
            )
            return

        self.exa_secret.clear()
        self.groq_secret.clear()
        self.openrouter_secret.clear()
        QMessageBox.information(
            self,
            "Settings",
            "Réglages enregistrés. Les nouveaux secrets seront pris en compte au prochain démarrage.",
        )

    def _set_permission(self, decision: str) -> None:
        row = self.permissions_table.currentRow()
        if row < 0:
            return
        item = self.permissions_table.item(row, 0)
        if item is None:
            return
        capability = item.text()
        self.agent.permissions.set(capability, decision, scope="always")
        self.agent.platform.log(
            "permission",
            "changed",
            {"capability": capability, "decision": decision, "source": "desktop"},
        )
        self.agent.events.publish(
            "permission.changed",
            {"capability": capability, "decision": decision, "source": "desktop"},
        )
        self.refresh()

    def _stop_all(self) -> None:
        count = self.agent.jobs.cancel_all()
        self.agent.events.publish("core.stop_requested", {"jobs": count, "source": "desktop"})
        self.refresh()
