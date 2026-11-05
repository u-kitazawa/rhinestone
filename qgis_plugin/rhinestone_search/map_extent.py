"""QGIS's rectangle selection tool with explicit cancellation."""

from qgis.gui import QgsMapToolExtent
from qgis.PyQt.QtCore import Qt, pyqtSignal


class BboxMapTool(QgsMapToolExtent):
    cancelled = pyqtSignal()

    def __init__(self, canvas):
        super().__init__(canvas)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasPressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            super().canvasPressEvent(event)

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
        elif event.button() == Qt.MouseButton.LeftButton:
            super().canvasReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)
