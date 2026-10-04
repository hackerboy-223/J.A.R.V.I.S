from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from jarvis.config import DATA_DIR, settings
from jarvis.core.preferences import Preferences


def _page(title: str, text: str) -> QWizardPage:
    page = QWizardPage()
    page.setTitle(title)
    layout = QVBoxLayout(page)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setMinimumWidth(520)
    layout.addWidget(label)
    return page


class FirstRunWizard(QWizard):
    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.preferences = preferences
        self.setWindowTitle("Bienvenue dans J.A.R.V.I.S.")
        self.resize(640, 430)

        self.addPage(
            _page(
                "J.A.R.V.I.S. // Initialisation",
                "Bienvenue. Ce wizard prépare le runtime local. "
                "J.A.R.V.I.S. est conçu pour rester local-first et pour demander "
                "des permissions avant les actions sensibles.",
            )
        )
        self.addPage(
            _page(
                "Permissions",
                "Les lectures système et la mémoire locale peuvent être autorisées. "
                "Écran, clipboard, modifications de fichiers, UI Automation, MCP "
                "et tâches mutantes peuvent rester sur DEMANDER ou INTERDIRE. "
                "Vous pourrez changer chaque capacité dans Control Center.",
            )
        )
        self.addPage(
            _page(
                "Données locales",
                f"Workspace : {settings.workspace_root}\n\n"
                f"Données J.A.R.V.I.S. : {DATA_DIR}\n\n"
                "Les captures temporaires, logs, mémoire SQLite et futures mises à jour "
                "restent dans les emplacements locaux du runtime.",
            )
        )
        self.addPage(
            _page(
                "Prêt",
                "Le cœur est prêt. Au premier démarrage, testez Health Center, "
                "le microphone et les permissions avant d'activer davantage de pouvoirs.",
            )
        )

    def accept(self) -> None:
        self.preferences.complete_first_run()
        super().accept()
