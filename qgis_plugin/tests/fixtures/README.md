# PLATEAU regression fixture

`plateau-saitama-2023-sample.zip` is a subset of the distribution reported by the user:

- Dataset: 3D都市モデル（Project PLATEAU）さいたま市（2023年度）
- Publisher: 国土交通省都市局 / Project PLATEAU
- Dataset ID: `02336364-a110-4fc3-ba0b-1f4eaaf462e7`
- Resource ID: `6c1e9342-c282-462d-9b16-2da5513db3ce`
- Source: https://assets.cms.plateau.reearth.io/assets/f7/838da1-f754-4325-86ef-5b62c788dd94/11100_saitama-shi_city_2023_3dtiles_mvt_1_op.zip
- License/attribution: [Project PLATEAU site policy](https://www.mlit.go.jp/plateau/site-policy/).
  Source credit: 国土交通省 Project PLATEAU. This fixture extracts a subset of the published distribution.
- Retrieved: 2026-11-05.
- Original archive SHA256: `299b3b01c9bcb59f29afda046cbfc5ceac28f28bedd6be8aa1b411dd55dde226`.
- Fixture SHA256: `b6c169198b6435519aef2cd788eb8407bf6b96db6b9fbc365997811b04b12656`.

The complete `tran_3dtiles_lod3` and `squr_mvt_lod2` directories retain their original
paths and file bytes; other models are excluded. JSON, B3DM, and MVT contents are not
rewritten. The ZIP container is recompressed. `../plateau_fixture.py` provides an
optional regeneration helper (`archive_bytes(local_path)` for a downloaded archive).
Normal CI uses this fixed fixture and does not require the live upstream service.

The integration test exercises selection, ZIP download/unpack, logical discovery,
QGIS layer creation and nonempty rendering separately for 3D Tiles and MVT. This
does not claim rendering coverage for every model in the original 12 GB extraction.
