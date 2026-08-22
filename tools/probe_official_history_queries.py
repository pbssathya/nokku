from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


URL = "https://result.keralalotteries.com/detailsofdrawweb.php"

# Known 2022 draw used only as a probe oracle. Nothing is preserved.
TARGET_SERIAL = "73081"
TARGET_DRAW = "AK-541"

CASES = [
    ("mysearch draw code", {"mysearch": TARGET_DRAW}),
    ("mysearch numeric draw", {"mysearch": "541"}),
    ("mysearch lottery name", {"mysearch": "AKSHAYA"}),
    ("lottery select", {"lotterydet": "52"}),
    ("select + draw code", {"lotterydet": "52", "mysearch": TARGET_DRAW}),
]


class ResultProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self._href = urljoin(URL, values["href"])
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((self._href, text))
            self._href = None
            self._text = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.all_text.append(cleaned)
        if self._href is not None:
            self._text.append(data)


def post_case(label: str, fields: dict[str, str]) -> None:
    encoded = urlencode(fields).encode("ascii")
    request = Request(
        URL,
        data=encoded,
        headers={
            "User-Agent": "Mozilla/5.0 Nokku-Habitat-Probe",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    print(f"\n--- {label} ---")
    print("post:", fields)

    with urlopen(request, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
        print("status:", response.status)
        print("final url:", response.geturl())
        print("bytes:", len(raw))

    parser = ResultProbe()
    parser.feed(html)

    result_links = [
        (href, text)
        for href, text in parser.links
        if "viewlotisresult.php" in href.lower() or "drawserial=" in href.lower()
    ]

    joined = " | ".join(parser.all_text)
    print("contains target serial:", TARGET_SERIAL in html)
    print("contains target draw:", TARGET_DRAW.lower() in joined.lower())
    print("result links:", len(result_links))

    for href, text in result_links[:20]:
        print("  ", {"text": text, "href": href})

    interesting = []
    wanted = ("AKSHAYA", "AK-541", "23/03/2022", "73081", "DRAW")
    for text in parser.all_text:
        if any(token.lower() in text.lower() for token in wanted):
            interesting.append(text)

    if interesting:
        print("interesting text:")
        for text in interesting[:30]:
            print("  ", text)


def main() -> int:
    print("=== OFFICIAL HISTORICAL RESOLVER QUERY PROBE ===")
    print("url:", URL)
    print("preservation: NO")
    print("target oracle:", TARGET_SERIAL, TARGET_DRAW, "23/03/2022")
    print("purpose: test whether the official existing resolver can discover a known 2022 draw")

    for label, fields in CASES:
        try:
            post_case(label, fields)
        except Exception as exc:
            print(f"\n--- {label} ---")
            print("ERROR:", type(exc).__name__, str(exc))

    print("\nNo history was changed by this probe.")
    print("================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
