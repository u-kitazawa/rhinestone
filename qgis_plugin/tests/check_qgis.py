"""Run with QGIS's Python after extracting the distribution ZIP.

RHINESTONE_PLUGIN_DIR points to extracted rhinestone_search. Optional --live uses
search.ckan.jp and the selected publisher's real HTTP endpoint.
"""

import configparser
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsProject,
)
from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas
from qgis.PyQt.QtCore import QT_VERSION_STR, QEvent, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QImage
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
if os.environ.get("RHINESTONE_QGIS_VERSION"):
    expected = tuple(
        int(part) for part in os.environ["RHINESTONE_QGIS_VERSION"].split(".")
    )
    actual = (Qgis.QGIS_VERSION_INT // 10000, Qgis.QGIS_VERSION_INT // 100 % 100)
    assert actual[: len(expected)] == expected, (Qgis.QGIS_VERSION, expected)
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


def portable(uri, format, options=None):
    value = json.loads(
        (Path(__file__).parent / "fixtures/unsupported_resource.json").read_text()
    )
    value["uri"] = uri
    value["format"] = format
    value["access_plan"].update(uri=uri, format=format, options=options or {})
    value["reference"]["parameters"].update(uri=uri, format=format)
    return value


class FixtureServer:
    def __init__(self, data):
        self.hits = []
        hits = self.hits

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"


def vector_fixture(path, driver, names=("points",)):
    from osgeo import ogr, osr

    data = ogr.GetDriverByName(driver).CreateDataSource(str(path))
    crs = osr.SpatialReference()
    crs.ImportFromEPSG(4326)
    crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    for name in names:
        layer = data.CreateLayer(name, crs, ogr.wkbPoint)
        layer.CreateField(ogr.FieldDefn("name", ogr.OFTString))
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("name", "selected")
        feature.SetGeometry(ogr.CreateGeometryFromWkt("POINT (139 36)"))
        assert layer.CreateFeature(feature) == 0
        feature = None
        layer = None
    data = None


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
        self.iface.canvas.stopRendering()
        self.iface.canvas.setLayers([])
        QgsProject.instance().removeAllMapLayers()
        self.iface.window.close()
        self.iface.window.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        del self.plugin, self.iface

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
        wait_until(lambda: not self.plugin.busy())
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
            wait_until(lambda: not self.plugin.busy())
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
        wait_until(lambda: not self.plugin.busy())
        self.assertIn("未対応", self.plugin.status.text())
        self.assertIn("追加失敗", self.plugin.status.text())
        self.assertNotIn("rhinestone", sys.modules)

    def add_distribution(self, data, format, options=None):
        with FixtureServer(data) as server:
            uri = server.url + "/selected"
            selected = portable(uri, format, options)
            self.plugin.results.clear()
            self.plugin.searched(
                {
                    "rows": [
                        {
                            "resource": selected,
                            "title": "選択した配布",
                            "provider": "fixture",
                            "format": format,
                            "reason": None,
                        }
                    ],
                    "diagnostics": [],
                }
            )
            item = self.plugin.results.item(0)
            QTest.mouseClick(
                self.plugin.results.viewport(),
                Qt.MouseButton.LeftButton,
                pos=self.plugin.results.visualItemRect(item).center(),
            )
            wait_until(lambda: not self.plugin.busy())
            self.assertIn("追加しました", self.plugin.status.text())
            self.assertEqual(server.hits, ["/selected"])
            layers = list(QgsProject.instance().mapLayers().values())
            for layer in layers:
                self.assertTrue(layer.isValid())
                self.assertEqual(
                    json.loads(layer.customProperty("rhinestone/resource")), selected
                )
            return layers

    def release_layers(self):
        self.iface.canvas.setLayers([])
        QgsProject.instance().removeAllMapLayers()
        APP.processEvents()

    def test_vector_drivers_through_selected_resource_and_worker(self):
        cases = [
            ("GPKG", "gpkg", ".gpkg"),
            ("FlatGeobuf", "flatgeobuf", ".fgb"),
            ("GML", "gml", ".gml"),
            ("KML", "kml", ".kml"),
            ("GPX", "gpx", ".gpx"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for driver, format, suffix in cases:
                with self.subTest(driver=driver):
                    path = Path(directory) / ("data" + suffix)
                    vector_fixture(path, driver)
                    layers = self.add_distribution(path.read_bytes(), format)
                    self.assertGreaterEqual(len(layers), 1)
                    self.assertEqual(sum(layer.featureCount() for layer in layers), 1)
                    self.release_layers()

    def test_multiple_gpkg_layers_and_explicit_layer_selector(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multi.gpkg"
            vector_fixture(path, "GPKG", ("first", "second"))
            layers = self.add_distribution(path.read_bytes(), "gpkg")
            self.assertEqual(len(layers), 2)
            self.assertEqual(
                {layer.name() for layer in layers},
                {"選択した配布 — first", "選択した配布 — second"},
            )
            self.release_layers()
            layers = self.add_distribution(
                path.read_bytes(), "gpkg", {"layer": "second"}
            )
            self.assertEqual(len(layers), 1)
            self.assertIn("second", layers[0].source())
            self.release_layers()

    def test_zip_shapefile_nested_sidecars_and_multiple_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shape = root / "日本語"
            shape.mkdir()
            vector_fixture(shape / "points.shp", "ESRI Shapefile")
            vector_fixture(root / "second.geojson", "GeoJSON")
            archive_path = root / "data.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for path in [*shape.iterdir(), root / "second.geojson"]:
                    archive.write(path, path.relative_to(root))
            layers = self.add_distribution(archive_path.read_bytes(), "zip")
            self.assertEqual(len(layers), 2)  # .dbf is a sidecar, not a third table.
            self.assertTrue(all(layer.featureCount() == 1 for layer in layers))
            self.release_layers()
            layers = self.add_distribution(
                archive_path.read_bytes(),
                "shapefile",
                {"archive": "zip", "entry_point": "日本語/points.shp"},
            )
            self.assertEqual(len(layers), 1)
            self.release_layers()

    def test_csv_is_a_table_without_inventing_geometry(self):
        layers = self.add_distribution(b"name,x,y\npark,139,36\n", "csv")
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].featureCount(), 1)
        self.assertFalse(layers[0].isSpatial())
        self.release_layers()

    def test_raster_and_netcdf_drivers(self):
        from osgeo import gdal, osr

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raster.tif"
            dataset = gdal.GetDriverByName("GTiff").Create(
                str(path), 2, 2, 1, gdal.GDT_Byte
            )
            dataset.SetGeoTransform((139, 0.01, 0, 36, 0, -0.01))
            crs = osr.SpatialReference()
            crs.ImportFromEPSG(4326)
            dataset.SetProjection(crs.ExportToWkt())
            dataset.GetRasterBand(1).Fill(42)
            dataset = None
            cog = Path(directory) / "cloud.tif"
            dataset = gdal.Translate(str(cog), str(path), format="COG")
            dataset = None
            for format, fixture in (("geotiff", path), ("cog", cog)):
                layers = self.add_distribution(fixture.read_bytes(), format)
                self.assertEqual(len(layers), 1)
                self.assertEqual(layers[0].type(), Qgis.LayerType.Raster)
                self.assertEqual(layers[0].width(), 2)
                self.release_layers()
            nc = Path(directory) / "data.nc"
            if gdal.GetDriverByName("netCDF") is not None:
                dataset = gdal.Translate(str(nc), str(path), format="netCDF")
                dataset = None
                layers = self.add_distribution(nc.read_bytes(), "netcdf")
                self.assertTrue(layers)
                self.assertTrue(
                    all(layer.type() == Qgis.LayerType.Raster for layer in layers)
                )
                self.release_layers()

    def test_generic_xyz_template_preserves_query_and_renders_visible_tiles(self):
        from qgis.core import QgsMapRendererSequentialJob, QgsRectangle
        from qgis.PyQt.QtCore import QSize

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tile.png"
            image = QImage(256, 256, QImage.Format.Format_RGB32)
            image.fill(QColor("#12ab34"))
            image.save(str(path))
            with FixtureServer(path.read_bytes()) as server:
                template = server.url + "/{z}/{x}/{y}.png?key=a&other=b"
                selected = portable(template, "unknown")
                self.plugin.selected_title = "Other publisher XYZ"
                self.plugin.search_status = "1件"
                self.plugin.start(
                    {
                        "action": "download",
                        "resource": selected,
                        "target": str(Path(directory) / "unused"),
                    },
                    self.plugin.downloaded,
                )
                wait_until(lambda: not self.plugin.busy())
                layers = list(QgsProject.instance().mapLayers().values())
                self.assertEqual(len(layers), 1, self.plugin.status.text())
                layer = layers[0]
                parsed = QgsDataSourceUri()
                parsed.setEncodedUri(layer.source())
                self.assertEqual(parsed.param("url"), template)
                self.assertFalse((Path(directory) / "unused").exists())
                settings = self.iface.canvas.mapSettings()
                settings.setLayers([layer])
                settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
                settings.setExtent(QgsRectangle(-100000, -100000, 100000, 100000))
                settings.setOutputSize(QSize(256, 256))
                job = QgsMapRendererSequentialJob(settings)
                job.start()
                wait_until(lambda: not job.isActive())
                self.assertTrue(server.hits)
                self.assertEqual(
                    job.renderedImage().pixelColor(128, 128).name(), "#12ab34"
                )
                self.assertLess(len(server.hits), 30)
                self.release_layers()

    def test_mvt_xyz_layer_and_zoom_limits(self):
        from qgis.core import QgsMapRendererSequentialJob, QgsRectangle
        from qgis.PyQt.QtCore import QSize

        # Minimal valid MVT: one point in the center of a 4096-unit tile.
        feature = b"\x08\x01\x18\x01\x22\x05\x09\x80\x20\x80\x20"
        layer_data = (
            b"\x0a\x06points\x12"
            + bytes([len(feature)])
            + feature
            + b"\x28\x80\x20\x78\x02"
        )
        mvt = b"\x1a" + bytes([len(layer_data)]) + layer_data
        with FixtureServer(mvt) as server:
            self.plugin.selected_title = "Vector XYZ"
            self.plugin.search_status = "1件"
            tile = {
                "scheme": "xyz",
                "url": server.url + "/{z}/{x}/{y}.pbf",
                "format": "pbf",
                "min_zoom": 2,
                "max_zoom": 14,
                "attribution": "Publisher",
            }
            self.plugin.downloaded(
                {"tile": tile, "resource": {}, "plan": {"options": {"tile": tile}}}
            )
            layers = list(QgsProject.instance().mapLayers().values())
            self.assertEqual(len(layers), 1, self.plugin.status.text())
            self.assertEqual(layers[0].type(), Qgis.LayerType.VectorTile)
            self.assertEqual(layers[0].sourceMinZoom(), 2)
            self.assertEqual(layers[0].sourceMaxZoom(), 14)
            self.assertEqual(layers[0].metadata().rights(), ["Publisher"])
            self.assertTrue(layers[0].renderer().styles())
            # This fixture's point is centered in every requested tile.
            settings = self.iface.canvas.mapSettings()
            settings.setLayers(layers)
            settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
            settings.setExtent(QgsRectangle(4_000_000, 4_000_000, 6_000_000, 6_000_000))
            settings.setOutputSize(QSize(256, 256))
            job = QgsMapRendererSequentialJob(settings)
            job.start()
            wait_until(lambda: not job.isActive())
            self.assertTrue(server.hits)
            self.release_layers()

    @unittest.skipUnless(LIVE, "explicit --live required")
    def test_real_search_click_download_ogr(self):
        beats = []
        timer = QTimer()
        timer.timeout.connect(lambda: beats.append(time.monotonic()))
        timer.start(20)
        self.plugin.query.setText("那須塩原市 公園")
        QTest.keyClick(self.plugin.query, Qt.Key.Key_Return)
        self.assertIn("検索中", self.plugin.status.text())
        wait_until(lambda: not self.plugin.busy())
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
        wait_until(lambda: not self.plugin.busy())
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
    program = unittest.main(exit=False)
    APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    APP.processEvents()
    APP.exitQgis()
    sys.exit(not program.result.wasSuccessful())
