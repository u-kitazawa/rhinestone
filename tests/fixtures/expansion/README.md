# Adapter expansion fixtures

These are synthetic, minimal examples of official structures, not snapshots of
live datasets or complete schema-conformance samples. Identifiers containing
`fixture` must never be sent to a live service.

- `plateau.json`: CKAN Action API package response. Reference:
  https://front.geospatial.jp/wp-content/uploads/2022/03/gic-api.pdf
- `catalog.ttl`: DCAT Dataset/Distribution, including an accessURL-only landing
  page that must not be opened as a file. https://www.w3.org/TR/vocab-dcat-3/
- `city.gml`: CityGML 2.0 Building with a GML footprint:
  https://schemas.opengis.net/citygml/2.0/
- `basic.xml`: GSI basic building-area geometry structure:
  https://service.gsi.go.jp/kiban/app/help/
- `odpt.json`: ODPT station response vocabulary and array shape:
  https://developer.odpt.org/documents

Contract tests assert explicit Source, candidate, AccessPlan and open results.
The GML samples exercise reader compatibility, not full PLATEAU/GSI validation.
