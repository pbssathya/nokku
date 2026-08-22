from nokku.lottery.kerala import DrawRecord, KeralaLotteryStore


def test_store_detects_internal_gap_and_next_expected(tmp_path):
    store = KeralaLotteryStore(tmp_path / "nokku.db")

    store.upsert_draw(DrawRecord(draw_serial=75341))
    store.upsert_draw(DrawRecord(draw_serial=75343))

    assert store.known_serials() == (75341, 75343)
    assert store.missing_serials() == (75342,)
    assert store.latest_serial() == 75343
    assert store.next_expected_serial() == 75344


def test_store_upsert_is_idempotent(tmp_path):
    store = KeralaLotteryStore(tmp_path / "nokku.db")

    store.upsert_draw(DrawRecord(draw_serial=75343, lottery_code="SK-64"))
    store.upsert_draw(DrawRecord(draw_serial=75343, lottery_code="SK-64"))

    assert store.known_serials() == (75343,)
