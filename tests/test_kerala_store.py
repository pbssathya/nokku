import json

from nokku.lottery.kerala import DrawRecord, KeralaLotteryStore


def test_store_detects_internal_gap_and_next_expected(tmp_path):
    store = KeralaLotteryStore(tmp_path / "draws.json")

    store.upsert_draw(DrawRecord(draw_serial=75341))
    store.upsert_draw(DrawRecord(draw_serial=75343))

    assert store.known_serials() == (75341, 75343)
    assert store.missing_serials() == (75342,)
    assert store.latest_serial() == 75343
    assert store.next_expected_serial() == 75344


def test_store_upsert_is_idempotent(tmp_path):
    store = KeralaLotteryStore(tmp_path / "draws.json")

    store.upsert_draw(DrawRecord(draw_serial=75343, lottery_code="SK-64"))
    store.upsert_draw(DrawRecord(draw_serial=75343, lottery_code="SK-64"))

    assert store.known_serials() == (75343,)


def test_store_is_plain_inspectable_json(tmp_path):
    path = tmp_path / "draws.json"
    store = KeralaLotteryStore(path)
    store.upsert_draw(DrawRecord(draw_serial=75343, lottery_code="SK-64"))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == [
        {
            "draw_serial": 75343,
            "draw_date": None,
            "lottery_code": "SK-64",
            "lottery_name": None,
            "source_url": None,
        }
    ]
