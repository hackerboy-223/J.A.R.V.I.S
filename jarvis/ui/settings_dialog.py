from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from jarvis.config import settings
from jarvis.core.preferences import Preferences, SecretStore


def _permission_combo(current: str) -> QComboBox:
    combo = QComboBox()
    combo.addItem("Autoriser", "allow")
    combo.addItem("Demander", "ask")
    combo.addItem("Interdire", "deny")
    index = combo.findData(current)
    combo.setCurrentIndex(index if index >= 0 else 1)
    return combo


class SettingsDialog(QDialog):
    def __init__(self, agent, parent=None) -> None:
        super().__init__(parent)
        self.agent = agent
        self.preferences = Preferences()
        self.secrets = SecretStore()
        self.setWindowTitle("J.A.R.V.I.S. — Réglages")
        self.resize(560, 380)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.background = QCheckBox("Garder J.A.R.V.I.S. actif dans la zone de notification")
        self.background.setChecked(self.preferences.get_bool("desktop/background_mode", True))
        form.addRow("Arrière-plan", self.background)

        self.notifications = QCheckBox("Afficher les notifications de fin de tâche")
        self.notifications.setChecked(self.preferences.get_bool("desktop/notifications", True))
        form.addRow("Notifications", self.notifications)

        self.auto_updates = QCheckBox("Vérifier automatiquement les nouvelles releases")
        self.auto_updates.setChecked(self.preferences.get_bool("desktop/auto_update_check", True))
        form.addRow("Mises à jour", self.auto_updates)

        self.pc_permission = _permission_combo(
            self.agent.runtime.permissions.get("pc.control")
        )
        self.screen_permission = _permission_combo(
            self.agent.runtime.permissions.get("screen.capture")
        )
        self.clipboard_permission = _permission_combo(
            self.agent.runtime.permissions.get("clipboard.read")
        )
        self.ui_permission = _permission_combo(
            self.agent.runtime.permissions.get("ui.automation")
        )
        form.addRow("Contrôle PC", self.pc_permission)
        form.addRow("Capture écran", self.screen_permission)
        form.addRow("Lecture clipboard", self.clipboard_permission)
        form.addRow("Automatisation UI", self.ui_permission)

        form.addRow("Workspace", QLabel(str(settings.workspace_root)))
        form.addRow("Données", QLabel(str(settings.database_path.parent)))
        form.addRow(
            "Secrets",
            QLabel(
                "Windows Credential Manager disponible"
                if self.secrets.available()
                else "Backend sécurisé indisponible"
            ),
        )
        root.addLayout(form)

        note = QLabel(
            "Les réglages sensibles ci-dessus modifient directement le PermissionEngine. "
            "Les paramètres fournisseur/modèle restent compatibles avec .env pendant "
            "la migration vers un Core unique."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8fb6c2; padding:8px;")
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _save(self) -> None:
        self.preferences.set("desktop/background_mode", self.background.isChecked())
        self.preferences.set("desktop/notifications", self.notifications.isChecked())
        self.preferences.set("desktop/auto_update_check", self.auto_updates.isChecked())

        for capability, combo in (
            ("pc.control", self.pc_permission),
            ("screen.capture", self.screen_permission),
            ("clipboard.read", self.clipboard_permission),
            ("ui.automation", self.ui_permission),
        ):
            self.agent.runtime.permissions.set(
                capability,
                str(combo.currentData()),
                "always",
            )
            self.agent.runtime.events.emit(
                "permission.changed",
                {
                    "capability": capability,
                    "decision": str(combo.currentData()),
                    "scope": "always",
                },
            )
        self.accept()
