# APIの安定性とリリース運用

Rhinestoneは現在`0.1.x`のAlphaです。この文書は、利用者がアップグレードの影響を判断できるように、公開APIの範囲、変更の知らせ方、リリースの正本を定めます。

## 0.1.xのAPI安定性

`0.1.x`では、公開APIの破壊的変更を許容します。0.1.xの互換性契約は、すべての変更を後方互換にすることではなく、利用者に影響する変更をリリース単位で明示することです。

### 公開APIの範囲

次のsurfaceを利用者向けの公開APIとして扱います。

- `rhinestone`パッケージの`__all__`に含まれる名前
- 利用者向けガイドと[APIリファレンス](api.md)に記載された関数、クラス、引数、戻り値、データ項目
- [対応状況](compatibility.md)および各Adapterリファレンスに記載された利用方法

`src/rhinestone/`に存在することだけでは、公開APIであることを意味しません。`_`で始まるmoduleや名前、
Resolver、Registry、Adapterの内部実装は、公開ドキュメントで明示されない限り内部APIです。`Config`などの
トップレベル中核APIと、各サブモジュールの`__all__`に含まれる拡張APIは、それぞれのsurfaceの契約に従います。
内部実装を直接利用したコードの互換性は保証しません。

公開APIの追加・変更・削除では、実装、テスト、該当する利用者向けドキュメントを同じ変更で更新します。

### 変更の扱い

- 破壊的変更は`0.1.x`でも許容しますが、GitHub Release notesの`Removed / Breaking changes`または`Changed`に利用者への影響と移行方法を記載します。
- deprecation periodは`0.1.x`の必須条件にしません。deprecated APIを導入する場合は`Deprecated`に対象、代替手段、削除予定または判断条件を記載します。
- セキュリティ修正や設計上の緊急対応で段階的な廃止ができない場合も、変更の影響と必要な対応をRelease notesに記載します。
- 内部実装の変更は、公開APIの挙動や利用者の設定・依存関係に影響しない限り、Release notesへの個別記載を必須にしません。

トップレベルsurfaceとサブモジュールの拡張surfaceは別の契約として扱います。トップレベルの
`__all__`は通常利用・設定導線のための小さな語彙を示し、低レベル型やAdapter契約は
`rhinestone.models`、`rhinestone.adapters.contracts`、`rhinestone.adapters.knowledge`、
`rhinestone.security`、`rhinestone.representations`の各`__all__`で公開します。サブモジュール
経由の拡張APIは低レベルですが、これらの文書化されたsurfaceでは互換性を追跡します。

`0.2.0`以降は、必要に応じて各surfaceの安定性を個別に見直します。`1.0.0`では、公開APIと
互換性の基準を別途見直し、安定版としての契約を定めます。具体的なリリース時期はこの文書では決めません。

## 変更履歴の正本

GitHub Releaseを、各versionの利用者向け変更履歴の正本とします。独立した`CHANGELOG.md`は作成せず、Release notesと別の履歴を二重に管理しません。

各GitHub Releaseでは、次の見出し（英語の固定ラベル）を使用します。該当する変更がない見出しは省略できます。

- `Added`（追加）
- `Changed`（変更）
- `Fixed`（修正）
- `Deprecated`（非推奨）
- `Removed / Breaking changes`（削除／互換性を壊す変更）

Release notesには、少なくとも次を記載します。

- 利用者が認識できる変更の概要
- 公開API、設定、依存関係、対応範囲への影響
- 破壊的変更がある場合の影響対象と移行方法
- 必要なcredential、runtime、環境変数などの変更

GitHub Release作成時は`Generate release notes`を初期値として利用し、上記の見出しに整理してからPublishします。PRとIssueには、Release notesで追跡できる変更の背景と影響を記載します。

## version、tag、Release、PyPIの関係

これらは同じversionを表さなければなりません。

1. `pyproject.toml`の`project.version`を次のversionに更新し、`develop`へ統合します。
2. `develop`から`main`へのrelease promotion PRを作成し、公開対象のcommitを`main`へ統合します。
3. `main`上の同じcommitに`v<project.version>`形式のtagを付けます。
4. そのtagを対象にGitHub Releaseを作成し、Release notesを整理してPublishします。
5. `release.published`を起点にPublish workflowがtagをcheckoutして配布物をbuildし、PyPIへ公開します。

Publish workflowは、Release tagの`v`を除いたversionが`pyproject.toml`のversionと一致すること、tagのcommitが`main`の履歴上にあること、buildされたwheelとsdistのversionが一致することを検証します。不一致の場合はPyPI公開を行いません。

GitHub ReleaseをPublishした後にnotesを編集しても、すでにPyPIへ公開された配布物は変更されません。公開後の訂正は、必要に応じてnotesの修正と次versionのFixedで行います。

## v0.1.0の変更履歴

v0.1.0は初回Releaseです。初回Release notesでは、少なくとも次の主要変更を利用者が追跡できるようにします。

- `Catalog`、`Provider`、`Result`、`Resource`を中心とした公開語彙と、検索からResource解決までの利用導線
- CKAN、DCAT、Direct、ODPT、OGC API Features、PLATEAU、STAC、静的SourceなどのSource対応範囲
- 組み込みHTTP、外部Runtimeの注入、Credentialの分離、およびResourceのExecution Adapter連携
- package metadata、wheel検証、GitHub Actionsによるテスト・ドキュメント・PyPI公開workflow
- Catalog由来の宛先制限を含む、認証付きSourceとネットワークポリシーの利用契約

これらはv0.1.0のRelease notesの`Added`または`Changed`に整理します。以降のversionでは、初回Releaseから変わった公開surfaceを同じ形式で追跡します。

## v0.1.1の変更履歴

### Removed / Breaking changes

トップレベルの再エクスポートを通常利用・設定導線へ整理しました。`Source`、
`ResourceCandidate`、`AccessPlan`系、`Metadata`、`Provenance`、`SearchQuery`、Runtime型、
Adapter／Knowledge Adapter契約、`DestinationPolicy`、format定義・正規化関数、
`SourceDefinition` は `rhinestone` から削除されています。

これらを使うコードは、次の移行先へimportを変更してください。

- ドメイン型・Runtime型: `rhinestone.models`
- Adapter Definition／Context／Factory: `rhinestone.adapters.contracts`
- Knowledge Adapter: `rhinestone.adapters.knowledge`
- 宛先ポリシー: `rhinestone.security`
- format定義・正規化: `rhinestone.representations`

`Provider`が通常利用における提供元定義の正式名です。`SourceDefinition`を使っていた設定例は
`Provider`へ置き換えてください。0.1.xでもbreaking changeを許容する方針に基づき、0.2まで
旧トップレベルimportを残す段階的廃止は行いません。
