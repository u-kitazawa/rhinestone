# PLATEAUのCityGML

## 準備と実行

RhinestoneとGDALのPython bindingsを用意します。G空間情報センターのCKAN Resource IDを
`RHINESTONE_PLATEAU_RESOURCE_ID`に、ZIP内の正確なCityGMLパスを
`RHINESTONE_PLATEAU_CITYGML_MEMBER`に設定し、`python examples/09_plateau_citygml/example.py`を実行します。
HTTP通信は組み込みtransportを使います。

ZIP内のファイル名を必須にすることで、RhinestoneがCityGMLファイルを推測しないことを示します。
