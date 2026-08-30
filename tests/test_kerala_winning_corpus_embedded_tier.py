from nokku.lottery.kerala.winning_corpus import normalize_government_record


def test_embedded_consolation_boundary_is_reclassified_truthfully():
    record = {
        "source": "72038",
        "draw_date": "20/09/2020",
        "lottery_name": "THIRUVONAM BUMPER 2020 LOTTERY NO.BR-75th DRAW",
        "parsed": {
            "lottery_name": "THIRUVONAM BUMPER 2020 LOTTERY NO.BR-75th DRAW",
            "draw_date": "20/09/2020",
            "prize_tiers": [
                {
                    "label": "1st Prize",
                    "amount": "120000000",
                    "entries": [
                        "TB 173964 (ERNAKULAM)",
                        "Consolation Prize-Rs",
                        ":500000/-",
                        "TA 173964 TC 173964 TD 173964 TE 173964",
                        "TG 173964",
                    ],
                }
            ],
        },
    }

    result = normalize_government_record(record)

    assert result.status == "success"
    assert result.ignored_entry_lines == 2
    assert result.reclassified_entry_count == 5
    assert [entry.series for entry in result.entries] == ["TB", "TA", "TC", "TD", "TE", "TG"]
    assert result.entries[0].prize_tier == "1st Prize"
    assert result.entries[0].prize_amount == 120000000
    assert all(
        entry.prize_tier == "Consolation Prize"
        for entry in result.entries[1:]
    )
    assert all(entry.prize_amount == 500000 for entry in result.entries[1:])
