from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from jarvis.config import settings
from jarvis.core.secrets import SecretStore


class FirstRunWizard(QWizard):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bienvenue dans J.A.R.V.I.S.")
        self.resize(700, 560)

        welcome = QWizardPage()
        welcome.setTitle("J.A.R.V.I.S. PLATFORM")
        layout = QVBoxLayout(welcome)
        layout.addWidget(
            QLabel(
                "Configuration locale initiale. Les clés API sont facultatives et, "
                "si tu en fournis, elles sont stockées dans le gestionnaire de "
                "credentials du système — jamais dans QSettings ou dans le dépôt."
            )
        )
        self.addPage(welcome)

        workspace = QWizardPage()
        workspace.setTitle("Workspace")
        workspace_layout = QVBoxLayout(workspace)
        self.workspace_edit = QLineEdit(str(settings.workspace_root))
        workspace_layout.addWidget(QLabel("Dossier de travail autorisé :"))
        workspace_layout.addWidget(self.workspace_edit)
        workspace_layout.addWidget(
            QLabel(
                "J.A.R.V.I.S. limitera ses outils fichiers à ce dossier. "
                "Le dossier sera créé s'il n'existe pas."
            )
        )
        self.addPage(workspace)

        providers = QWizardPage()
        providers.setTitle("Providers IA et outils web (facultatif)")
        providers_layout = QVBoxLayout(providers)
        providers_layout.addWidget(
            QLabel(
                "Tu peux laisser tous les champs vides et les configurer plus tard "
                "dans Platform > Settings."
            )
        )

        self.openrouter_secret = self._secret_input("OpenRouter API key")
        self.groq_secret = self._secret_input("Groq API key (transcription)")
        self.exa_secret = self._secret_input("Exa API key (recherche web)")
        self.hf_secret = self._secret_input("Hugging Face token")

        for label, field in (
            ("OpenRouter", self.openrouter_secret),
            ("Groq", self.groq_secret),
            ("Exa", self.exa_secret),
            ("Hugging Face", self.hf_secret),
        ):
            providers_layout.addWidget(QLabel(label))
            providers_layout.addWidget(field)
        self.addPage(providers)

        behavior = QWizardPage()
        behavior.setTitle("Comportement desktop")
        behavior_layout = QVBoxLayout(behavior)
        self.background = QCheckBox(
            "Continuer en arrière-plan quand la fenêtre est fermée"
        )
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
                "de fichiers, le scheduler, MCP et les actions UI restent sur ASK "
                "par défaut. Le contrôle PC distribué reste désactivé par défaut."
            )
        )
        self.addPage(safety)

    @staticmethod
    def _secret_input(placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    def _workspace(self) -> Path | None:
        raw = self.workspace_edit.text().strip()
        if not raw:
            QMessageBox.warning(
                self,
                "Workspace",
                "Choisis un dossier de travail pour J.A.R.V.I.S.",
            )
            return None

        try:
            path = Path(raw).expanduser().resolve()
            if path.exists() and not path.is_dir():
                raise ValueError("Le chemin existe mais n'est pas un dossier.")
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Workspace",
                f"Impossible de préparer le workspace : {exc}",
            )
            return None
        return path

    def _store_secrets(self) -> bool:
        pairs = (
            ("OPENROUTER_API_KEY", self.openrouter_secret.text().strip(), "llm_api_key"),
            ("GROQ_API_KEY", self.groq_secret.text().strip(), "groq_api_key"),
            ("EXA_API_KEY", self.exa_secret.text().strip(), "exa_api_key"),
            ("HF_TOKEN", self.hf_secret.text().strip(), "hf_token"),
        )
        supplied = [(name, value, attr) for name, value, attr in pairs if value]
        if not supplied:
            return True

        try:
            store = SecretStore()
            for name, value, attr in supplied:
                store.set(name, value)
                # settings is intentionally updated in-place so modules that already
                # imported it see the first-run values immediately.
                object.__setattr__(settings, attr, value)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Credential Manager",
                "Les clés n'ont pas été enregistrées. "
                f"Le gestionnaire de credentials est indisponible : {exc}",
            )
            return False

        return True

    def accept(self) -> None:
        workspace = self._workspace()
        if workspace is None:
            return
        if not self._store_secrets():
            return

        store = QSettings("HACKERBOY", "JARVIS")
        store.setValue("workspace/root", str(workspace))
        store.setValue("desktop/background", self.background.isChecked())
        store.setValue("desktop/notifications", self.notifications.isChecked())
        store.setValue("setup/complete", True)
        store.sync()

        object.__setattr__(settings, "workspace_root", workspace)
        super().accept()


def setup_completed() -> bool:
    return bool(
        QSettings("HACKERBOY", "JARVIS").value(
            "setup/complete",
            False,
            type=bool,
        )
    )
