"""Run with QGIS's Python after extracting the distribution ZIP.

RHINESTONE_PLUGIN_DIR points to extracted rhinestone_search. Optional --live uses
search.ckan.jp and the selected publisher's real HTTP endpoint.
"""

import configparser
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.core import Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsProject
from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas
from qgis.PyQt.QtCore import QT_VERSION_STR, Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QMainWindow, QPushButton

ROOT = Path(os.environ["RHINESTONE_PLUGIN_DIR"])
sys.path.insert(0, str(ROOT.parent))
assert "rhinestone" not in sys.modules
from rhinestone_search import classFactory  # noqa: E402
from rhinestone_search import plugin as module  # noqa: E402

LIVE = "--live" in sys.argv
sys.argv = [s for s in sys.argv if s != "--live"]
APP = QgsApplication([], True)
if os.environ.get("QGIS_PREFIX_PATH"):
    APP.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
APP.initQgis()
print(
    json.dumps(
        {
            "qgis": Qgis.QGIS_VERSION,
            "qt": QT_VERSION_STR,
            "python": sys.version.split()[0],
        }
    ),
    flush=True,
)
if os.environ.get("RHINESTONE_QGIS_MAJOR"):
    assert Qgis.QGIS_VERSION_INT // 10000 == int(os.environ["RHINESTONE_QGIS_MAJOR"])
if Qgis.QGIS_VERSION_INT >= 40000:
    assert QT_VERSION_STR.startswith("6.")
if os.environ.get("RHINESTONE_FONT"):
    from qgis.PyQt.QtGui import QFont, QFontDatabase

    QFontDatabase.addApplicationFont(os.environ["RHINESTONE_FONT"])
    APP.setFont(QFont("Noto Sans CJK JP", 10))


class Interface:
    def __init__(self):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas()
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        self.bridge = QgsLayerTreeMapCanvasBridge(
            QgsProject.instance().layerTreeRoot(), self.canvas
        )
        self.window.setCentralWidget(self.canvas)
        self.window.resize(1000, 650)

    def mainWindow(self):
        return self.window

    def mapCanvas(self):
        return self.canvas

    def addPluginToMenu(self, *_args):
        pass

    def removePluginMenu(self, *_args):
        pass

    def addDockWidget(self, area, dock):
        self.window.addDockWidget(area, dock)

    def removeDockWidget(self, dock):
        self.window.removeDockWidget(dock)


def row(uri, title="同じ名前", reason=None):
    return {
        "resource": {"uri": uri},
        "title": title,
        "provider": "test",
        "format": "geojson",
        "reason": reason,
    }


def wait_until(predicate, seconds=120):
    deadline = time.monotonic() + seconds
    while not predicate():
        APP.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("QGIS operation timed out")
        QTest.qWait(10)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.iface = Interface()
        self.plugin = classFactory(self.iface)
        self.plugin.initGui()
        self.plugin.show()
        self.iface.window.show()
        APP.processEvents()

    def tearDown(self):
        self.plugin.unload()
        QgsProject.instance().removeAllMapLayers()
        self.iface.window.close()
        APP.processEvents()

    def test_metadata_allows_qgis3_and_qgis4(self):
        metadata = configparser.ConfigParser()
        metadata.read(ROOT / "metadata.txt", encoding="utf-8")
        self.assertEqual(metadata["general"]["qgisMinimumVersion"], "3.34")
        self.assertEqual(metadata["general"]["qgisMaximumVersion"], "4.99")

    def test_empty_failure_unknown_and_no_implicit_selection(self):
        self.plugin.searched({"rows": [], "diagnostics": []})
        self.assertEqual(self.plugin.status.text(), "結果0件")
        diagnostics = [
            {
                "provider": "test",
                "reason": "provider_failure",
                "failure_type": "response",
            }
        ]
        self.plugin.searched({"rows": [], "diagnostics": diagnostics})
        self.assertIn("失敗", self.plugin.status.text())
        self.plugin.searched(
            {"rows": [row("a", reason="未対応")], "diagnostics": diagnostics}
        )
        self.assertIn("一部", self.plugin.status.text())
        self.assertFalse(
            self.plugin.results.item(0).flags() & Qt.ItemFlag.ItemIsSelectable
        )
        self.assertIsNone(self.plugin.results.currentItem())
        self.assertEqual(len(QgsProject.instance().mapLayers()), 0)
        self.assertEqual(
            [b.text() for b in self.plugin.dock.findChildren(QPushButton)], ["検索"]
        )

    def test_single_click_uses_exact_resource(self):
        self.plugin.searched({"rows": [row("first"), row("second")], "diagnostics": []})
        captured = []
        with patch.object(
            self.plugin,
            "start",
            side_effect=lambda request, callback: captured.append(request),
        ):
            item = self.plugin.results.item(1)
            QTest.mouseClick(
                self.plugin.results.viewport(),
                Qt.MouseButton.LeftButton,
                pos=self.plugin.results.visualItemRect(item).center(),
            )
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["resource"]["uri"], "second")
        self.assertEqual(len(QgsProject.instance().mapLayers()), 0)

    def test_invalid_layer_is_not_added(self):
        self.plugin.search_status = "1件"
        self.plugin.selected_title = "invalid"
        self.plugin.downloaded({"path": "/not/a/file", "resource": {}, "plan": {}})
        self.assertIn("追加失敗", self.plugin.status.text())
        self.assertEqual(len(QgsProject.instance().mapLayers()), 0)

    def test_local_geojson_layer_crs_and_unload_lifetime(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data.geojson"
            target.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {},
                                "geometry": {"type": "Point", "coordinates": [139, 36]},
                            },
                            {
                                "type": "Feature",
                                "properties": {},
                                "geometry": {"type": "Point", "coordinates": [140, 37]},
                            },
                        ],
                    }
                )
            )
            self.plugin.search_status = "2件"
            self.plugin.selected_title = "parks"
            self.plugin.downloaded(
                {"path": str(target), "resource": {"uri": "selected"}, "plan": {}}
            )
            layers = list(QgsProject.instance().mapLayers().values())
            self.assertEqual(len(layers), 1)
            self.assertEqual(layers[0].featureCount(), 2)
            self.assertEqual(
                json.loads(layers[0].customProperty("rhinestone/resource"))["uri"],
                "selected",
            )
            APP.processEvents()
            self.assertEqual(len(self.iface.canvas.layers()), 1)
            self.assertLess(self.iface.canvas.extent().width(), 2_000_000)
            self.assertTrue(target.exists())
            # Windows cannot delete an OGR source while its layer owns the file.
            # Production caches outlive layers; release the test layer first.
            self.iface.canvas.setLayers([])
            QgsProject.instance().removeAllMapLayers()
            APP.processEvents()

    def test_missing_bundle_is_visible(self):
        with patch.object(
            module.Path, "read_text", side_effect=FileNotFoundError("bundle")
        ):
            self.plugin.query.setText("公園")
            QTest.keyClick(self.plugin.query, Qt.Key.Key_Return)
        self.assertIn("起動できません", self.plugin.status.text())
        self.assertIsNone(self.plugin.process)

    def test_bundled_core_runs_outside_qgis_without_site_packages(self):
        fixture = Path(__file__).parent / "fixtures/unsupported_resource.json"
        self.plugin.start(
            {
                "action": "download",
                "resource": json.loads(fixture.read_text()),
                "target": "/never-written.geojson",
            },
            self.fail,
        )
        wait_until(lambda: self.plugin.process is None)
        self.assertIn("GeoJSON", self.plugin.status.text())
        self.assertIn("追加失敗", self.plugin.status.text())
        self.assertNotIn("rhinestone", sys.modules)

    @unittest.skipUnless(LIVE, "explicit --live required")
    def test_real_search_click_download_ogr(self):
        beats = []
        timer = QTimer()
        timer.timeout.connect(lambda: beats.append(time.monotonic()))
        timer.start(20)
        self.plugin.query.setText("那須塩原市 公園")
        QTest.keyClick(self.plugin.query, Qt.Key.Key_Return)
        self.assertIn("検索中", self.plugin.status.text())
        wait_until(lambda: self.plugin.process is None)
        self.assertGreater(len(beats), 2)
        candidates = [
            self.plugin.results.item(i)
            for i in range(self.plugin.results.count())
            if self.plugin.results.item(i).flags() & Qt.ItemFlag.ItemIsSelectable
        ]
        self.assertGreaterEqual(len(candidates), 2, self.plugin.status.text())
        self.assertEqual(len(QgsProject.instance().mapLayers()), 0)
        selected = candidates[1]
        expected = selected.data(Qt.ItemDataRole.UserRole)["resource"]["uri"]
        QTest.mouseClick(
            self.plugin.results.viewport(),
            Qt.MouseButton.LeftButton,
            pos=self.plugin.results.visualItemRect(selected).center(),
        )
        wait_until(lambda: self.plugin.process is None)
        layers = list(QgsProject.instance().mapLayers().values())
        self.assertEqual(len(layers), 1, self.plugin.status.text())
        layer = layers[0]
        self.assertTrue(layer.isValid())
        self.assertGreater(layer.featureCount(), 0)
        self.assertEqual(
            json.loads(layer.customProperty("rhinestone/resource"))["uri"], expected
        )
        print(
            json.dumps(
                {
                    "source": expected,
                    "features": layer.featureCount(),
                    "crs": layer.crs().authid(),
                    "heartbeat": len(beats),
                },
                ensure_ascii=False,
            )
        )
        QTest.qWait(500)
        APP.processEvents()
        self.assertEqual(len(self.iface.canvas.layers()), 1)
        self.assertLess(self.iface.canvas.extent().width(), 2_000_000)
        if os.environ.get("RHINESTONE_SCREENSHOT"):
            self.iface.window.grab().save(os.environ["RHINESTONE_SCREENSHOT"])
        timer.stop()


if __name__ == "__main__":
    unittest.main()
