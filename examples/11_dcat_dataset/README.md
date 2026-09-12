# DCATカタログのDataset

## 準備と実行

Rhinestone、`rdflib`、`pyogrio`を用意します。DCATカタログから3つの
`RHINESTONE_DCAT_*_URI`を設定し、`python examples/11_dcat_dataset/example.py`を実行します。
文書の取得には組み込みHTTP通信を使います。

直接取得できるGeoJSONまたはGeoPackageの`downloadURL`を持つDistributionを選んでください。
ランディングページを示す`accessURL`はメタデータとして扱い、開きません。
