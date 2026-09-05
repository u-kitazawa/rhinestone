"""Inspect the knowledge retained by a resolved Resource."""

from rhinestone import Config, configure
from rhinestone.adapters import DirectAdapter

app = configure(
    dependencies={},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(),
)
resource = app.resolve(
    Config(
        source_type="direct",
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
candidate = resource.source.candidates[0]

print("URI:", resource.uri)
print("format/media type:", resource.format, resource.media_type)
print("resource attributes:", candidate.attributes)
print("metadata:", resource.metadata)
print("source capabilities:", resource.source.capabilities)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)
