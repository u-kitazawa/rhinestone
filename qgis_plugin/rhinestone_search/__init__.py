"""QGIS entry point; Core dependencies run in an isolated local worker."""


def classFactory(iface):
    from .plugin import RhinestonePlugin

    return RhinestonePlugin(iface)
