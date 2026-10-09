"""Inspect the knowledge retained by a resolved Resource."""

from rhinestone import Config, configure

app = configure()
resource = app.resolve(
    Config(
        source_id="direct",
        settings={
            "uri": "https://example.invalid/rivers.zip",
            "format": "shapefile",
            "media_type": "application/zip",
            "archive": "zip",
            "encoding": "cp932",
            "layer": "rivers",
            "metadata": {"title": "Rivers", "license": "CC BY 4.0"},
        },
    )
)
print("URI:", resource.uri)
print("format/media type:", resource.format, resource.media_type)
print("reference:", resource.reference)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("access options:", resource.access_plan.options if resource.access_plan else {})
print("provenance:", resource.provenance)
