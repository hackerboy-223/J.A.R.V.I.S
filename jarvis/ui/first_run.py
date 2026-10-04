from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from jarvis.config import DATA_DIR, settings
from jarvis.core.permissions import PermissionEngine
from jarvis.core.preferences import Preferences


def _page(title: str, text: str) -> QWizardPage:
    page = QWizardPage()
    page.setTitle(title)
    layout = QVBoxLayout(page)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setMinimumWidth(540)
    layout.addWidget(label)
    return page


def _permission_combo(default: str = "ask") -> QComboBox:
    combo = QComboBox()
    combo.addItem("Demander à chaque fois", "ask")
    combo.addItem("Autoriser", "allow")
    combo.addItem("Interdire", "deny")
    index = combo.findData(default)
    if index >= 0:
        combo.setCurrentIndex(index)
    return combo


class FirstRunWizard(QWizard):
    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.preferences = preferences
        self.permissions = PermissionEngine(settings.database_path)
        self.setWindowTitle("Bienvenue dans J.A.R.V.I.S.")
        self.resize(680, 500)

        self.addPage(
            _page(
                "J.A.R.V.I.S. // Initialisation",
                "Bienvenue. J.A.R.V.I.S. est local-first : les capacités sensibles "
                "sont séparées en permissions explicites et les actions importantes "
                "sont journalisées.",
            )
        )

        permissions_page = QWizardPage()
        permissions_page.setTitle("Permissions initiales")
        permission_layout = QFormLayout(permissions_page)
        intro = QLabel(
            "Choisissez la politique initiale. « Demander » est recommandé : "
            "J.A.R.V.I.S. sollicitera votre accord au moment de l'action."
        )
        intro.setWordWrap(True)
        permission_layout.addRow(intro)

        self.window_permission = _permission_combo("ask")
        self.screen_permission = _permission_combo("ask")
        self.clipboard_permission = _permission_combo("ask")
        self.ui_permission = _permission_combo("ask")
        permission_layout.addRow("Inspecter les fenêtres", self.window_permission)
        permission_layout.addRow("Capturer l'écran", self.screen_permission)
        permission_layout.addRow("Lire le presse-papiers", self.clipboard_permission)
        permission_layout.addRow("Automatisation UI", self.ui_permission)
        self.addPage(permissions_page)

        desktop_page = QWizardPage()
        desktop_page.setTitle("Comportement Desktop")
        desktop_layout = QVBoxLayout(desktop_page)
        self.background = QCheckBox("Garder J.A.R.V.I.S. actif dans le tray après fermeture")
        self.background.setChecked(True)
        self.notifications = QCheckBox("Afficher les notifications de tâches")
        self.notifications.setChecked(True)
        desktop_layout.addWidget(self.background)
        desktop_layout.addWidget(self.notifications)
        desktop_layout.addStretch(1)
        self.addPage(desktop_page)

        self.addPage(
            _page(
                "Données locales",
                f"Workspace : {settings.workspace_root}\n\n"
                f"Données J.A.R.V.I.S. : {DATA_DIR}\n\n"
                "Mémoire SQLite, logs, captures temporaires et mises à jour "
                "restent dans les emplacements locaux du runtime.",
            )
        )

        self.addPage(
            _page(
                "Prêt",
                "Le Core est prêt. Vous pourrez modifier chaque permission, "
                "inspecter les jobs et lancer les diagnostics depuis Control Center.",
            )
        )

    def accept(self) -> None:
        for capability, combo in (
            ("windows.inspect", self.window_permission),
            ("screen.capture", self.screen_permission),
            ("clipboard.read", self.clipboard_permission),
            ("ui.automation", self.ui_permission),
        ):
            self.permissions.set(
                capability,
                str(combo.currentData()),
                "always",
            )
        self.preferences.set("desktop/background_mode", self.background.isChecked())
        self.preferences.set("desktop/notifications", self.notifications.isChecked())
        self.preferences.complete_first_run()
        super().accept()
