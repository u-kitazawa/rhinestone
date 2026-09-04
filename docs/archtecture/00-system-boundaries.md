# システム境界

## 目的

Rhinestone は、事前に特定されたデータ参照を、説明可能かつ再現可能なアクセスプランへ解決し、そのプランを既存 OSS に委譲して実行する。データの探索、閲覧 UI、再配布、汎用 ETL はシステム境界の外に置く。

## 処理境界

| 段階 | 入力 | 出力 | 許可される副作用 |
| --- | --- | --- | --- |
| Parse | Mapping | Config | なし |
| Reference | Config | DataReference | なし |
| Inspect | DataReference | SourceMetadata | Metadata I/O |
| Resolve | Reference、Metadata、Requirements、Capabilities | AccessPlan | なし |
| Execute | AccessPlan、Loader Registry | Data | Dataset I/O、選択済み任意 OSS の Import |

パイプラインは一方向でなければならない（MUST）。後段の結果を使って Config、Reference、Metadata、Plan を変更してはならない（MUST NOT）。再試行する場合も Plan を書き換えず、新しい実行試行として扱う。

## 依存方向

```text
Interface / Composition
  -> Application
       -> Ports
       -> Domain
  -> Adapters -> Ports
  -> External systems and OSS
```

依存は内側の抽象へ向ける。Domain は他の階層を Import しない。Application は具体的な配信元、通信クライアント、Loader ライブラリを知らない。Adapters は Domain と対応する Port に依存してよいが、別種の Adapter を直接選択または呼び出してはならない（MUST NOT）。Interface / Composition だけが具象 Adapter を組み合わせてよい。

## I/O 所有権

- Metadata I/O は Metadata Adapter だけが開始する（MUST）。Transport Adapter は要求された通信を実行するが、何を検査するかを決めない。
- Dataset I/O は Loader Adapter だけが開始する（MUST）。Resolver と Metadata Adapter はデータ本体を開いてはならない（MUST NOT）。
- Filesystem の探索、URL 接尾辞による推測、HTML スクレイピング、候補検索を Core の判断材料にしてはならない（MUST NOT）。
- 任意依存の Import は Loader の構築時または実行時に限定する（MUST）。Planning は外部 Loader ライブラリを Import してはならない（MUST NOT）。

## システム不変条件

1. Config はユーザーが表明した事実だけを保持し、不変である。
2. DataReference は対象の識別だけを担い、取得方法や Loader 情報を持たない。
3. SourceMetadata は配信元が表明した事実と Provenance を保持し、生 Metadata を不用意に失わない。
4. Resolver はデータ本体を読まず、明示された Metadata と Capability だけで Plan を決める。
5. AccessPlan は実行に必要な選択を完了し、判断理由を機械可読に説明できる。
6. Loader は Plan を実行するだけで、Resource、Format、Protocol、代替 Loader を選択しない。
7. 同じ意味の Config、Metadata、Requirements、Capability 集合からは等しい Plan が得られる。
8. 不確実な場合は推測せず、固有のエラーで失敗するか、仕様化された明示 Opt-in を要求する。
9. 暗黙の形式変換、CRS 変換、Schema 正規化を行わない。
10. 秘密情報を Config、Domain Value、Plan、Error Context に保存しない。

## 決定性

Resolver の意味は次の純粋関数として扱う。

```text
resolve(reference, metadata, requirements, capabilities)
  -> access_plan | resolution_error
```

選択候補には完全順序を定義しなければならない（MUST）。同順位を Registry の挿入順、Hash 順、Import 順で解決してはならない（MUST NOT）。時刻、通信ヘッダー、ローカルパスのような観測情報は、仕様で意味的入力と定義されない限り Plan の等価性へ影響してはならない（MUST NOT）。

## 失敗の境界

予期される失敗は原因別の `RhinestoneError` 派生型として公開する。最も早い段階で確認できる問題を先に報告し、同一 Value 内では仕様に記載した Field 順で最初の問題を報告する。外部例外を境界エラーへ変換するときは Exception Chaining で原因を保持する一方、Credential、Header、データ本体、無制限の Response を診断情報へ含めてはならない（MUST NOT）。

## 適合確認

各垂直スライスは、少なくとも次を Offline Test で証明しなければならない（MUST）。

- 入力 Value が全段階で変更されない。
- Planning 中に Dataset I/O と任意 Loader Import が発生しない。
- 同じ入力から等しい Plan が生成される。
- Loader は選択済み Plan でちょうど1回呼ばれ、戻り値が変更されない。
- 各境界の失敗が対応する固有 Error になる。
- Registry の登録順を変えても結果が変わらない。
