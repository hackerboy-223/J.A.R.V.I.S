from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jarvis.tools.screen import screen_capture, screen_monitors
from jarvis.tools.windows import list_windows, window_action


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            table.setItem(row_index, column, QTableWidgetItem(value))
    table.resizeColumnsToContents()


def _selected(table: QTableWidget, column: int = 0) -> str | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, column)
    return item.text() if item is not None else None


class ChangesPanel(QWidget):
    def __init__(self, agent, parent=None) -> None:
        super().__init__(parent)
        self.agent = agent

        root = QVBoxLayout(self)
        self.table = _table(["ID", "Date", "Annulé", "Fichier"])
        root.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(self.refresh)
        preview = QPushButton("VOIR LE DIFF")
        preview.clicked.connect(self.preview)
        undo = QPushButton("ANNULER LA MODIFICATION")
        undo.clicked.connect(self.undo)
        buttons.addWidget(refresh)
        buttons.addWidget(preview)
        buttons.addWidget(undo)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        rows = [
            [
                str(item.get("id", "")),
                str(item.get("created_at", "")),
                "OUI" if item.get("undone") else "NON",
                str(item.get("path", "")),
            ]
            for item in self.agent.runtime.changes.recent(100)
        ]
        _fill(self.table, rows)

    def preview(self) -> None:
        change_id = _selected(self.table)
        if not change_id:
            QMessageBox.information(self, "Diff", "Sélectionnez une modification.")
            return
        try:
            diff = self.agent.runtime.changes.diff_for(change_id)
        except Exception as exc:
            QMessageBox.critical(self, "Diff", str(exc))
            return

        details = QPlainTextEdit(diff or "(aucune différence textuelle)")
        details.setReadOnly(True)
        details.setMinimumSize(820, 440)

        # QMessageBox does not expose a public custom-body API, so use a simple dialog-like child.
        preview_window = QWidget()
        layout = QVBoxLayout(preview_window)
        layout.addWidget(details)
        preview_window.setWindowTitle("J.A.R.V.I.S. — Diff")
        preview_window.resize(880, 520)
        preview_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        preview_window.show()
        self._preview_window = preview_window

    def undo(self) -> None:
        change_id = _selected(self.table)
        if not change_id:
            QMessageBox.information(self, "Undo", "Sélectionnez une modification.")
            return
        allowed = self.agent.runtime.permissions.authorize(
            "files.undo",
            f"Annuler la modification {change_id} ?",
            lambda reason: QMessageBox.question(
                self,
                "Autorisation J.A.R.V.I.S.",
                reason,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes,
        )
        if not allowed:
            return
        try:
            result = self.agent.runtime.changes.undo(change_id)
        except Exception as exc:
            QMessageBox.critical(self, "Undo", str(exc))
            return
        self.agent.runtime.activity.log(
            "file",
            "undo",
            summary=str(result.get("path", "")),
            details=result,
        )
        self.agent.runtime.events.emit("file.undone", result)
        self.refresh()


class FileSearchPanel(QWidget):
    def __init__(self, agent, parent=None) -> None:
        super().__init__(parent)
        self.agent = agent

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.workspace = QComboBox()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Rechercher un fichier ou un chemin…")
        self.query.returnPressed.connect(self.search)
        search = QPushButton("RECHERCHER")
        search.clicked.connect(self.search)
        index = QPushButton("INDEXER LE WORKSPACE")
        index.clicked.connect(self.index_workspace)
        header.addWidget(self.workspace)
        header.addWidget(self.query, 1)
        header.addWidget(search)
        header.addWidget(index)
        root.addLayout(header)

        self.table = _table(["Workspace", "Nom", "Extension", "Taille", "Chemin"])
        root.addWidget(self.table, 1)
        self.refresh_workspaces()

    def refresh_workspaces(self) -> None:
        current = self.workspace.currentData()
        self.workspace.clear()
        self.workspace.addItem("Tous les index", "")
        for item in self.agent.runtime.workspaces.list(100):
            self.workspace.addItem(str(item.get("name", "")), str(item.get("id", "")))
        index = self.workspace.findData(current)
        if index >= 0:
            self.workspace.setCurrentIndex(index)

    def search(self) -> None:
        query = self.query.text().strip()
        if not query:
            return
        workspace_id = str(self.workspace.currentData() or "").strip() or None
        try:
            results = self.agent.runtime.file_index.search(
                query,
                workspace_id=workspace_id,
                limit=150,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Recherche fichiers", str(exc))
            return
        _fill(
            self.table,
            [
                [
                    str(item.get("workspace_id", "")),
                    str(item.get("name", "")),
                    str(item.get("extension", "")),
                    str(item.get("size", "")),
                    str(item.get("path", "")),
                ]
                for item in results
            ],
        )

    def index_workspace(self) -> None:
        workspace_id = str(self.workspace.currentData() or "").strip()
        if not workspace_id:
            QMessageBox.information(
                self,
                "Indexation",
                "Sélectionnez un workspace précis avant l'indexation.",
            )
            return

        workspace = self.agent.runtime.workspaces.get(workspace_id)
        if workspace is None:
            return
        allowed = self.agent.runtime.permissions.authorize(
            "files.index",
            f"Indexer les noms et chemins du workspace « {workspace.get('name', workspace_id)} » ?",
            lambda reason: QMessageBox.question(
                self,
                "Autorisation J.A.R.V.I.S.",
                reason,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes,
        )
        if not allowed:
            return

        try:
            result = self.agent.runtime.file_index.index_workspace(
                workspace_id,
                str(workspace["root_path"]),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Indexation", str(exc))
            return
        self.agent.runtime.activity.log(
            "files",
            "index",
            summary=f"{result['indexed']} fichier(s) indexé(s)",
            details=result,
        )
        QMessageBox.information(
            self,
            "Indexation",
            f"{result['indexed']} fichier(s) indexé(s).",
        )


class DesktopPanel(QWidget):
    def __init__(self, agent, parent=None) -> None:
        super().__init__(parent)
        self.agent = agent

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Fenêtres visibles"))
        self.windows = _table(["Handle", "PID", "Process", "Titre"])
        root.addWidget(self.windows, 2)

        actions = QHBoxLayout()
        refresh = QPushButton("ACTUALISER")
        refresh.clicked.connect(self.refresh_windows)
        focus = QPushButton("FOCUS")
        focus.clicked.connect(lambda: self.window_action("focus"))
        minimize = QPushButton("MINIMISER")
        minimize.clicked.connect(lambda: self.window_action("minimize"))
        restore = QPushButton("RESTAURER")
        restore.clicked.connect(lambda: self.window_action("restore"))
        actions.addWidget(refresh)
        actions.addWidget(focus)
        actions.addWidget(minimize)
        actions.addWidget(restore)
        actions.addStretch(1)
        root.addLayout(actions)

        root.addWidget(QLabel("Écrans"))
        self.monitors = _table(["Index", "Global", "Left", "Top", "Largeur", "Hauteur"])
        root.addWidget(self.monitors, 1)

        screen_actions = QHBoxLayout()
        monitor_refresh = QPushButton("ACTUALISER ÉCRANS")
        monitor_refresh.clicked.connect(self.refresh_monitors)
        capture = QPushButton("CAPTURER L'ÉCRAN SÉLECTIONNÉ")
        capture.clicked.connect(self.capture_monitor)
        screen_actions.addWidget(monitor_refresh)
        screen_actions.addWidget(capture)
        screen_actions.addStretch(1)
        root.addLayout(screen_actions)

        self.refresh_monitors()

    def _confirm(self, capability: str, reason: str) -> bool:
        return self.agent.runtime.permissions.authorize(
            capability,
            reason,
            lambda text: QMessageBox.question(
                self,
                "Autorisation J.A.R.V.I.S.",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes,
        )

    def refresh_windows(self) -> None:
        if not self._confirm("windows.inspect", "Lister les fenêtres visibles ?"):
            return
        try:
            result = list_windows({"limit": 150})
        except Exception as exc:
            QMessageBox.critical(self, "Fenêtres", str(exc))
            return
        _fill(
            self.windows,
            [
                [
                    str(item.get("handle", "")),
                    str(item.get("pid", "")),
                    str(item.get("process", "")),
                    str(item.get("title", "")),
                ]
                for item in result.get("windows", [])
            ],
        )

    def window_action(self, action: str) -> None:
        handle = _selected(self.windows)
        if not handle:
            return
        if not self._confirm("windows.focus", f"{action} la fenêtre {handle} ?"):
            return
        try:
            result = window_action({"action": action, "handle": int(handle)})
        except Exception as exc:
            QMessageBox.critical(self, "Fenêtres", str(exc))
            return
        self.agent.runtime.activity.log(
            "desktop",
            f"window.{action}",
            summary=str(handle),
            details=result,
        )
        self.refresh_windows()

    def refresh_monitors(self) -> None:
        try:
            result = screen_monitors({})
        except Exception as exc:
            QMessageBox.critical(self, "Écrans", str(exc))
            return
        _fill(
            self.monitors,
            [
                [
                    str(item.get("index", "")),
                    "OUI" if item.get("all_monitors") else "NON",
                    str(item.get("left", "")),
                    str(item.get("top", "")),
                    str(item.get("width", "")),
                    str(item.get("height", "")),
                ]
                for item in result.get("monitors", [])
            ],
        )

    def capture_monitor(self) -> None:
        index = _selected(self.monitors)
        if index is None:
            return
        if not self._confirm("screen.capture", f"Capturer l'écran {index} ?"):
            return
        try:
            result = screen_capture({"monitor": int(index), "persist": False})
        except Exception as exc:
            QMessageBox.critical(self, "Capture écran", str(exc))
            return
        self.agent.runtime.activity.log(
            "desktop",
            "screen.capture",
            summary=str(result.get("path", "")),
            details=result,
        )
        QMessageBox.information(
            self,
            "Capture écran",
            f"Capture temporaire créée :\n{result.get('path', '')}",
        )
