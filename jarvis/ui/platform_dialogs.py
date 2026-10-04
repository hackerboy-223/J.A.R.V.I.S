from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
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
