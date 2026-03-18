from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class WarningOverlay(QtWidgets.QWidget):
    clicked = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle("Posture Warning")

        flags = (
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._show_text = False
        self._icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning)
        # Give extra vertical room so text can sit fully below the icon
        self._size = QtCore.QSize(100, 120)
        self.resize(self._size)

    def set_show_text(self, show: bool) -> None:
        self._show_text = bool(show)
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self.clicked.emit()
        event.accept()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(2, 2, -2, -2)
        bg = QtGui.QColor(0, 0, 0, 120)
        painter.setBrush(bg)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 140), 1))
        painter.drawRoundedRect(rect, 12, 12)

        icon_rect = QtCore.QRect(18, 14, 64, 64)
        self._icon.paint(painter, icon_rect)

        if self._show_text:
            painter.setPen(QtGui.QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            # Place text in a band clearly below the icon, with padding
            text_rect = QtCore.QRect(10, 84, rect.width() - 20, rect.height() - 94)
            painter.drawText(
                text_rect,
                QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                "Fix posture",
            )

