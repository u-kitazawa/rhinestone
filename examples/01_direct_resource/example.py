"""Resolve a fully described direct resource without network access."""

from rhinestone import Reference, configure

app = configure()
resource = app.load(
    Reference(
        provider_id="direct",
        parameters={
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
