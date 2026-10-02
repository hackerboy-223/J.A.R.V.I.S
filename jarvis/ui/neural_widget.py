from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


@dataclass
class Pulse:
    edge: int
    progress: float
    speed: float
    outward: bool


@dataclass
class Particle:
    angle: float
    radius: float
    speed: float
    alpha: float
    size: float


class NeuralCoreWidget(QWidget):
    """High-energy native Qt neural/HUD renderer for J.A.R.V.I.S."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(360)
        self.setMaximumHeight(560)

        self._phase = 0.0
        self._state = "idle"
        self._audio_target = 0.0
        self._audio_level = 0.0
        self._last_state = "idle"

        rng = random.Random(0x4A4152564953)

        # 3D neural cloud
        self._nodes: list[tuple[float, float, float, float]] = []
        while len(self._nodes) < 92:
            x = rng.uniform(-1.0, 1.0)
            y = rng.uniform(-0.72, 0.72)
            z = rng.uniform(-0.85, 0.85)
            if x * x + (y / 0.72) ** 2 + (z / 0.85) ** 2 > 1.0:
                continue
            if rng.random() < 0.32:
                x *= 0.55
                y *= 0.55
                z *= 0.55
            self._nodes.append((x, y, z, rng.random() * math.tau))

        self._edges: list[tuple[int, int]] = []
        edge_set: set[tuple[int, int]] = set()
        for i, a in enumerate(self._nodes):
            nearest: list[tuple[float, int]] = []
            for j, b in enumerate(self._nodes):
                if i == j:
                    continue
                dx = a[0] - b[0]
                dy = a[1] - b[1]
                dz = a[2] - b[2]
                nearest.append((dx * dx + dy * dy + dz * dz, j))
            nearest.sort(key=lambda item: item[0])
            for _, j in nearest[:3]:
                edge = (min(i, j), max(i, j))
                if edge not in edge_set:
                    edge_set.add(edge)
                    self._edges.append(edge)

        self._stars = [
            (rng.random(), rng.random(), 0.4 + rng.random() * 1.3, rng.random() * math.tau)
            for _ in range(80)
        ]

        self._pulses: list[Pulse] = []
        self._particles: list[Particle] = []
        self._rng = rng

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(25)

    def set_audio_level(self, level: float) -> None:
        if not math.isfinite(level):
            level = 0.0
        self._audio_target = max(0.0, min(1.0, level))

    def set_state(self, state: str) -> None:
        normalized = state.lower()
        if "listen" in normalized:
            next_state = "listening"
        elif "think" in normalized or "traitement" in normalized or "transcrib" in normalized:
            next_state = "thinking"
        elif "speak" in normalized or "élocution" in normalized:
            next_state = "speaking"
        elif "error" in normalized:
            next_state = "error"
        else:
            next_state = "idle"

        if next_state != self._state:
            self._last_state = self._state
            self._state = next_state
            self._spawn_burst(14 if next_state != "idle" else 5)
        self.update()

    def _spawn_burst(self, count: int) -> None:
        for _ in range(count):
            self._particles.append(
                Particle(
                    angle=self._rng.random() * math.tau,
                    radius=0.08 + self._rng.random() * 0.16,
                    speed=0.004 + self._rng.random() * 0.009,
                    alpha=0.65 + self._rng.random() * 0.35,
                    size=0.8 + self._rng.random() * 2.1,
                )
            )

    def _tick(self) -> None:
        state_energy = {
            "idle": 0.22,
            "listening": 0.58,
            "thinking": 0.92,
            "speaking": 0.74,
            "error": 0.42,
        }.get(self._state, 0.22)

        self._audio_level += (self._audio_target - self._audio_level) * 0.28
        if self._state != "listening":
            self._audio_target *= 0.84

        speed = 0.018 + state_energy * 0.045 + self._audio_level * 0.045
        self._phase = (self._phase + speed) % math.tau

        pulse_chance = 0.04 + state_energy * 0.13 + self._audio_level * 0.18
        if self._rng.random() < pulse_chance and self._edges:
            self._pulses.append(
                Pulse(
                    edge=self._rng.randrange(len(self._edges)),
                    progress=0.0,
                    speed=0.022 + state_energy * 0.025 + self._rng.random() * 0.02,
                    outward=self._rng.random() > 0.35,
                )
            )

        updated_pulses: list[Pulse] = []
        for pulse in self._pulses:
            pulse.progress += pulse.speed
            if pulse.progress <= 1.0:
                updated_pulses.append(pulse)
        self._pulses = updated_pulses[-36:]

        updated_particles: list[Particle] = []
        for p in self._particles:
            p.radius += p.speed
            p.alpha *= 0.975
            if p.alpha > 0.06 and p.radius < 1.25:
                updated_particles.append(p)
        self._particles = updated_particles[-80:]

        if self._state in {"thinking", "speaking"} and self._rng.random() < 0.08:
            self._spawn_burst(1)

        self.update()

    def _palette(self) -> tuple[QColor, QColor, QColor]:
        if self._state == "thinking":
            return QColor(255, 184, 62), QColor(255, 236, 174), QColor(255, 120, 22)
        if self._state == "error":
            return QColor(255, 70, 70), QColor(255, 190, 190), QColor(170, 20, 20)
        if self._state == "speaking":
            return QColor(62, 225, 255), QColor(220, 252, 255), QColor(20, 130, 255)
        return QColor(0, 212, 255), QColor(188, 248, 255), QColor(0, 104, 190)

    def _project_nodes(self, cx: float, cy: float, scale: float) -> list[tuple[QPointF, float]]:
        ry = self._phase * 0.42
        rx = math.sin(self._phase * 0.37) * 0.16
        cosy = math.cos(ry)
        siny = math.sin(ry)
        cosx = math.cos(rx)
        sinx = math.sin(rx)

        projected: list[tuple[QPointF, float]] = []
        for x, y, z, node_phase in self._nodes:
            xr = x * cosy - z * siny
            zr = x * siny + z * cosy
            yr = y * cosx - zr * sinx
            zr2 = y * sinx + zr * cosx

            perspective = 1.0 / max(0.55, 1.0 + zr2 * 0.34)
            breathing = 1.0 + math.sin(self._phase * 1.7 + node_phase) * (
                0.018 + self._audio_level * 0.05
            )
            px = cx + xr * scale * perspective * breathing
            py = cy + yr * scale * perspective * breathing
            projected.append((QPointF(px, py), zr2))
        return projected

    def _draw_background(self, painter: QPainter, primary: QColor) -> None:
        painter.fillRect(self.rect(), QColor(2, 6, 12))

        # Radial haze
        haze = QRadialGradient(self.rect().center(), max(self.width(), self.height()) * 0.7)
        haze.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(), 22))
        haze.setColorAt(0.50, QColor(primary.red(), primary.green(), primary.blue(), 7))
        haze.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), haze)

        # Grid
        grid_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 18))
        grid_pen.setWidthF(0.8)
        painter.setPen(grid_pen)
        step = 30
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)

        # Scanlines
        scan_pen = QPen(QColor(255, 255, 255, 8))
        painter.setPen(scan_pen)
        for y in range(0, self.height(), 5):
            painter.drawLine(0, y, self.width(), y)

        # Stars / data points
        painter.setPen(Qt.PenStyle.NoPen)
        for sx, sy, radius, star_phase in self._stars:
            flicker = (math.sin(self._phase * 1.8 + star_phase) + 1.0) * 0.5
            alpha = int(24 + flicker * 65)
            painter.setBrush(QColor(primary.red(), primary.green(), primary.blue(), alpha))
            painter.drawEllipse(
                QPointF(sx * self.width(), sy * self.height()),
                radius,
                radius,
            )

    def _draw_orbits(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        scale: float,
        primary: QColor,
        accent: QColor,
        energy: float,
    ) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)

        rings = [
            (0.43, 1.4, 225, 1),
            (0.56, -1.0, 190, 1),
            (0.69, 0.68, 150, 2),
            (0.82, -0.43, 105, 1),
            (0.94, 0.31, 75, 1),
        ]

        for idx, (ratio, direction, alpha, width) in enumerate(rings):
            radius = scale * ratio * (1.0 + math.sin(self._phase + idx) * 0.018)
            rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            color = primary if idx % 2 == 0 else accent
            pen = QPen(QColor(color.red(), color.green(), color.blue(), int(alpha * (0.62 + energy * 0.38))))
            pen.setWidthF(float(width))
            painter.setPen(pen)

            start = int((self._phase * direction * 180 / math.pi + idx * 47) * 16)
            span = int((86 + idx * 25) * 16)
            painter.drawArc(rect, start, span)
            painter.drawArc(rect, start + 180 * 16, int(span * 0.52))

        # Tick ring
        tick_radius = scale * 0.87
        for i in range(72):
            angle = i / 72.0 * math.tau + self._phase * 0.18
            strong = i % 6 == 0
            inner = tick_radius - (8 if strong else 4)
            outer = tick_radius
            p1 = QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner)
            p2 = QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer)
            alpha = 120 if strong else 52
            pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), alpha))
            pen.setWidthF(1.2 if strong else 0.7)
            painter.setPen(pen)
            painter.drawLine(p1, p2)

    def _draw_network(
        self,
        painter: QPainter,
        projected: list[tuple[QPointF, float]],
        primary: QColor,
        bright: QColor,
        energy: float,
    ) -> None:
        for a, b in self._edges:
            pa, za = projected[a]
            pb, zb = projected[b]
            depth = max(-1.0, min(1.0, (za + zb) * 0.5))
            alpha = int((40 + energy * 58) * (1.05 - (depth + 1.0) * 0.20))
            pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), max(18, alpha)))
            pen.setWidthF(0.7 + energy * 0.35)
            painter.setPen(pen)
            painter.drawLine(pa, pb)

        # Travelling synaptic pulses
        painter.setPen(Qt.PenStyle.NoPen)
        for pulse in self._pulses:
            a, b = self._edges[pulse.edge]
            pa, _ = projected[a]
            pb, _ = projected[b]
            t = pulse.progress if pulse.outward else 1.0 - pulse.progress
            x = pa.x() + (pb.x() - pa.x()) * t
            y = pa.y() + (pb.y() - pa.y()) * t
            radius = 2.0 + energy * 2.2
            glow = QRadialGradient(QPointF(x, y), radius * 3.4)
            glow.setColorAt(0.0, QColor(255, 255, 255, 250))
            glow.setColorAt(0.35, QColor(bright.red(), bright.green(), bright.blue(), 220))
            glow.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(x, y), radius * 3.4, radius * 3.4)

        # Nodes sorted by depth
        order = sorted(range(len(projected)), key=lambda i: projected[i][1], reverse=True)
        for i in order:
            point, depth = projected[i]
            node_phase = self._nodes[i][3]
            pulse = (math.sin(self._phase * 2.8 + node_phase) + 1.0) * 0.5
            near = max(0.55, 1.0 - depth * 0.22)
            radius = (1.2 + pulse * 2.4 + self._audio_level * 2.0) * near
            alpha = int(105 + pulse * 135)
            painter.setPen(Qt.PenStyle.NoPen)

            halo = QRadialGradient(point, radius * 3.5)
            halo.setColorAt(0.0, QColor(255, 255, 255, alpha))
            halo.setColorAt(0.28, QColor(bright.red(), bright.green(), bright.blue(), alpha))
            halo.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
            painter.setBrush(halo)
            painter.drawEllipse(point, radius * 3.5, radius * 3.5)

    def _draw_particles(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        scale: float,
        primary: QColor,
    ) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            x = cx + math.cos(p.angle + self._phase * 0.2) * p.radius * scale
            y = cy + math.sin(p.angle + self._phase * 0.2) * p.radius * scale
            alpha = int(255 * max(0.0, min(1.0, p.alpha)))
            painter.setBrush(QColor(primary.red(), primary.green(), primary.blue(), alpha))
            painter.drawEllipse(QPointF(x, y), p.size, p.size)

    def _draw_core(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        scale: float,
        primary: QColor,
        bright: QColor,
        accent: QColor,
        energy: float,
    ) -> None:
        pulse = (math.sin(self._phase * 3.0) + 1.0) * 0.5
        core_radius = max(32.0, scale * (0.145 + energy * 0.028 + self._audio_level * 0.025))

        # Outer shock halo
        halo_radius = core_radius * (2.0 + pulse * 0.18)
        outer = QRadialGradient(QPointF(cx, cy), halo_radius)
        outer.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(), 50))
        outer.setColorAt(0.50, QColor(primary.red(), primary.green(), primary.blue(), 24))
        outer.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(outer)
        painter.drawEllipse(QPointF(cx, cy), halo_radius, halo_radius)

        # Reactor core
        gradient = QRadialGradient(QPointF(cx, cy), core_radius)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient.setColorAt(0.20, QColor(bright.red(), bright.green(), bright.blue(), 248))
        gradient.setColorAt(0.55, QColor(primary.red(), primary.green(), primary.blue(), 195))
        gradient.setColorAt(0.82, QColor(accent.red(), accent.green(), accent.blue(), 95))
        gradient.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        # Inner segmented arcs
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i, ratio in enumerate((0.48, 0.67, 0.86)):
            radius = core_radius * ratio
            rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            pen = QPen(QColor(bright.red(), bright.green(), bright.blue(), 210 - i * 40))
            pen.setWidthF(1.6 if i == 0 else 1.0)
            painter.setPen(pen)
            start = int((self._phase * (1 if i % 2 == 0 else -1) * 150 + i * 55) * 16)
            painter.drawArc(rect, start, int((95 - i * 12) * 16))
            painter.drawArc(rect, start + 155 * 16, int((56 + i * 7) * 16))

        # Scanner ray
        sweep_angle = self._phase * 1.7
        sweep_len = scale * 0.92
        sweep = QPointF(
            cx + math.cos(sweep_angle) * sweep_len,
            cy + math.sin(sweep_angle) * sweep_len,
        )
        sweep_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 115))
        sweep_pen.setWidthF(1.0)
        painter.setPen(sweep_pen)
        painter.drawLine(QPointF(cx, cy), sweep)

    def _draw_waveform(
        self,
        painter: QPainter,
        primary: QColor,
        energy: float,
    ) -> None:
        width = self.width()
        baseline = self.height() - 30
        left = 34
        right = width - 34
        span = max(1, right - left)

        path = QPainterPath()
        for i in range(120):
            x = left + span * i / 119.0
            phase = i * 0.34 + self._phase * 8.0
            live = self._audio_level if self._state == "listening" else 0.0
            synthetic = energy * (0.35 if self._state in {"thinking", "speaking"} else 0.12)
            amp = 4.0 + (live * 24.0 + synthetic * 18.0) * (
                0.45 + 0.55 * math.sin(i * 0.17) ** 2
            )
            y = baseline + math.sin(phase) * amp * math.sin(math.pi * i / 119.0)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 175))
        pen.setWidthF(1.35)
        painter.setPen(pen)
        painter.drawPath(path)

    def _draw_labels(
        self,
        painter: QPainter,
        primary: QColor,
        bright: QColor,
    ) -> None:
        state_label = {
            "idle": "NEURAL CORE · STANDBY",
            "listening": "NEURAL CORE · LISTENING",
            "thinking": "NEURAL CORE · PROCESSING",
            "speaking": "NEURAL CORE · SPEAKING",
            "error": "NEURAL CORE · ALERT",
        }.get(self._state, "NEURAL CORE")

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(primary.red(), primary.green(), primary.blue(), 175))
        painter.drawText(18, 22, "J.A.R.V.I.S. // COGNITIVE MATRIX")
        painter.drawText(18, self.height() - 10, state_label)

        level = int(self._audio_level * 100)
        painter.setPen(QColor(bright.red(), bright.green(), bright.blue(), 145))
        painter.drawText(self.width() - 150, 22, f"VOICE ENERGY {level:03d}%")

        # HUD corner brackets
        pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 120))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        m = 10
        l = 18
        painter.drawLine(m, m, m + l, m)
        painter.drawLine(m, m, m, m + l)
        painter.drawLine(self.width() - m, m, self.width() - m - l, m)
        painter.drawLine(self.width() - m, m, self.width() - m, m + l)
        painter.drawLine(m, self.height() - m, m + l, self.height() - m)
        painter.drawLine(m, self.height() - m, m, self.height() - m - l)
        painter.drawLine(
            self.width() - m,
            self.height() - m,
            self.width() - m - l,
            self.height() - m,
        )
        painter.drawLine(
            self.width() - m,
            self.height() - m,
            self.width() - m,
            self.height() - m - l,
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0 - 2.0
        scale = min(w * 0.48, h * 0.55)

        primary, bright, accent = self._palette()
        state_energy = {
            "idle": 0.24,
            "listening": 0.62,
            "thinking": 0.96,
            "speaking": 0.80,
            "error": 0.48,
        }.get(self._state, 0.24)
        energy = max(0.0, min(1.0, state_energy + self._audio_level * 0.34))

        self._draw_background(painter, primary)
        self._draw_orbits(painter, cx, cy, scale, primary, accent, energy)

        projected = self._project_nodes(cx, cy, scale * 0.84)
        self._draw_network(painter, projected, primary, bright, energy)
        self._draw_particles(painter, cx, cy, scale, primary)
        self._draw_core(painter, cx, cy, scale, primary, bright, accent, energy)
        self._draw_waveform(painter, primary, energy)
        self._draw_labels(painter, primary, bright)

        painter.end()
