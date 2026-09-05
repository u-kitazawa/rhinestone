# PLATEAU CityGML

## Setup

Install Rhinestone, `requests`, and GDAL Python bindings. Set
`RHINESTONE_PLATEAU_RESOURCE_ID` to an official G Spatial Information Center
CKAN resource ID and `RHINESTONE_PLATEAU_CITYGML_MEMBER` to the exact CityGML
path in its ZIP archive. Run `python examples/09_plateau_citygml/example.py`.

The archive member is required so the example never guesses a CityGML file.
