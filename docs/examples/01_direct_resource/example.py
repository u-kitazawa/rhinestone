"""Resolve a fully described direct resource without network access."""

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
            "uri": "https://example.invalid/data.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
            "metadata": {"title": "Known boundaries", "publisher": "Example"},
        },
    )
)

print("URI:", resource.uri)
print("format:", resource.format)
print("metadata:", resource.metadata)
print("provenance:", resource.provenance)
