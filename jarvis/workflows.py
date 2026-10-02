from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from jarvis.core.llm import LLMClient


ProgressFn = Callable[[str], None]


@dataclass
class WorkflowResult:
    mode: str
    answer: str
    notes: list[str]


class WorkflowEngine:
    """Open-JARVIS-inspired collaboration workflows using the configured LLM."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def _simple_call(self, system: str, prompt: str) -> str:
        result = self.llm.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            tools=None,
        )
        message = result.get("message") or {}
        return str(message.get("content") or "").strip()

    def parallel(self, task: str, progress: ProgressFn | None = None) -> WorkflowResult:
        progress = progress or (lambda _: None)
        roles = [
            ("analyste", "Analyse la demande, les hypothèses et les risques."),
            ("ingénieur", "Cherche une solution pratique, faisable et technique."),
            ("critique", "Cherche les failles, oublis et améliorations possibles."),
        ]

        notes: list[str] = []
        progress("PARALLEL · 3 AGENTS")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(
                    self._simple_call,
                    f"Tu es l'agent {name}. {instruction}",
                    task,
                ): name
                for name, instruction in roles
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    text = future.result()
                except Exception as exc:
                    text = f"Erreur {name}: {exc}"
                notes.append(f"{name.upper()}: {text}")
                progress(f"PARALLEL · {name.upper()} TERMINÉ")

        synthesis_prompt = (
            f"Tâche initiale :\n{task}\n\n"
            + "\n\n".join(notes)
            + "\n\nSynthétise une réponse finale claire, cohérente et directement utile."
        )
        answer = self._simple_call(
            "Tu es J.A.R.V.I.S., synthétiseur principal. Résous les désaccords sans inventer.",
            synthesis_prompt,
        )
        return WorkflowResult("parallel", answer, notes)

    def sequential(self, task: str, progress: ProgressFn | None = None) -> WorkflowResult:
        progress = progress or (lambda _: None)
        stages = [
            ("PLAN", "Décompose la tâche en étapes et contraintes concrètes."),
            ("BUILD", "À partir du plan, propose la solution détaillée."),
            ("REVIEW", "Relis la solution, corrige les erreurs et simplifie ce qui peut l'être."),
        ]

        current = task
        notes: list[str] = []
        for label, instruction in stages:
            progress(f"SEQUENTIAL · {label}")
            current = self._simple_call(
                f"Tu es l'étape {label}. {instruction}",
                f"Demande originale :\n{task}\n\nEntrée de l'étape :\n{current}",
            )
            notes.append(f"{label}: {current}")

        return WorkflowResult("sequential", current, notes)

    def debate(self, task: str, progress: ProgressFn | None = None) -> WorkflowResult:
        progress = progress or (lambda _: None)
        progress("DEBATE · OUVERTURE")
        position_a = self._simple_call(
            "Défends la solution A avec arguments techniques solides.",
            task,
        )
        position_b = self._simple_call(
            "Cherche une solution alternative ou contradictoire, avec arguments techniques solides.",
            task,
        )

        progress("DEBATE · RÉFUTATION")
        rebuttal_a = self._simple_call(
            "Réponds aux objections et améliore la première position.",
            f"Tâche: {task}\nPosition A: {position_a}\nPosition B: {position_b}",
        )
        rebuttal_b = self._simple_call(
            "Réponds aux objections et améliore la seconde position.",
            f"Tâche: {task}\nPosition A: {position_a}\nPosition B: {position_b}",
        )

        progress("DEBATE · VERDICT")
        notes = [
            f"A: {position_a}",
            f"B: {position_b}",
            f"A2: {rebuttal_a}",
            f"B2: {rebuttal_b}",
        ]
        answer = self._simple_call(
            "Tu es le juge technique. Synthétise les meilleurs éléments sans faire de faux compromis.",
            f"Tâche: {task}\n\n" + "\n\n".join(notes),
        )
        return WorkflowResult("debate", answer, notes)
