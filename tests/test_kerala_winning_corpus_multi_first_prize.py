from nokku.lottery.kerala.winning_corpus import normalize_government_record


def test_reclassifies_location_bearing_first_prize_leaked_into_consolation_tier():
    record = {
        "source": "72081",
        "draw_date": "06/12/2020",
        "lottery_name": "BHAGYAMITHRA LOTTERY NO.BM-1st DRAW",
        "parsed": {
            "lottery_name": "BHAGYAMITHRA LOTTERY NO.BM-1st DRAW",
            "draw_date": "06/12/2020",
            "prize_tiers": [
                {
                    "label": "1st Prize",
                    "amount": "10000000",
                    "entries": ["BA 247741 (MALAPPURAM)"],
                },
                {
                    "label": "Consolation Prize",
                    "amount": "25000",
                    "entries": [
                        "BB 247741 BC 247741 BD 247741 BE 247741",
                        "BF 247741 BG 247741 BH 247741",
                        "BB 391162 (PUNALUR)",
                    ],
                },
                {
                    "label": "Consolation Prize",
                    "amount": "25000",
                    "entries": [
                        "BA 391162 BC 391162 BD 391162 BE 391162",
                        "BF 391162 BG 391162 BH 391162",
                    ],
                },
            ],
        },
    }

    result = normalize_government_record(record)

    first_prize_entries = [
        entry for entry in result.entries if entry.prize_tier == "1st Prize"
    ]
    consolation_entries = [
        entry for entry in result.entries if entry.prize_tier == "Consolation Prize"
    ]

    assert [(entry.series, entry.numeric_part) for entry in first_prize_entries] == [
        ("BA", "247741"),
        ("BB", "391162"),
    ]
    assert all(entry.prize_amount == 10000000 for entry in first_prize_entries)
    assert all(
        entry.numeric_part in {"247741", "391162"}
        for entry in consolation_entries
    )
    assert result.reclassified_entry_count == 1
    assert result.status == "success"
