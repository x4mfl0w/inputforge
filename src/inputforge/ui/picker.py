"""Bildschirm-Picker: Punkt oder Bereich auf einem eingefrorenen Screenshot wählen.

Ablauf: Countdown (Zeit, um ins Spiel zu wechseln) → Screenshot des gesamten virtuellen
Desktops in *physischen* Pixeln → Vollbild-Ansicht des Screenshots. Weil die Auswahl in
Bildkoordinaten erfolgt, gibt es keine Probleme mit Windows-DPI-Skalierung.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from inputforge.platform.base import Rect, WindowManager
from inputforge.vision.matcher import Image
from inputforge.vision.screen import ScreenGrabber


@dataclass(frozen=True, slots=True)
class PickResult:
    rect: Rect
    """Bildschirmkoordinaten (bei Punkt-Auswahl: w = h = 1)."""
    crop: Image
    """BGR-Ausschnitt (bei Punkt: 1×1)."""
    window: Rect | None
    """Client-Bereich des Zielfensters zum Aufnahmezeitpunkt (für relative Koordinaten)."""

    def relative_to_window(self) -> tuple[int, int] | None:
        if self.window is None:
            return None
        return self.rect.x - self.window.x, self.rect.y - self.window.y


def bgr_to_qimage(img: Image) -> QImage:
    h, w = img.shape[:2]
    rgb = np.ascontiguousarray(img[:, :, ::-1])
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class _View(QGraphicsView):
    def __init__(self, dialog: PickerDialog) -> None:
        super().__init__()
        self.dlg = dialog
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin: QPointF | None = None

    def wheelEvent(self, ev: QWheelEvent) -> None:
        factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(factor, factor)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.RightButton:
            self.dlg.reject()
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        pos = self.mapToScene(ev.position().toPoint())
        if self.dlg.mode == "point":
            self.dlg.finish(QRectF(pos.x(), pos.y(), 1, 1))
            return
        self._origin = pos
        self.dlg.band.setRect(QRectF(pos, pos))
        self.dlg.band.show()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        pos = self.mapToScene(ev.position().toPoint())
        self.dlg.update_info(pos)
        if self._origin is not None:
            self.dlg.band.setRect(QRectF(self._origin, pos).normalized())

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if self._origin is not None and ev.button() == Qt.MouseButton.LeftButton:
            rect = self.dlg.band.rect()
            self._origin = None
            if rect.width() >= 3 and rect.height() >= 3:
                self.dlg.finish(rect)
            else:
                self.dlg.band.hide()


class PickerDialog(QDialog):
    def __init__(self, shot: Image, origin: Rect, window: Rect | None, mode: str) -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.mode = mode
        self.shot = shot
        self.origin = origin
        self.target_rect = window
        self.result_value: PickResult | None = None

        self.scene = QGraphicsScene(self)
        self.pix = QGraphicsPixmapItem(QPixmap.fromImage(bgr_to_qimage(shot)))
        self.scene.addItem(self.pix)
        if window is not None:
            wr = QGraphicsRectItem(window.x - origin.x, window.y - origin.y, window.w, window.h)
            wr.setPen(QPen(QColor("#2d7ff9"), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(wr)
        self.band = QGraphicsRectItem()
        self.band.setPen(QPen(QColor("#ff3366"), 1))
        self.band.setBrush(QColor(255, 51, 102, 40))
        self.band.hide()
        self.scene.addItem(self.band)

        self.view = _View(self)
        self.view.setScene(self.scene)
        self.info = QLabel()
        self.info.setStyleSheet("QLabel { background: #222; color: #eee; padding: 4px 8px; }")
        hint = (
            "Klicke auf den gewünschten Punkt"
            if mode == "point"
            else "Ziehe einen Rahmen um das Icon (möglichst eng, ohne wechselnden Hintergrund)"
        )
        self._hint = f"{hint}  ·  Mausrad = Zoom  ·  Esc/Rechtsklick = Abbrechen"
        self.info.setText(self._hint)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.info)
        lay.addWidget(self.view, 1)

    def showEvent(self, ev: QShowEvent) -> None:
        super().showEvent(ev)
        self.view.fitInView(self.pix, Qt.AspectRatioMode.KeepAspectRatio)

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(ev)

    def update_info(self, pos: QPointF) -> None:
        sx, sy = int(pos.x()) + self.origin.x, int(pos.y()) + self.origin.y
        rel = ""
        if self.target_rect is not None:
            rel = f"  ·  Fenster: ({sx - self.target_rect.x}, {sy - self.target_rect.y})"
        self.info.setText(f"Bildschirm: ({sx}, {sy}){rel}  ·  {self._hint}")

    def finish(self, scene_rect: QRectF) -> None:
        h, w = self.shot.shape[:2]
        x1 = max(0, min(w - 1, int(scene_rect.left())))
        y1 = max(0, min(h - 1, int(scene_rect.top())))
        x2 = max(x1 + 1, min(w, round(scene_rect.right())))
        y2 = max(y1 + 1, min(h, round(scene_rect.bottom())))
        crop = self.shot[y1:y2, x1:x2].copy()
        rect = Rect(self.origin.x + x1, self.origin.y + y1, x2 - x1, y2 - y1)
        self.result_value = PickResult(rect=rect, crop=crop, window=self.target_rect)
        self.accept()


def pick_from_screen(
    parent: QWidget | None,
    windows: WindowManager,
    target_title: str,
    *,
    mode: str = "region",
    delay_s: int = 3,
) -> PickResult | None:
    """Blockierend: versteckt ``parent``, wartet ``delay_s`` und öffnet den Picker."""
    # Eigene Fenster unsichtbar machen. Nicht hide(): das würde laufende modale
    # Dialoge (QDialog.exec) beenden – Transparenz lässt sie bestehen.
    faded: list[tuple[QWidget, float]] = []
    for w in QApplication.topLevelWidgets():
        if w.isVisible() and not isinstance(w, QLabel):
            faded.append((w, w.windowOpacity()))
            w.setWindowOpacity(0.0)

    try:
        _Countdown(delay_s).exec()
        handle = windows.find(target_title) if target_title else None
        window_rect = windows.client_rect(handle) if handle is not None else None
        shot, origin = ScreenGrabber().grab()
    finally:
        for w, opacity in faded:
            w.setWindowOpacity(opacity)
    dlg = PickerDialog(shot, origin, window_rect, mode)
    # Auf den gesamten virtuellen Desktop legen (logische Koordinaten des Qt-Desktops).
    vgeo = QApplication.primaryScreen().virtualGeometry()
    dlg.setGeometry(vgeo)
    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return dlg.result_value if ok else None


class _Countdown(QDialog):
    def __init__(self, seconds: int) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.remaining = seconds
        self.label = QLabel()
        self.label.setStyleSheet(
            "QLabel { background: rgba(20,20,20,230); color: #ffd166; font-size: 18px;"
            " padding: 12px 20px; border-radius: 8px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.label)
        self._tick()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(screen.center().x() - 160, screen.top() + 40)

    def _tick(self) -> None:
        if self.remaining <= 0:
            # Kurz warten, bis das Overlay selbst verschwunden ist.
            self.hide()
            QTimer.singleShot(150, self.accept)
            if hasattr(self, "timer"):
                self.timer.stop()
            return
        self.label.setText(f"Screenshot in {self.remaining} s – jetzt ins Spiel wechseln …")
        self.remaining -= 1
