# テスト戦略

## 原則

テストは、アーキテクチャ境界の仕様を記述する。Pull Request 用テストは決定的かつ Offline で、任意の地理空間 Binary に依存しない。実環境の Provider を確認するテストは別 Suite とし、通常の Pull Request の必須条件にはしない。

## CKAN の Golden Case

Fixture：

```text
tests/fixtures/ckan/resource_geopackage.json
```

Fixture には、CKAN 仕様の代表的な `resource_show` Response 全体を含める。期待される Plan は不透明な Snapshot として保存せず、Field ごとに Assert する。

必須の検証項目：

1. Mapping の Config から、正確な `CkanResourceReference` が作成される。
2. Adapter は Encoding 済みの `resource_show` URI だけを Request する。
3. 生 Metadata 全体が保持され、呼び出し元による変更から分離される。
4. `GPKG` が `geopackage` になり、`vector.read` が選択される。
5. Binding の選択が Registry への挿入順に依存しない。
6. Planning が Dataset の読み込みも pyogrio の Import も行わない。
7. 実行時に、選択された Fake Loader が正確な Plan で1回だけ呼び出される。
8. `load(config)` が Fake Loader の Object を変更せずに返す。
9. Config と Metadata の入力が、パイプライン全体を通して変更されない。
10. 解決処理を繰り返すと等しい Plan が生成される。

## 異常系 Matrix

少なくとも、次の対象を絞ったテストを用意する。

| 境界 | Case | Error |
| --- | --- | --- |
| Config | `source` がない | `InvalidConfig` |
| Config | 未知の Key | `InvalidConfig` |
| Config | 未知の Source Type | `UnsupportedSourceType` |
| Config | Resource ID が空 | `InvalidConfig` |
| Transport | Timeout | `MetadataUnavailable` |
| CKAN | 不正な JSON | `MetadataUnavailable` |
| CKAN | `success: false` | `MetadataUnavailable` |
| CKAN | 不正な Result | `MetadataInvalid` |
| CKAN | Result ID が不一致 | `MetadataInvalid` |
| Resolve | Format と Media Type がない | `UnsupportedFormat` |
| Resolve | Format と Media Type が競合 | `MetadataInvalid` |
| Resolve | 一致する Binding がない | `CapabilityUnavailable` |
| Execute | 選択済み Binding が消失 | `LoaderUnavailable` |
| Execute | Loader の読み込みに失敗 | `ResourceUnavailable` |

## Test Double

定義された Port では、小さな Fake を使用する。

- Fake HTTP Transport は Request URI を記録し、Decode 済み JSON を返すか Exception を送出する。
- Fake Metadata Adapter は Reference を記録し、固定された Metadata を返す。
- Fake Loader は Plan を記録し、Sentinel Object を返す。
- Fake Capability Registry は明示的な不変 Binding を含む。

Port への Injection の方が仕様を直接表現できる場合、テストから Provider 内部を Monkeypatch してはならない（MUST NOT）。

## Coverage と品質チェック

Repository のコマンドは引き続き次のとおり。

```console
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv build
```

Line Coverage と Branch Coverage 100% はプロジェクトの Guardrail であり、境界に対する Assert の代わりではない。除外 Pragma には文書化された理由が必要である。型チェックにはテストも含め、Fake 実装も意図された Port を満たすようにする。

## Live Test

将来の Live Test は別の Marker（例：`@pytest.mark.live`）を付け、明示的な Opt-in を必須とする。外部サービスの仕様に変化がないことを検証するが、変動する Title、Row Count、Timestamp、Availability を通常の Unit Test の事実として Assert してはならない（MUST NOT）。
