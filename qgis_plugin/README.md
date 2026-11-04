# Rhinestone Search for QGIS（実験版）

検索欄へキーワードを入力してEnter、結果を1回クリックすると地図へ追加します。
キーボードでは結果を選んでEnterで追加できます。「追加」ボタンや確認画面はありません。
AI・MCP・アカウント・独自サーバーは不要です。

## インストール

配布対象はLinux x86_64のQGIS 3.x（3.34以上）／4.xと、Windows x64のQGIS 3.44 LTR／4.x、Python 3.12です。
4.xの実機・CI検証対象はQGIS 4.2.3／Qt 6です。
GitHubの[QGIS plugin workflow](https://github.com/u-kitazawa/rhinestone/actions/workflows/qgis-plugin.yml)
で成功した対象commitのArtifactsから、使用するQGIS系列に合わせてダウンロードし、
**Artifactsの外側のZIPを展開**します。中にあるZIPがプラグインです。

| OS・QGIS | Artifact | 中のプラグインZIP |
| --- | --- | --- |
| Linux 3.x | `rhinestone-qgis-linux-x86_64-py312` | `rhinestone-qgis-linux-x86_64-py312.zip` |
| Linux 4.x | `rhinestone-qgis4-linux-x86_64-py312` | `rhinestone-qgis4-linux-x86_64-py312.zip` |
| Windows x64 3.44 LTR | `rhinestone-qgis344-windows-x86_64-py312` | `rhinestone-qgis344-windows-x86_64-py312.zip` |
| Windows x64 4.x | `rhinestone-qgis4-windows-x86_64-py312` | `rhinestone-qgis4-windows-x86_64-py312.zip` |

QGISの「プラグイン → プラグインの管理とインストール → ZIPからインストール」でそのZIPを選び、
「Rhinestone Search」を有効にします。メニューの「Rhinestone → Rhinestone Search」でパネルを開きます。
GitHubへのサインインがArtifactsの取得に必要になる場合があります。検索・利用にアカウントは不要です。

Coreとそのロック済み依存をZIPへ同梱します。利用者によるpip操作は不要です。
QGIS付属の対応Python実行ファイルが必要です（`sys.prefix/bin/python3` または `python.exe` 等）。
CoreはそのPythonの隔離プロセス（`-I -S`）で実行し、QGISや他プラグインのimport環境を変更しません。
ZIPはOS・CPU・Python minor versionに対応します。不一致・付属Python不足は画面へ表示します。
Windows版は公式OSGeo4WのQGIS 3.44 LTR／4.x、Python 3.12を検証対象とします。
macOS・Windows ARM64・他のPython版は未検証で、現時点の配布サポート対象には含めません。
Qtのimportと列挙値は `qgis.PyQt` のQt 5／6共通APIを使用します。
互換性の指定は `qgisMinimumVersion=3.34`／`qgisMaximumVersion=4.99` です。
公式QGISプラグインリポジトリへの登録は行っていません。

WindowsのQGIS 3.44では `rhinestone-qgis344-windows-x86_64-py312`、
QGIS 4.xでは `rhinestone-qgis4-windows-x86_64-py312` を選んでください。Linux用ZIPは使用できません。
外側ZIPをエクスプローラーの「すべて展開」で展開し、中のZIPをQGISの「ZIPからインストール」へ指定します。
QGIS付属Pythonは「ヘルプ → バージョン情報」で確認できます。3.12以外の場合、対応しないZIPは起動時に拒否します。
Pythonやpipを別途インストールする必要はありません。

## 検索と対応範囲

- 検索先は組み込みのsearch.ckan.jp、G空間情報センター、国土地理院。Coreの公開 `search` を呼び、
  各Provider最大20配布物を表示します。検索語の解釈・ページング・重複除去はCoreが担当します。
- 選択は一覧の行に保持したResourceへ対応し、暗黙の先頭選択はありません。
  表示はデータ名／提供元／形式。行番号とツールチップの配布URI・Referenceで同名配布を区別できます。
- ファイルをバックグラウンドで取得し、QGISのOGR/GDALで実際のレイヤーを調べます。
  GeoJSON専用の制限はありません。宣言された形式を拡張子として保存し、ドライバーの判断へ渡します。
  一般ファイルのURL拡張子から形式を推測したり、形式変換したりしません。

| 配信 | 扱い |
| --- | --- |
| GeoJSON、JSON、GeoPackage、FlatGeobuf、GML／CityGML、KML、GPX、DXFなど | インストール済みOGRドライバーで読む |
| CSV、XLS／XLSXなど | 対応OGRドライバーで表として読む。座標列から勝手に地物を作らない |
| GeoTIFF／COG、NetCDF、JPEG／PNG、ASCII Gridなど | インストール済みGDALドライバーで読む |
| ZIP、ZIP内Shapefile・MapInfo・FileGDBなど | 関連ファイルとディレクトリを保持して展開し、QGISのファイルフィルターに合うデータを調べる |
| XYZ画像タイル、XYZ MVTベクタータイル | QGISのネイティブなタイルレイヤー。表示範囲だけ取得する |

- 対応候補であっても、そのQGISに必要なドライバーがない・配布物が破損している場合は追加失敗になります。
  「GDALで読める全形式を全環境で保証」という意味ではありません。認証付き配信、WMS／WMTS／WFS、
  API、未対応オプション、形式不明の通常ファイルは理由を表示して選択不可にします。
  単独のShapefileは関連ファイルのURLを推測せず、ZIP配布を利用します。
- 複数レイヤーを含む配布物は、その配布物の全レイヤーをまとめて追加します。内部名をレイヤー名へ付け、
  別の検索結果は追加しません。Planの `layer` 指定やZIPの `entry_point` があれば、その指定に従います。
  ZIPの `.dbf` をShapefileとは別の表として重複追加しません。`encoding` はベクターへ反映します。
- XYZは提供元を限定しません。Coreの `AccessPlan.options.tile` を優先し、未設定の場合も
  配信URI自体が `{z}/{x}/{y}`（パス・クエリ、percent-encoded表記を含む）のテンプレートなら、
  プラグイン側でポータブルなXYZ AccessPlanを作ります。標準XYZ（EPSG:3857）の画像、
  `.pbf`／`.mvt` またはMVT media typeのベクターに対応します。一般のURLをタイルと推測しません。
  ズーム範囲が定義されていれば保持し、未定義ならQGISの既定値を使用します。非標準CRS・TMS等は未対応です。
  帰属・利用条件は渡された定義からレイヤーのメタデータへ保持します。
- ファイルの取得上限は512 MiB、読取タイムアウト30秒。ZIPは展開後1 GiB・4096エントリーまで。
  ZIPの外への書き出しや同一パスの上書きを拒否し、失敗途中のファイルは削除します。
  COGもローカルへ取得してから読みます。Range読み込みは行いません。
- 検索中／取得中／データ確認中／0件／Providerの失敗／追加失敗を別表示にします。
  データ確認はQGISの `QgsProviderSublayerTask` で実行し、通信・展開・内容調査中もQGISを操作できます。
  処理中はパネルの再検索・選択を抑制し、無効化時はworkerと内容調査を中止します。
- 成功したファイルはQGISのキャッシュ領域 `rhinestone/layer-*/` に保持します。
  無効化しても既存レイヤーや保存したプロジェクトを壊さないため、自動削除しません。
  長期保存する場合はQGISの通常の保存機能で書き出してください。キャッシュを手動削除すると、
  そのファイルを参照するレイヤー・保存プロジェクトは開けなくなります。
- レイヤーのカスタムプロパティ `rhinestone/resource` と `rhinestone/plan` に選択時の契約を保存します。
  Coreの検索・配信元解釈は再実装せず、QGIS依存はCoreの配布物に追加しません。
  XYZ URLテンプレートの解釈とQGISへの変換はプラグイン側の処理です。

## 再現手順と検証

2026-11-02、隔離したconda-forge QGIS 3.44.14、Python 3.12.16、Qt 5.15.15、GDAL 3.13.3、Linux x86_64で、
依存同梱ZIPを展開し、QGIS側へCoreをインストールせずに実QGIS/Qtの自動操作を検証しました。
これはoffscreenでの自動受け入れテストであり、通常デスクトップのZIPインストール画面と手動操作は未確認です。
Ubuntu標準QGIS 3.34.4による回帰テストに加え、conda-forge QGIS 4.2.3／Qt 6の
依存同梱ZIPを使う回帰テストも上記workflowで実行します。
Windows CIでは公式OSGeo4Wの `qgis-ltr`（3.44）と `qgis`（4.x）をそれぞれ導入し、
系列に対応する `python-qgis-ltr.bat`／`python-qgis.bat` で実行します。
3.44ジョブは実行中のQGISのmajor/minorも確認し、別のLTR系列を成功扱いにしません。
Windowsで生成したZIPを
空白・日本語を含むフォルダーへ展開して同じテストを実行します。

2026-11-03、QGIS 4.2.3／Python 3.12.16／Qt 6.11.2／GDAL 3.13.3で、
同じ実データのEnter検索→1クリック追加・10 feature・選択URI一致・GUIイベントの継続を
検証しました。Qt 6の実体を使い、QGIS 3.xが混入した環境を成功扱いにしないチェックも行います。

実データの再現手順:

1. パネルの検索欄に `那須塩原市 公園` と入力し、Enter。
2. `【那須塩原市】公園 都市整備` のGeoJSON配布を1回クリック。
3. 那須塩原市の公園10地点が追加され、表示範囲がレイヤーへ移ることを確認。

出典は[OpenData 那須の公園 都市整備施設](https://opendata-nasu.opendatastack.jp/dataset/shisetu-kouenn-tosisetibi/resource/d94a1299-e0fb-4c9a-9a9f-aac7dcb97763)、
[GeoJSON配布](https://nasu-ckan.s3.amazonaws.com/ckan/resources/d94a1299-e0fb-4c9a-9a9f-aac7dcb97763/011201.json)です。
2026-11-02の検証では一覧2件目をクリックし、追加レイヤーの記録URIと選択URIの一致、10 feature、EPSG:4979を確認しました。
検索結果の順序・件数・配布内容は提供元の更新で変わります。結果の名称・配布URIで対象を確認してください。
ライセンス・帰属表示は配布元の記載に従ってください。

## 開発と配布ZIPの生成

対象OS・CPU・QGISと同じPython minor版の環境で、開発者がuvを利用して生成します。
以下は利用者のインストール操作ではありません。

```console
python3 scripts/build_qgis_plugin.py --output /tmp/rhinestone-qgis-linux-x86_64-py312.zip
uv run pytest qgis_plugin/tests/test_worker.py --no-cov
python3 -m zipfile -e /tmp/rhinestone-qgis-linux-x86_64-py312.zip /tmp/qgis-plugin
RHINESTONE_PLUGIN_DIR=/tmp/qgis-plugin/rhinestone_search QT_QPA_PLATFORM=offscreen python3 qgis_plugin/tests/check_qgis.py
```

QGISのPythonモジュールが環境の既定パスにない場合は、配布元の設定に合わせて
`PYTHONPATH` と `QGIS_PREFIX_PATH` を設定します。`--live` を最後のコマンドへ追加すると、
上記公開API・配布先へ実通信してEnter検索→1クリック追加とGUIイベントの継続を検証します。
通常CIは提供元の稼働に依存する実通信テストを実行しません。
通常デスクトップの手動受け入れでは、上記3手順、画面応答、追加ボタン・確認画面が不要であることも確認してください。
