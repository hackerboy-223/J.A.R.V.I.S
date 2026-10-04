from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jarvis.core.diagnostics import export_diagnostic_bundle, health_snapshot


def _table(headers: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.horizontalHeader().setStretchLastSection(True)
    return widget


class SystemCenterDialog(QDialog):
    def __init__(self, agent, parent=None, on_activate_mission=None) -> None:
        super().__init__(parent)
        self.agent = agent
        self.on_activate_mission = on_activate_mission
        self.setWindowTitle("J.A.R.V.I.S. — Control Center")
        self.resize(920, 620)

        root = QVBoxLayout(self)
        title = QLabel("CONTROL CENTER · permissions, jobs, activité, santé et missions")
        title.setStyleSheet("font-weight:700; color:#00d4ff; padding:6px;")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.permissions_table = _table(["Capability", "Decision"])
        self.jobs_table = _table(["ID", "État", "Type", "Progression", "Tâche"])
        self.activity_table = _table(["Date", "Catégorie", "Action", "État", "Résumé"])
        self.schedule_table = _table(["ID", "Actif", "Type", "Prochaine", "Instruction"])
        self.health_table = _table(["Composant", "État", "Détail"])
        self.missions_table = _table(["ID", "Titre", "État", "Mode", "Mise à jour"])
        self.workspaces_table = _table(["ID", "Nom", "Favori", "Chemin"])
        self.recent_files_table = _table(["Date", "Action", "Fichier"])

        self.tabs.addTab(self._permission_tab(), "Permissions")
        self.tabs.addTab(self._simple_tab(self.jobs_table, self._refresh_jobs, self._cancel_job), "Jobs")
        self.tabs.addTab(self._schedule_tab(), "Tasks")
        self.tabs.addTab(self._simple_tab(self.activity_table, self._refresh_activity), "Activity")
        self.tabs.addTab(self._simple_tab(self.health_table, self._refresh_health, self._export_diagnostics, "EXPORTER DIAGNOSTICS"), "Health")
        self.tabs.addTab(self._mission_tab(), "Missions")
        self.tabs.addTab(self._simple_tab(self.workspaces_table, self._refresh_workspaces), "Workspaces")
        self.tabs.addTab(self._simple_tab(self.recent_files_table, self._refresh_recent_files), "Recent Files")

        close = QPushButton("FERMER")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh_all()

    def _simple_tab(self, table, refresh_fn, action_fn=None, action_label: str = "ANNULER LE JOB") -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(refresh_fn)
        actions.addWidget(refresh)
        if action_fn is not None:
            action = QPushButton(action_label)
            action.clicked.connect(action_fn)
            actions.addWidget(action)
        actions.addStretch(1)
        layout.addLayout(actions)
        return page

    def _schedule_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.schedule_table, 1)
        actions = QHBoxLayout()
        for label, callback in (
            ("PAUSE", self._pause_schedule),
            ("REPRENDRE", self._resume_schedule),
            ("ANNULER", self._cancel_schedule),
            ("ACTUALISER", self._refresh_schedule),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return page

    def _mission_tab(self) -> QWidget:
        return self._simple_tab(
            self.missions_table,
            self._refresh_missions,
            self._activate_mission,
            "ACTIVER LA MISSION",
        )

    def _permission_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.permissions_table, 1)
        actions = QHBoxLayout()
        for label, decision in (("AUTORISER", "allow"), ("DEMANDER", "ask"), ("INTERDIRE", "deny")):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=decision: self._set_permission(value))
            actions.addWidget(button)
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(self._refresh_permissions)
        actions.addWidget(refresh)
        actions.addStretch(1)
        layout.addLayout(actions)
        return page

    @staticmethod
    def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row):
                table.setItem(row_index, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()

    def _selected_value(self, table: QTableWidget, column: int = 0) -> str | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, column)
        return item.text() if item is not None else None

    def _set_permission(self, decision: str) -> None:
        capability = self._selected_value(self.permissions_table)
        if not capability:
            QMessageBox.information(self, "Permissions", "Sélectionnez une capacité.")
            return
        self.agent.runtime.permissions.set(capability, decision, "always")
        self.agent.runtime.events.emit(
            "permission.changed",
            {"capability": capability, "decision": decision, "scope": "always"},
        )
        self._refresh_permissions()

    def _cancel_job(self) -> None:
        job_id = self._selected_value(self.jobs_table)
        if not job_id:
            QMessageBox.information(self, "Jobs", "Sélectionnez un job.")
            return
        self.agent.runtime.jobs.cancel(job_id)
        self._refresh_jobs()

    def _selected_schedule(self) -> str | None:
        return self._selected_value(self.schedule_table)

    def _pause_schedule(self) -> None:
        task_id = self._selected_schedule()
        if task_id:
            self.agent.scheduler.pause(task_id)
            self._refresh_schedule()

    def _resume_schedule(self) -> None:
        task_id = self._selected_schedule()
        if task_id:
            self.agent.scheduler.resume(task_id)
            self._refresh_schedule()

    def _cancel_schedule(self) -> None:
        task_id = self._selected_schedule()
        if task_id:
            answer = QMessageBox.question(
                self,
                "Tâche planifiée",
                "Annuler définitivement cette tâche ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.agent.scheduler.cancel(task_id)
                self._refresh_schedule()

    def _activate_mission(self) -> None:
        mission_id = self._selected_value(self.missions_table)
        if mission_id and self.on_activate_mission is not None:
            self.on_activate_mission(mission_id)

    def _refresh_permissions(self) -> None:
        rows = [
            [item["capability"], item["decision"].upper()]
            for item in self.agent.runtime.permissions.effective()
        ]
        self._fill(self.permissions_table, rows)

    def _refresh_jobs(self) -> None:
        rows = []
        for item in self.agent.runtime.jobs.list(100):
            progress = item.get("progress")
            progress_text = "—" if progress is None else f"{float(progress) * 100:.0f}%"
            rows.append([
                str(item.get("id", "")),
                str(item.get("status", "")),
                str(item.get("kind", "")),
                progress_text,
                str(item.get("label", "")),
            ])
        self._fill(self.jobs_table, rows)

    def _refresh_schedule(self) -> None:
        rows = []
        for item in self.agent.scheduler.list(100):
            rows.append([
                str(item.get("id", "")),
                "OUI" if item.get("enabled") else "NON",
                str(item.get("schedule_type", "")),
                str(item.get("next_run_at", "") or "—"),
                str(item.get("prompt", "")),
            ])
        self._fill(self.schedule_table, rows)

    def _refresh_activity(self) -> None:
        rows = [
            [
                str(item.get("created_at", "")),
                str(item.get("category", "")),
                str(item.get("action", "")),
                str(item.get("status", "")),
                str(item.get("summary", "")),
            ]
            for item in self.agent.runtime.activity.recent(150)
        ]
        self._fill(self.activity_table, rows)

    def _export_diagnostics(self) -> None:
        try:
            path = export_diagnostic_bundle()
        except Exception as exc:
            QMessageBox.critical(self, "Diagnostics", str(exc))
            return
        QMessageBox.information(
            self,
            "Diagnostics",
            f"Bundle créé :\n{path}\n\nAucun .env ou secret n'est inclus.",
        )

    def _refresh_health(self) -> None:
        running = bool(
            self.agent.scheduler._thread is not None
            and self.agent.scheduler._thread.is_alive()
        )
        snapshot = health_snapshot(
            scheduler_running=running,
            extra_checks={
                "skills": lambda: len(self.agent.skills.list()),
                "mcp": lambda: len(self.agent.mcp.list_servers()),
            },
        )
        rows = []
        for name, item in snapshot["checks"].items():
            detail = item.get("detail")
            if detail is None:
                detail = {
                    key: value for key, value in item.items() if key != "ok"
                }
            rows.append([name, "OK" if item.get("ok") else "ERREUR", str(detail)])
        self._fill(self.health_table, rows)

    def _refresh_missions(self) -> None:
        rows = [
            [
                str(item.get("id", "")),
                str(item.get("title", "")),
                str(item.get("status", "")),
                str(item.get("mode", "")),
                str(item.get("updated_at", "")),
            ]
            for item in self.agent.runtime.missions.list(100)
        ]
        self._fill(self.missions_table, rows)

    def _refresh_workspaces(self) -> None:
        rows = [
            [
                str(item.get("id", "")),
                str(item.get("name", "")),
                "★" if item.get("favorite") else "",
                str(item.get("root_path", "")),
            ]
            for item in self.agent.runtime.workspaces.list(100)
        ]
        self._fill(self.workspaces_table, rows)

    def _refresh_recent_files(self) -> None:
        rows = [
            [
                str(item.get("last_used_at", "")),
                str(item.get("action", "")),
                str(item.get("path", "")),
            ]
            for item in self.agent.runtime.recent_files.list(100)
        ]
        self._fill(self.recent_files_table, rows)

    def refresh_all(self) -> None:
        self._refresh_permissions()
        self._refresh_jobs()
        self._refresh_schedule()
        self._refresh_activity()
        self._refresh_health()
        self._refresh_missions()
        self._refresh_workspaces()
        self._refresh_recent_files()
