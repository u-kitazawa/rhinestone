# Rhinestone Search for QGIS（実験版）

地域やキーワード・提供元などを指定して検索し、結果を選んで説明・配布情報を確認します。
「選択したデータを追加」ボタンを押すと地図へ追加します。クリックや結果一覧でのEnterだけでは追加しません。
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

## 検索条件と結果の確認

| 条件 | 入力方法 |
| --- | --- |
| キーワード（text） | 省略可能。areaだけの検索も可能 |
| 地域（area） | 行政区域名・別名・コード。例: 神奈川県、横浜市 |
| 提供元（providers） | Coreの組み込みCatalogから複数選択。未選択の提供元へ通信しない |
| 形式（format） | CoreのFormatから複数選択（OR）。未選択なら形式を限定しない |
| 日時（time） | 詳細条件に開始・終了をISO8601で入力。片側省略可。日付だけなら00:00 |
| 範囲（bbox） | 詳細条件に西・南・東・北の経緯度。現在の表示範囲からも取得可能。areaと併用不可 |
| 件数（limit） | 提供元ごとの件数。0の「提供元の既定」は全件保証ではない |

初期選択はsearch.ckan.jp、G空間情報センター、国土地理院です。他の検索対応の組み込みProviderも選べます。ODPT等の直接参照専用Providerは選択できません。
認証が必要なProviderは、未設定の場合に診断を表示します。

## 認証情報・APIキーの設定

パネルの「設定（認証情報・APIキー）」から、認証情報の名前と値を入力し「保存・更新」を押します。
既存の名前を選んで新しい値を保存すると更新、「削除」で登録を削除できます。
入力は伏字で、保存済みの値を画面へ再表示しません。閉じる操作は未保存の入力を破棄します。

現在の組み込み検索では、**国土交通DPFのAPIキーを `mlit-dpf` という名前で登録**して利用します。
登録後、検索の提供元で「国土交通DPF」を選択してください。キー未登録でも他の提供元の検索は継続できます。
認証情報はCoreが参照する名前と単一の文字列値の組です。任意の名前を保存できますが、
対応するProviderが参照しなければ使用しません。登録だけでODPTの検索、OAuthログイン、
ユーザー名・パスワードによるサービス接続や認証付きレイヤー取得が追加されるわけではありません。

QGISの認証データベースへ暗号化保存し、必要な場合はQGIS標準のマスターパスワード入力が開きます。
解除のキャンセル・保存失敗時に平文保存へ切り替えることはありません。
保存は現在のQGIS認証データベースに属し、プロジェクトファイル・通常の設定ファイルへキーを書き込みません。
認証情報を参照する提供元を選択した検索時だけ読み出し、その提供元に必要な値だけを
ローカルworkerの標準入力からCoreのCredential factoryへ渡します。コマンド引数・環境変数・検索結果・
Resource／AccessPlan・レイヤーのカスタムプロパティへ追加しません。
送信先と認証ヘッダーの指定は既存Coreに委ね、認証付きレイヤー取得・タイルの認証は引き続き未対応です。
検索条件の解釈・適用はCoreが担当し、地域・日時等を適用できないProviderは結果一覧と詳細に注意を表示します。

結果一覧の名称・提供者・検索元・形式から対象を選ぶと、説明・更新日・ライセンス・配布URI・識別子と
追加できない理由を詳細欄へ表示します。未対応の結果も内容を読めますが、追加ボタンは無効になります。
「検索結果の名称・説明・提供者で絞り込み」は取得済みの結果内を絞り込むだけで、追加通信は行いません。
結果の選択やダブルクリック・Enterでは取得を開始せず、追加ボタンで選択した配布物だけを取得します。

## 検索と対応範囲

- 選択したProviderをCoreの公開 `search` で検索します。件数の初期値はProviderごとに20配布物です。
  検索語の解釈・ページング・重複除去はCoreが担当します。
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
  API、未対応オプション、形式不明の通常ファイルは理由を表示し、追加を無効にします。
  単独のShapefileは関連ファイルのURLを推測せず、ZIP配布を利用します。
- 複数レイヤーを含む配布物は、取得・内容調査後に「追加するレイヤーを選択」を表示します。
  必要なものをチェックして追加します。初期状態では全件未選択で、キャンセルでは追加しません。
  1レイヤーだけならそのまま追加します。内部名をレイヤー名へ付け、別の検索結果は追加しません。
  Planの `layer` 指定やZIPの `entry_point` があれば、その指定に従います。
  ZIPの `.dbf` をShapefileとは別の表として重複追加しません。`encoding` はベクターへ反映します。
- XYZは提供元を限定しません。Coreの `AccessPlan.options.tile` を優先し、未設定の場合も
  配信URI自体が `{z}/{x}/{y}`（パス・クエリ、percent-encoded表記を含む）のテンプレートなら、
  プラグイン側でポータブルなXYZ AccessPlanを作ります。標準XYZ（EPSG:3857）の画像、
  `.pbf`／`.mvt` またはMVT media typeのベクターに対応します。一般のURLをタイルと推測しません。
  ズーム範囲が定義されていれば保持し、未定義ならQGISの既定値を使用します。非標準CRS・TMS等は未対応です。
  帰属・利用条件は渡された定義からレイヤーのメタデータへ保持します。
- ファイル取得・ZIP展開後の容量に固定上限は設けません。データは逐次取得・展開し、全体をメモリへ保持しません。
  読取タイムアウトは30秒です。多数のタイルを含むZIPを扱うため、ZIP内の固定件数上限も設けません。
  ZIPの外への書き出しや同一パスの上書きを拒否し、ディスク容量不足等の失敗では中間ファイルを削除してエラーを表示します。

### ZIP内の3D Tiles・MVT

3D Tilesは `asset` と `root` を持つJSONを入口として、QGISの3D Tiles providerで開きます。
子tilesetを親とは別レイヤーとして追加せず、同梱された相対参照・ディレクトリ構造を保持します。
ZIP外・外部URLへの参照や、同梱されていない参照先は未対応理由を表示します。
MVTは `format=pbf/mvt`・ズーム範囲を宣言したディレクトリmetadataと、実在する `z/x/y.mvt` または
`z/x/y.pbf` の階層を使い、QGISのローカルXYZベクタータイルレイヤーとして追加します。
方式はXYZに対応し、TMSは未対応表示します。タイル片を数千の独立OGRレイヤーとして追加しません。
モデル名・LODは配布元のディレクトリ名を表示し、名称や配布URLからモデルを推測しません。
対応する入口があることを確認して初めて候補にし、ZIPという形式だけで中身の対応を保証しません。

さいたま市2023年度の「3D Tiles, MVT（v3）」では、取得後に建物・道路・土地利用等の各配布内の入口を
選択します。通常の2DキャンバスでもQGISの3D Tiles描画を利用できます。3D表示はQGIS側の表示設定です。
大容量の配布物は全ZIPの取得・展開に時間とディスク領域を要します。進行中もGUIは応答しますが、
この実装はサーバー上のZIPを部分取得する機能や、選択モデルだけを展開する機能ではありません。
  COGもローカルへ取得してから読みます。Range読み込みは行いません。
- 検索中／取得中／データ確認中／0件／Providerの失敗／追加失敗を別表示にします。
  データ確認はQGISの `QgsProviderSublayerTask` で実行し、通信・展開・内容調査中もQGISを操作できます。
  処理中はパネルの条件変更・再検索・選択・追加を抑制し、無効化時はworkerと内容調査を中止します。
- 成功したファイルはQGISのキャッシュ領域 `rhinestone/layer-*/` に保持します。
  無効化しても既存レイヤーや保存したプロジェクトを壊さないため、自動削除しません。
  長期保存する場合はQGISの通常の保存機能で書き出してください。キャッシュを手動削除すると、
  そのファイルを参照するレイヤー・保存プロジェクトは開けなくなります。
- レイヤーのカスタムプロパティ `rhinestone/resource` と `rhinestone/plan` に選択時の契約を保存します。
  Coreの検索・配信元解釈は再実装せず、QGIS依存はCoreの配布物に追加しません。
  XYZ URLテンプレートの解釈とQGISへの変換はプラグイン側の処理です。

## 再現手順と検証

CIでは、依存同梱ZIPを展開してQGIS側へCoreをインストールせず、実際のQGIS/Qtで
検索条件の受け渡し、詳細表示、明示的な追加、複数レイヤー、形式別読み込み、XYZの実描画を検証します。
UbuntuのQGIS 3.34、conda-forgeのQGIS 4.2.3／Qt 6、Windows公式OSGeo4WのQGIS 3.44 LTR／4.xが対象です。
Windowsでは日本語・空白パスも検証し、3.44ジョブは実行中のmajor/minorを確認します。
これはoffscreen自動操作であり、通常デスクトップでのZIPインストール画面と手動操作は未確認です。

実データの再現手順:

1. パネルの検索欄に `那須塩原市 公園` と入力し、Enter。
2. `【那須塩原市】公園 都市整備` のGeoJSON配布を選び、説明と配布URIを確認。
3. 「選択したデータを追加」を押す。
4. 公園の地点が追加され、表示範囲がレイヤーへ移ることを確認。

出典は[OpenData 那須の公園 都市整備施設](https://opendata-nasu.opendatastack.jp/dataset/shisetu-kouenn-tosisetibi/resource/d94a1299-e0fb-4c9a-9a9f-aac7dcb97763)、
[GeoJSON配布](https://nasu-ckan.s3.amazonaws.com/ckan/resources/d94a1299-e0fb-4c9a-9a9f-aac7dcb97763/011201.json)です。
提供元の更新前の確認では10 feature、EPSG:4979でした。追加レイヤーの記録URIと選択した配布URIの一致を確認してください。
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
上記公開API・配布先へ実通信して検索→詳細確認→追加ボタンとGUIイベントの継続を検証します。
通常CIは提供元の稼働に依存する実通信テストを実行しません。
通常デスクトップの手動受け入れでは、上記4手順、画面応答、選択だけでは追加されず追加ボタンが必要なことを確認してください。
