from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class NeuralCoreWidget(QWidget):
    """Native Qt neural/HUD animation for J.A.R.V.I.S."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.setMaximumHeight(300)
        self._phase = 0.0
        self._state = "idle"

        rng = random.Random(0x4A52564953)
        self._nodes: list[tuple[float, float, float]] = []
        for _ in range(56):
            angle = rng.random() * math.tau
            radius = 0.22 + rng.random() * 0.70
            squash = 0.68 + rng.random() * 0.22
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius * squash
            pulse = rng.random() * math.tau
            self._nodes.append((x, y, pulse))

        self._edges: list[tuple[int, int]] = []
        for i, a in enumerate(self._nodes):
            distances: list[tuple[float, int]] = []
            for j, b in enumerate(self._nodes):
                if i == j:
                    continue
                dx = a[0] - b[0]
                dy = a[1] - b[1]
                distances.append((dx * dx + dy * dy, j))
            distances.sort(key=lambda item: item[0])
            for _, j in distances[:2]:
                edge = (min(i, j), max(i, j))
                if edge not in self._edges:
                    self._edges.append(edge)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, state: str) -> None:
        normalized = state.lower()
        if "listen" in normalized:
            self._state = "listening"
        elif "think" in normalized or "traitement" in normalized:
            self._state = "thinking"
        elif "speak" in normalized or "élocution" in normalized:
            self._state = "speaking"
        elif "error" in normalized:
            self._state = "error"
        else:
            self._state = "idle"
        self.update()

    def _tick(self) -> None:
        speed = {
            "idle": 0.022,
            "listening": 0.045,
            "thinking": 0.070,
            "speaking": 0.052,
            "error": 0.018,
        }.get(self._state, 0.022)
        self._phase = (self._phase + speed) % math.tau
        self.update()

    def _palette(self) -> tuple[QColor, QColor]:
        if self._state == "thinking":
            return QColor(255, 194, 82), QColor(255, 225, 160)
        if self._state == "error":
            return QColor(255, 82, 82), QColor(255, 170, 170)
        return QColor(0, 212, 255), QColor(180, 248, 255)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(3, 7, 13))

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0
        scale = min(w, h) * 0.40

        primary, bright = self._palette()
        energy = {
            "idle": 0.34,
            "listening": 0.72,
            "thinking": 0.92,
            "speaking": 0.82,
            "error": 0.48,
        }.get(self._state, 0.34)

        # Faint HUD grid
        grid_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 18))
        grid_pen.setWidthF(1.0)
        painter.setPen(grid_pen)
        step = 28
        x = 0
        while x < self.width():
            painter.drawLine(x, 0, x, self.height())
            x += step
        y = 0
        while y < self.height():
            painter.drawLine(0, y, self.width(), y)
            y += step

        positions: list[QPointF] = []
        for nx, ny, node_phase in self._nodes:
            breathing = 1.0 + math.sin(self._phase * 1.8 + node_phase) * (0.018 + energy * 0.035)
            px = cx + nx * scale * breathing
            py = cy + ny * scale * breathing
            positions.append(QPointF(px, py))

        # Neural links
        link_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), int(38 + energy * 42)))
        link_pen.setWidthF(0.8)
        painter.setPen(link_pen)
        for a, b in self._edges:
            painter.drawLine(positions[a], positions[b])

        # Nodes
        for i, point in enumerate(positions):
            pulse = (math.sin(self._phase * 2.4 + self._nodes[i][2]) + 1.0) / 2.0
            radius = 1.3 + pulse * (1.8 + energy * 1.4)
            alpha = int(110 + pulse * 130)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(bright.red(), bright.green(), bright.blue(), alpha))
            painter.drawEllipse(point, radius, radius)

        # Concentric HUD rings
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for idx, ratio in enumerate((0.38, 0.52, 0.68)):
            ring_alpha = 60 + idx * 18
            pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), ring_alpha))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            radius = scale * ratio * (1.0 + math.sin(self._phase + idx) * 0.025)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Central core
        core_radius = max(26.0, 30.0 + energy * 18.0)
        gradient = QRadialGradient(QPointF(cx, cy), core_radius)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 245))
        gradient.setColorAt(
            0.28,
            QColor(primary.red(), primary.green(), primary.blue(), 230),
        )
        gradient.setColorAt(
            0.70,
            QColor(primary.red(), primary.green(), primary.blue(), 85),
        )
        gradient.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        core_pen = QPen(QColor(bright.red(), bright.green(), bright.blue(), 220))
        core_pen.setWidthF(1.4)
        painter.setPen(core_pen)
        painter.drawEllipse(QPointF(cx, cy), core_radius * 0.58, core_radius * 0.58)

        # Scanner sweep
        sweep_angle = self._phase * 1.6
        sweep_len = scale * 0.78
        sweep = QPointF(
            cx + math.cos(sweep_angle) * sweep_len,
            cy + math.sin(sweep_angle) * sweep_len,
        )
        sweep_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 110))
        sweep_pen.setWidthF(1.0)
        painter.setPen(sweep_pen)
        painter.drawLine(QPointF(cx, cy), sweep)

        painter.end()
