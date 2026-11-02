"""Minimal Qt UI. All network I/O and Core work happen outside the GUI process."""

import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from qgis.core import QgsCoordinateTransform, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QProcess, QStandardPaths, Qt, QTimer
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def python_executable():
    """Use QGIS's matching Python, never an arbitrary executable on PATH."""
    for relative in ("python.exe", "bin/python3", "bin/python"):
        candidate = Path(sys.prefix) / relative
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("QGISに対応するPython実行ファイルが見つかりません")


class RhinestonePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.process = None
        self.pending_directory = None
        self.closed = False

    def initGui(self):
        self.action = QAction("Rhinestone Search", self.iface.mainWindow())
        self.action.triggered.connect(self.show)
        self.iface.addPluginToMenu("Rhinestone", self.action)

    def show(self):
        if self.dock is None:
            self.dock = QDockWidget("Rhinestone Search", self.iface.mainWindow())
            self.dock.setObjectName("RhinestoneSearch")
            self.dock.setMinimumWidth(360)
            panel = QWidget()
            layout = QVBoxLayout(panel)
            self.query = QLineEdit()
            self.query.setPlaceholderText("河川、公園…")
            self.query.setAccessibleName("検索キーワード")
            self.button = QPushButton("検索")
            self.status = QLabel("キーワードを入力して検索")
            self.status.setWordWrap(True)
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            self.results = QListWidget()
            self.results.setWordWrap(True)
            self.results.setAccessibleName("検索結果：選択で地図へ追加")
            for widget in (self.query, self.button, self.status, self.results):
                layout.addWidget(widget)
            self.dock.setWidget(panel)
            self.query.returnPressed.connect(self.search)
            self.button.clicked.connect(self.search)
            self.results.itemClicked.connect(self.select)
            self.results.itemActivated.connect(self.select)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.query.setFocus()

    def search(self):
        text = self.query.text().strip()
        if not text or self.process is not None:
            return
        self.results.clear()
        self.search_status = ""
        self.status.setText("検索中…")
        self.start({"action": "search", "text": text}, self.searched)

    def start(self, request, completed):
        try:
            executable = python_executable()
            root = Path(__file__).parent
            manifest = json.loads((root / "bundle.json").read_text())
            if (
                manifest["python"] != list(sys.version_info[:2])
                or manifest["platform"] != sys.platform
                or manifest["machine"] != platform.machine()
            ):
                raise RuntimeError(
                    "このQGIS/Pythonに対応する配布ZIPをインストールしてください"
                )
            self.operation = request["action"]
            process = QProcess(self.dock)
            self.process = process
            self.button.setEnabled(False)
            self.results.setEnabled(False)
            process.setProgram(executable)
            process.setArguments(["-I", "-S", str(root / "worker.py")])
            process.finished.connect(
                lambda code, _status: self.finished(process, code, completed)
            )
            process.errorOccurred.connect(lambda _error: self.process_error(process))
            process.started.connect(lambda: self.send(process, request))
            process.start()
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.status.setText(f"起動できません: {error}")
            self.cleanup_pending()

    @staticmethod
    def send(process, request):
        process.write(json.dumps(request, ensure_ascii=False).encode("utf-8"))
        process.closeWriteChannel()

    def process_error(self, process):
        if self.process is not process:
            return
        self.status.setText(
            "処理を開始・継続できません。対応ZIPとPython環境を確認してください"
        )
        self.reset(process)
        self.cleanup_pending()

    def finished(self, process, code, completed):
        if self.closed or self.process is not process:
            return
        try:
            if code != 0:
                raise ValueError("worker failed")
            message = json.loads(bytes(process.readAllStandardOutput()).decode("utf-8"))
            if not message["ok"]:
                phase = "検索失敗" if self.operation == "search" else "追加失敗"
                self.status.setText(f"{phase}: 通信・データ処理 ({message['error']})")
                self.cleanup_pending()
            else:
                completed(message["result"])
        except (ValueError, KeyError, TypeError):
            self.status.setText("処理結果を読み取れません。対応ZIPを確認してください")
            self.cleanup_pending()
        finally:
            self.reset(process)

    def reset(self, process):
        self.process = None
        self.button.setEnabled(True)
        self.results.setEnabled(True)
        process.deleteLater()

    def searched(self, result):
        diagnostics = result["diagnostics"]
        failures = [d for d in diagnostics if d["reason"] == "provider_failure"]
        rows = result["rows"]
        if failures:
            prefix = (
                "一部の提供元で検索失敗"
                if rows
                else "提供元の検索に失敗（0件とは未確定）"
            )
        else:
            prefix = f"{len(rows)}件" if rows else "結果0件"
        if diagnostics:
            prefix += f" / 診断{len(diagnostics)}件"
        self.search_status = prefix
        self.status.setText(prefix)
        self.status.setToolTip(
            "\n".join(
                f"{d['provider']}: {d['reason']} ({d['failure_type'] or '-'})"
                for d in diagnostics
            )
        )
        for index, row in enumerate(rows):
            suffix = f" — {row['reason']}" if row["reason"] else ""
            item = QListWidgetItem(
                f"{index + 1}. {row['title']}\n{row['provider']} / {row['format']}{suffix}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            resource = row["resource"]
            item.setToolTip(
                f"{row['title']}\n{resource['uri']}\n"
                + json.dumps(resource.get("reference", {}), ensure_ascii=False)
            )
            if row["reason"]:
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEnabled
                    & ~Qt.ItemFlag.ItemIsSelectable
                )
            self.results.addItem(item)
        # Populating a list must never choose or add a Resource.
        self.results.setCurrentRow(-1)
        self.results.clearSelection()

    def select(self, item):
        if self.process is not None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        if not row or row["reason"]:
            return
        cache = (
            Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.CacheLocation
                )
            )
            / "rhinestone"
        )
        try:
            cache.mkdir(parents=True, exist_ok=True)
            self.pending_directory = Path(tempfile.mkdtemp(prefix="layer-", dir=cache))
        except OSError:
            self.status.setText("追加失敗: キャッシュへ保存できません")
            return
        self.selected_title = row["title"]
        self.status.setText("選択したデータを取得中…")
        self.start(
            {
                "action": "download",
                "resource": row["resource"],
                "target": str(self.pending_directory / "data.geojson"),
            },
            self.downloaded,
        )

    def downloaded(self, result):
        layer = QgsVectorLayer(result["path"], self.selected_title, "ogr")
        if not layer.isValid():
            self.status.setText("レイヤー追加失敗: QGIS/OGRで開けません")
            self.cleanup_pending()
            return
        layer.setCustomProperty(
            "rhinestone/resource", json.dumps(result["resource"], ensure_ascii=False)
        )
        layer.setCustomProperty(
            "rhinestone/plan", json.dumps(result["plan"], ensure_ascii=False)
        )
        QgsProject.instance().addMapLayer(layer)
        # QGIS's layer-tree bridge may change the canvas CRS on its queued
        # first-layer update. Zoom only after that update has run.
        QTimer.singleShot(0, lambda: self.zoom_to_layer(layer.id()))
        # Files must outlive plugin unload and project save/reopen. Cache is retained.
        self.pending_directory = None
        self.status.setText(
            f"追加しました: {self.selected_title} / {self.search_status}"
        )

    def zoom_to_layer(self, layer_id):
        if self.closed:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return
        canvas = self.iface.mapCanvas()
        extent = layer.extent()
        if extent.isEmpty():
            extent.grow(0.001 if layer.crs().isGeographic() else 10)
        transform = QgsCoordinateTransform(
            layer.crs(), canvas.mapSettings().destinationCrs(), QgsProject.instance()
        )
        canvas.setExtent(transform.transformBoundingBox(extent))
        canvas.refresh()

    def cleanup_pending(self):
        if self.pending_directory is not None:
            shutil.rmtree(self.pending_directory, ignore_errors=True)
            self.pending_directory = None

    def unload(self):
        self.closed = True
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(1000)
            self.process = None
        self.cleanup_pending()
        self.iface.removePluginMenu("Rhinestone", self.action)
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
        self.action.deleteLater()
