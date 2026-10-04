from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from jarvis.config import settings
from jarvis.core.preferences import Preferences, SecretStore


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.preferences = Preferences()
        self.secrets = SecretStore()
        self.setWindowTitle("J.A.R.V.I.S. — Réglages")
        self.resize(520, 320)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.background = QCheckBox("Garder J.A.R.V.I.S. actif dans la zone de notification")
        self.background.setChecked(self.preferences.get_bool("desktop/background_mode", True))
        form.addRow("Arrière-plan", self.background)

        self.notifications = QCheckBox("Afficher les notifications de fin de tâche")
        self.notifications.setChecked(self.preferences.get_bool("desktop/notifications", True))
        form.addRow("Notifications", self.notifications)

        self.confirm_safe = QCheckBox("Demander une confirmation supplémentaire pour les actions PC réversibles")
        self.confirm_safe.setChecked(
            self.preferences.get_bool(
                "security/confirm_safe_pc_actions",
                settings.confirm_safe_pc_actions,
            )
        )
        form.addRow("Actions PC", self.confirm_safe)

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
            "Les permissions détaillées se règlent dans Control Center. "
            "Les paramètres fournisseur/modèle restent compatibles avec .env pendant l'unification du Core."
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
        self.preferences.set(
            "security/confirm_safe_pc_actions",
            self.confirm_safe.isChecked(),
        )
        self.accept()
