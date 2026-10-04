from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from jarvis.config import settings


class FirstRunWizard(QWizard):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bienvenue dans J.A.R.V.I.S.")
        self.resize(700, 480)

        welcome = QWizardPage()
        welcome.setTitle("J.A.R.V.I.S. PLATFORM")
        layout = QVBoxLayout(welcome)
        layout.addWidget(
            QLabel(
                "Ce wizard configure uniquement les préférences locales. "
                "Aucune permission sensible n'est accordée automatiquement."
            )
        )
        self.addPage(welcome)

        workspace = QWizardPage()
        workspace.setTitle("Workspace")
        workspace_layout = QVBoxLayout(workspace)
        self.workspace_edit = QLineEdit(str(settings.workspace_root))
        workspace_layout.addWidget(QLabel("Dossier de travail autorisé :"))
        workspace_layout.addWidget(self.workspace_edit)
        self.addPage(workspace)

        behavior = QWizardPage()
        behavior.setTitle("Comportement desktop")
        behavior_layout = QVBoxLayout(behavior)
        self.background = QCheckBox("Continuer en arrière-plan quand la fenêtre est fermée")
        self.background.setChecked(True)
        self.notifications = QCheckBox("Afficher les notifications locales")
        self.notifications.setChecked(True)
        behavior_layout.addWidget(self.background)
        behavior_layout.addWidget(self.notifications)
        self.addPage(behavior)

        safety = QWizardPage()
        safety.setTitle("Permissions")
        safety_layout = QVBoxLayout(safety)
        safety_layout.addWidget(
            QLabel(
                "Les captures d'écran, le presse-papiers en lecture, les modifications "
                "de fichiers et les actions UI restent sur ASK par défaut."
            )
        )
        self.addPage(safety)

    def accept(self) -> None:
        store = QSettings("HACKERBOY", "JARVIS")
        store.setValue("setup/complete", True)
        store.setValue("workspace/root", self.workspace_edit.text().strip())
        store.setValue("desktop/background", self.background.isChecked())
        store.setValue("desktop/notifications", self.notifications.isChecked())
        store.sync()
        super().accept()


def setup_completed() -> bool:
    return bool(QSettings("HACKERBOY", "JARVIS").value("setup/complete", False, type=bool))
