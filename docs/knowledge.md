# Knowledge Adapter（共有知識アダプター）

Rhinestoneの共有知識は、Source Adapterに直接埋め込まず、独立したKnowledge Adapterとして
注入できます。現在の対象は自治体 identity と time semantics です。

```text
Source Adapter -> KnowledgeAdapterRegistry -> Identity / Time Adapter
```

## 構成

`KnowledgeAdapterDefinition`は、Source/Execution Adapter Definitionと同じくadapter type、factory、
依存関係を持ち、Knowledge種別を追加で宣言します。標準のTime Adapterは自動登録されます。
独自のKnowledge Adapterを使う場合だけ`configure(adapters=...)`へ指定し、同じ種別の標準実装を置き換えます。

```python
from rhinestone import KnowledgeAdapterDefinition, configure
from rhinestone.adapters.knowledge import StandardTimeAdapter

app = configure(
    adapters=(
        KnowledgeAdapterDefinition(
            "official-municipality", make_municipality_adapter, "identity"
        ),
    )
)
```

自治体の公式辞書/APIはRhinestoneへ同梱せず、利用者のfactoryから注入します。標準Time Adapterは
追加設定なしで利用できます。factoryは必要なSource Adapterが初めて知識を利用したときに評価されます。factoryには
`KnowledgeAdapterContext`が渡されます。

## 地域や自治体の識別（Identity）

Identity Adapterは、明示された名称またはコードを`MunicipalityIdentity`へ解決します。
Provider固有のidentifierはcanonical codeとは別に保持してください。unknown、ambiguous、
不正な入力を推測で解決してはいけません。

## 時間の意味（Time）

Time Adapterは、暦年、年度、survey year、as-of dateを別の意味として返します。
`StandardTimeAdapter`は明示的な西暦、和暦、年度、ISO日付だけを扱います。

例えば、`令和2年`はcalendar year 2020、`2020年度`はfiscal year 2020として区別されます。
`令和元年5月1日`はas-of date 2019-05-01として扱い、元号の開始日前や次の元号開始日以後の
日付は拒否します。これはtimezone処理を行う機能ではありません。

## Source Adapterとの境界

PLATEAUと基盤地図情報のSource Adapterは、設定された`municipality`と`time`をKnowledge
Adapterで解決し、候補の`attributes["knowledge"]`へ保持します。Knowledge AdapterはProvider
固有のresource選択、HTTP通信、Runtime、Credentialを担当しません。
