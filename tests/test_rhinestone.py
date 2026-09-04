from rhinestone import hello


def test_hello() -> None:
    """公開済みの最小 API がパッケージ導入後も利用できることを保証する。"""
    assert hello() == "Hello from rhinestone!"
