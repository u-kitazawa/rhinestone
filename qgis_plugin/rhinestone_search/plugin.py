"""Minimal Qt UI. All network I/O and Core work happen outside the GUI process."""

import json
import os
import platform
import re
import shutil
import sys
import tempfile
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsProject,
    QgsProviderRegistry,
    QgsProviderSublayerDetails,
    QgsProviderSublayerTask,
    QgsRasterLayer,
    QgsVectorTileBasicRenderer,
    QgsVectorTileLayer,
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QProcess, QStandardPaths, Qt, QTimer
from qgis.PyQt.QtGui import QAction, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QToolButton,
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


def dataset_paths(path):
    """Use installed OGR/GDAL file filters to scan extracted distributions."""
    root = Path(path)
    if not root.is_dir() or root.suffix.lower() == ".gdb":
        return [str(root)]
    registry = QgsProviderRegistry.instance()
    filters = registry.fileVectorFilters() + ";;" + registry.fileRasterFilters()
    suffixes = {
        "." + ext.lower() for ext in re.findall(r"\*\.([a-zA-Z0-9_]+)", filters)
    }
    paths = []
    for directory, folders, files in os.walk(root):
        folders[:] = sorted(f for f in folders if f != "__MACOSX")
        for folder in folders[:]:
            if folder.lower().endswith(".gdb"):
                paths.append(str(Path(directory) / folder))
                folders.remove(folder)
        shapes = {
            Path(f).stem.casefold() for f in files if Path(f).suffix.lower() == ".shp"
        }
        for file in sorted(files):
            member = Path(directory) / file
            if member.suffix.lower() not in suffixes:
                continue
            if member.suffix.lower() == ".dbf" and member.stem.casefold() in shapes:
                continue
            paths.append(str(member))
    return paths


class RhinestonePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.process = None
        self.scan_task = None
        self.pending_directory = None
        self.closed = False
        self.selected_row = None
        self.catalog_loaded = False
        self.diagnostic_text = ""

    def initGui(self):
        self.action = QAction("Rhinestone Search", self.iface.mainWindow())
        self.action.triggered.connect(self.show)
        self.iface.addPluginToMenu("Rhinestone", self.action)

    def show(self):
        if self.dock is None:
            self.dock = QDockWidget("Rhinestone Search", self.iface.mainWindow())
            self.dock.setObjectName("RhinestoneSearch")
            self.dock.setMinimumWidth(440)
            panel = QWidget()
            layout = QVBoxLayout(panel)
            self.search_controls = QWidget()
            form = QFormLayout(self.search_controls)
            self.query = QLineEdit()
            self.query.setPlaceholderText("河川、公園…（省略可）")
            self.query.setAccessibleName("検索キーワード")
            self.area = QLineEdit()
            self.area.setPlaceholderText("神奈川県、横浜市、行政区域コードなど")
            self.area.setAccessibleName("地域名")
            self.providers_button = QToolButton()
            self.providers_button.setMenu(QMenu(self.providers_button))
            self.providers_button.setPopupMode(
                QToolButton.ToolButtonPopupMode.InstantPopup
            )
            self.formats_button = QToolButton()
            self.formats_button.setMenu(QMenu(self.formats_button))
            self.formats_button.setPopupMode(
                QToolButton.ToolButtonPopupMode.InstantPopup
            )
            self.provider_actions = []
            self.format_actions = []
            self.providers_button.setText("提供元を読み込み中…")
            self.formats_button.setText("形式: すべて")
            form.addRow("キーワード", self.query)
            form.addRow("地域（area）", self.area)
            form.addRow("提供元", self.providers_button)
            form.addRow("形式（複数可）", self.formats_button)
            advanced_button = QToolButton()
            advanced_button.setText("期間・範囲・件数")
            advanced_button.setCheckable(True)
            form.addRow(advanced_button)
            self.advanced = QWidget()
            extra = QFormLayout(self.advanced)
            extra.setContentsMargins(0, 0, 0, 0)
            self.start_time = QLineEdit()
            self.end_time = QLineEdit()
            for control in (self.start_time, self.end_time):
                control.setPlaceholderText("2026-01-01T00:00:00+09:00（省略可）")
            self.bbox = QLineEdit()
            self.bbox.setPlaceholderText("西,南,東,北（経度・緯度）。areaと併用不可")
            self.extent_button = QPushButton("現在の表示範囲を使う")
            self.extent_button.clicked.connect(self.use_extent)
            self.limit = QSpinBox()
            self.limit.setRange(0, 1000)
            self.limit.setSpecialValueText("提供元の既定")
            self.limit.setValue(20)
            extra.addRow("開始日時", self.start_time)
            extra.addRow("終了日時", self.end_time)
            extra.addRow("範囲（bbox）", self.bbox)
            extra.addRow(self.extent_button)
            extra.addRow("件数（提供元ごと）", self.limit)
            form.addRow(self.advanced)
            self.advanced.hide()
            advanced_button.toggled.connect(self.advanced.setVisible)
            self.button = QPushButton("検索")
            form.addRow(self.button)
            layout.addWidget(self.search_controls)
            self.status = QLabel("キーワードや地域を指定して検索")
            self.status.setWordWrap(True)
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(self.status)
            self.result_filter = QLineEdit()
            self.result_filter.setPlaceholderText(
                "検索結果の名称・説明・提供者で絞り込み"
            )
            self.result_filter.textChanged.connect(self.filter_results)
            layout.addWidget(self.result_filter)
            splitter = QSplitter(Qt.Orientation.Vertical)
            self.results = QListWidget()
            self.results.setWordWrap(True)
            self.results.setAccessibleName("検索結果：選択で詳細を表示")
            self.details = QTextBrowser()
            self.details.setPlaceholderText(
                "結果を選ぶと、説明・更新日・ライセンス・配布URIを表示します"
            )
            splitter.addWidget(self.results)
            splitter.addWidget(self.details)
            layout.addWidget(splitter)
            self.add_button = QPushButton("選択したデータを追加")
            self.add_button.setEnabled(False)
            self.add_button.clicked.connect(self.add_selected)
            layout.addWidget(self.add_button)
            self.dock.setWidget(panel)
            for edit in (
                self.query,
                self.area,
                self.bbox,
                self.start_time,
                self.end_time,
            ):
                edit.returnPressed.connect(self.search)
            self.button.clicked.connect(self.search)
            self.results.currentItemChanged.connect(self.select)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.query.setFocus()
        if not self.catalog_loaded and not self.busy():
            self.start({"action": "catalog"}, self.catalog_ready)

    def catalog_ready(self, catalog):
        for button, storage, values in (
            (self.providers_button, self.provider_actions, catalog["providers"]),
            (self.formats_button, self.format_actions, catalog["formats"]),
        ):
            button.menu().clear()
            storage.clear()
            for value in values:
                action = QAction(value["label"], button.menu())
                action.setCheckable(True)
                action.setChecked(value.get("default", False))
                action.setData(value["id"])
                action.toggled.connect(self.update_filter_labels)
                button.menu().addAction(action)
                storage.append(action)
        self.catalog_loaded = True
        self.update_filter_labels()
        self.status.setText("キーワードや地域を指定して検索")

    def update_filter_labels(self, *_args):
        providers = [a.text() for a in self.provider_actions if a.isChecked()]
        formats = [a.text() for a in self.format_actions if a.isChecked()]
        self.providers_button.setText(
            "、".join(providers)
            if 0 < len(providers) <= 2
            else f"{len(providers)}件の提供元を選択"
            if providers
            else "提供元を選んでください"
        )
        self.providers_button.setToolTip("\n".join(providers))
        self.formats_button.setText(
            "、".join(formats)
            if 0 < len(formats) <= 2
            else f"{len(formats)}形式を選択"
            if formats
            else "すべて"
        )
        self.formats_button.setToolTip("\n".join(formats))

    def use_extent(self):
        canvas = self.iface.mapCanvas()
        from qgis.core import QgsCoordinateReferenceSystem

        transform = QgsCoordinateTransform(
            canvas.mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(canvas.extent())
        self.bbox.setText(
            ", ".join(
                str(v)
                for v in (
                    extent.xMinimum(),
                    extent.yMinimum(),
                    extent.xMaximum(),
                    extent.yMaximum(),
                )
            )
        )
        self.area.clear()

    def update_controls(self):
        available = not self.busy()
        self.search_controls.setEnabled(available)
        self.results.setEnabled(available)
        self.result_filter.setEnabled(available)
        self.add_button.setEnabled(
            available
            and self.selected_row is not None
            and not self.selected_row.get("reason")
        )

    def busy(self):
        return self.process is not None or self.scan_task is not None

    def search(self):
        if self.busy():
            return
        providers = [a.data() for a in self.provider_actions if a.isChecked()]
        if not providers:
            self.status.setText("提供元を1件以上選択してください")
            return
        if self.area.text().strip() and self.bbox.text().strip():
            self.status.setText(
                "地域名（area）と範囲（bbox）はどちらか一方を指定してください"
            )
            return
        try:
            bbox = (
                [float(v.strip()) for v in self.bbox.text().split(",")]
                if self.bbox.text().strip()
                else None
            )
            if bbox is not None and len(bbox) != 4:
                raise ValueError()
        except ValueError:
            self.status.setText("bboxは西・南・東・北の4数値をカンマで区切ってください")
            return
        conditions = {
            "text": self.query.text().strip() or None,
            "area": self.area.text().strip() or None,
            "bbox": bbox,
            "time": [
                self.start_time.text().strip() or None,
                self.end_time.text().strip() or None,
            ],
            "format": [a.data() for a in self.format_actions if a.isChecked()],
            "limit": self.limit.value() or None,
            "providers": providers,
        }
        if not any(conditions["time"]):
            conditions["time"] = None
        self.results.clear()
        self.selected_row = None
        self.details.clear()
        self.result_filter.clear()
        self.search_status = ""
        self.status.setText("検索中…")
        self.start({"action": "search", "conditions": conditions}, self.searched)

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
            self.update_controls()
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
                phase = {"search": "検索失敗", "catalog": "初期化失敗"}.get(
                    self.operation, "追加失敗"
                )
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
        self.update_controls()
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
        labels = {
            "unsupported": "指定条件に未対応",
            "missing_required": "必須条件が不足",
            "area_resolution_failed": "地域を特定できません",
            "provider_failure": "提供元の検索失敗",
            "item_skipped": "一部の配布を除外",
        }
        self.diagnostic_text = "\n".join(
            f"{d['provider']}: {labels.get(d['reason'], d['reason'])} "
            + (
                "（条件: "
                + ", ".join(
                    d.get("skipped_conditions", []) + d.get("missing_conditions", [])
                )
                + "）"
                if d.get("skipped_conditions") or d.get("missing_conditions")
                else ""
            )
            + (f" / {d['failure_type']}" if d.get("failure_type") else "")
            for d in diagnostics
        )
        self.status.setToolTip(self.diagnostic_text)
        self.details.setPlainText(
            self.diagnostic_text or "結果を選ぶと詳細を表示します"
        )
        for index, row in enumerate(rows):
            suffix = f" — {row['reason']}" if row["reason"] else ""
            if row.get("skipped_conditions"):
                names = {
                    "area": "地域",
                    "bbox": "範囲",
                    "time": "日時",
                    "format": "形式",
                    "text": "キーワード",
                    "limit": "件数",
                }
                suffix += " / 条件未適用: " + "、".join(
                    names.get(k, k) for k in row["skipped_conditions"]
                )
            item = QListWidgetItem(
                f"{index + 1}. {row['title']}\n{row['provider']} / {row.get('source_id', '')} / {row['format']}{suffix}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            resource = row["resource"]
            item.setToolTip(
                f"{row['title']}\n{resource['uri']}\n"
                + json.dumps(resource.get("reference", {}), ensure_ascii=False)
            )
            self.results.addItem(item)
        # Populating a list must never choose or add a Resource.
        self.results.setCurrentRow(-1)
        self.results.clearSelection()
        self.filter_results()
        self.update_controls()

    def filter_results(self, *_args):
        needle = self.result_filter.text().casefold().strip()
        for index in range(self.results.count()):
            item = self.results.item(index)
            row = item.data(Qt.ItemDataRole.UserRole)
            metadata = row["resource"].get("metadata", {})
            text = " ".join(
                str(v or "")
                for v in (
                    row["title"],
                    row["provider"],
                    row["format"],
                    metadata.get("description"),
                    metadata.get("license"),
                )
            )
            item.setHidden(needle not in text.casefold())
        current = self.results.currentItem()
        if current is not None and current.isHidden():
            self.results.setCurrentRow(-1)

    def select(self, item, previous=None):
        self.selected_row = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if self.selected_row is None:
            self.details.setPlainText(
                self.diagnostic_text or "結果を選ぶと詳細を表示します"
            )
            self.update_controls()
            return
        row = self.selected_row
        resource = row["resource"]
        metadata = resource.get("metadata", {})
        discovery = resource.get("discovery") or {}
        description = (
            metadata.get("description")
            or (discovery.get("metadata") or {}).get("description")
            or "説明はありません"
        )
        reference = resource.get("reference", {})
        plan = resource.get("access_plan") or {}
        note = row.get("reason") or (
            "配布物内の対応レイヤーをまとめて追加します"
            if plan.get("options", {}).get("archive")
            else "追加時にOGR/GDALまたはタイルレイヤーで読み込みます"
        )
        text = f"{row['title']}\n\n{description}\n\n" + "\n".join(
            [
                f"提供者: {metadata.get('publisher') or row['provider']}",
                f"検索元: {row.get('source_id') or row['provider']}",
                f"形式: {row['format']}",
                f"更新日: {metadata.get('updated_at') or '記載なし'}",
                f"ライセンス: {metadata.get('license') or '記載なし（配布元を確認してください）'}",
                f"配布URI: {resource['uri']}",
                f"データセットID: {reference.get('dataset_identifier') or '記載なし'}",
                f"配布ID: {reference.get('resource_identifier') or '記載なし'}",
                f"追加について: {note}",
            ]
        )
        if self.diagnostic_text:
            text += "\n\n検索条件・提供元の診断\n" + self.diagnostic_text
        self.details.setPlainText(text)
        self.update_controls()

    def add_selected(self):
        if self.busy():
            return
        row = self.selected_row
        if not row or row.get("reason"):
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
                "target": str(self.pending_directory / "data"),
            },
            self.downloaded,
        )

    def downloaded(self, result):
        if "tile" in result:
            self.add_tile(result)
            return
        self.scan_paths = dataset_paths(result["path"])
        self.sublayers = []
        self.status.setText("OGR/GDALでデータを確認中…")
        self.update_controls()
        self.scan_next(result)

    def add_tile(self, result):
        tile = result["tile"]
        uri = QgsDataSourceUri()
        for key, value in {
            "type": "xyz",
            "url": tile["url"],
            "zmin": tile.get("min_zoom"),
            "zmax": tile.get("max_zoom"),
        }.items():
            if value is not None:
                uri.setParam(key, str(value))
        encoded = bytes(uri.encodedUri()).decode("utf-8")
        if tile["format"] in {"pbf", "mvt"}:
            layer = QgsVectorTileLayer(encoded, self.selected_title)
            renderer = QgsVectorTileBasicRenderer()
            renderer.setStyles(
                QgsVectorTileBasicRenderer.simpleStyle(
                    QColor("#c5dfeb"),
                    QColor("#38748f"),
                    0.2,
                    QColor("#38748f"),
                    0.4,
                    QColor("#12ab34"),
                    QColor("#126b34"),
                    4,
                )
            )
            layer.setRenderer(renderer)
        else:
            layer = QgsRasterLayer(encoded, self.selected_title, "wms")
        if not layer.isValid():
            sip.delete(layer)
            self.status.setText("レイヤー追加失敗: XYZタイルを開けません")
            self.cleanup_pending()
            return
        metadata = layer.metadata()
        metadata.setRights([tile.get("attribution", "")])
        metadata.setAbstract(
            "\n".join(tile.get(k, "") for k in ("coverage", "usage_notes", "usage_url"))
        )
        layer.setMetadata(metadata)
        layer.setCustomProperty(
            "rhinestone/resource", json.dumps(result["resource"], ensure_ascii=False)
        )
        layer.setCustomProperty(
            "rhinestone/plan", json.dumps(result["plan"], ensure_ascii=False)
        )
        QgsProject.instance().addMapLayer(layer)
        # QGIS requests only visible tiles; never download a global tile pyramid.
        self.cleanup_pending()
        self.status.setText(
            f"追加しました: {self.selected_title}（XYZタイル） / {self.search_status}"
        )

    def scan_next(self, result):
        if not self.scan_paths:
            self.add_sublayers(result)
            return
        task = QgsProviderSublayerTask(self.scan_paths.pop(0))
        self.scan_task = task
        self.update_controls()
        task.taskCompleted.connect(lambda: self.scanned(task, result, True))
        task.taskTerminated.connect(lambda: self.scanned(task, result, False))
        QgsApplication.taskManager().addTask(task)

    def scanned(self, task, result, success):
        self.scan_task = None
        if self.closed:
            self.cleanup_pending()
            return
        if not success:
            self.status.setText("レイヤー追加失敗: データ確認を中止しました")
            self.cleanup_pending()
            self.update_controls()
            return
        self.sublayers.extend(
            d for d in task.results() if d.providerKey() in {"ogr", "gdal"}
        )
        self.scan_next(result)

    def add_sublayers(self, result):
        selector = result["plan"].get("options", {}).get("layer")
        details = self.sublayers
        if selector is not None:
            details = [
                d
                for d in details
                if (d.layerNumber() if isinstance(selector, int) else d.name())
                == selector
            ]
        options = QgsProviderSublayerDetails.LayerOptions(
            QgsProject.instance().transformContext()
        )
        layers = []
        for detail in details:
            layer = detail.toLayer(options)
            if layer is None or not layer.isValid():
                # Release all providers before deleting their files on Windows.
                if layer is not None:
                    sip.delete(layer)
                for prepared in layers:
                    sip.delete(prepared)
                self.status.setText("レイヤー追加失敗: QGIS/OGR/GDALで開けません")
                self.update_controls()
                self.cleanup_pending()
                return
            layer.setName(
                self.selected_title
                if len(details) == 1
                else f"{self.selected_title} — {detail.name()}"
            )
            encoding = result["plan"].get("options", {}).get("encoding")
            if encoding and layer.type() == Qgis.LayerType.Vector:
                layer.setProviderEncoding(encoding)
            layer.setCustomProperty(
                "rhinestone/resource",
                json.dumps(result["resource"], ensure_ascii=False),
            )
            layer.setCustomProperty(
                "rhinestone/plan", json.dumps(result["plan"], ensure_ascii=False)
            )
            layers.append(layer)
        self.update_controls()
        if not layers:
            self.status.setText(
                "レイヤー追加失敗: 対応するOGR/GDALドライバー・レイヤーがありません"
            )
            self.cleanup_pending()
            return
        QgsProject.instance().addMapLayers(layers)
        spatial = next(
            (layer for layer in layers if layer.isSpatial() and layer.crs().isValid()),
            None,
        )
        if spatial is not None:
            QTimer.singleShot(0, lambda: self.zoom_to_layer(spatial.id()))
        self.pending_directory = None
        self.status.setText(
            f"追加しました: {self.selected_title}（{len(layers)}レイヤー） / {self.search_status}"
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
        if self.scan_task is not None:
            self.scan_task.cancel()
        else:
            self.cleanup_pending()
        self.iface.removePluginMenu("Rhinestone", self.action)
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
        self.action.deleteLater()
