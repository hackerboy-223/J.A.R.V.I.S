from __future__ import annotations

import re
from pathlib import Path
import tomllib
from typing import Any

from jarvis.config import settings


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")


class SkillManager:
    """Discovers local instruction/pipeline skills without executing bundled scripts."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.skills_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, name: str) -> Path:
        clean = name.strip()
        if not _SAFE_NAME.fullmatch(clean):
            raise ValueError("Nom de skill invalide.")
        path = (self.root / clean).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError("Skill hors du répertoire autorisé.") from exc
        return path

    def _metadata(self, directory: Path) -> dict[str, Any]:
        data: dict[str, Any] = {}
        config = directory / "skill.toml"
        if config.exists():
            try:
                parsed = tomllib.loads(config.read_text(encoding="utf-8"))
                data.update(parsed.get("skill", parsed))
            except Exception:
                pass

        md = directory / "SKILL.md"
        if md.exists() and not data.get("description"):
            text = md.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                value = line.strip().lstrip("#").strip()
                if value:
                    data["description"] = value[:240]
                    break
        return data

    def list(self) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = []
        for directory in sorted(self.root.iterdir()) if self.root.exists() else []:
            if not directory.is_dir():
                continue
            if not ((directory / "SKILL.md").exists() or (directory / "skill.toml").exists()):
                continue
            meta = self._metadata(directory)
            skills.append(
                {
                    "name": directory.name,
                    "description": str(meta.get("description") or directory.name)[:240],
                    "has_instructions": (directory / "SKILL.md").exists(),
                    "has_pipeline": (directory / "skill.toml").exists(),
                }
            )
        return skills

    def catalog(self) -> str:
        entries = self.list()
        if not entries:
            return ""
        lines = ["<available_skills>"]
        for item in entries:
            desc = str(item["description"]).replace('"', "'")
            lines.append(f'  <skill name="{item["name"]}" description="{desc}" />')
        lines.append("</available_skills>")
        return "\n".join(lines)

    def load(self, name: str) -> dict[str, Any]:
        directory = self._dir(name)
        if not directory.exists():
            raise ValueError(f"Skill introuvable : {name}")

        instructions = ""
        md = directory / "SKILL.md"
        if md.exists():
            instructions = md.read_text(encoding="utf-8", errors="replace")[:20000]

        pipeline: dict[str, Any] | None = None
        config = directory / "skill.toml"
        if config.exists():
            pipeline = tomllib.loads(config.read_text(encoding="utf-8"))

        if not instructions and pipeline is None:
            raise ValueError("Le skill ne contient ni SKILL.md ni skill.toml.")

        return {
            "name": directory.name,
            "instructions": instructions,
            "pipeline": pipeline,
            "scripts_executed": False,
        }
