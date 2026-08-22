from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


URL = "https://result.keralalotteries.com/detailsofdrawweb.php"


class ResolverHTMLProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, str | None]] = []
        self.inputs: list[dict[str, str | None]] = []
        self.selects: list[dict[str, str | None]] = []
        self.options: list[dict[str, str | None]] = []
        self.scripts: list[str] = []
        self.links: list[str] = []
        self._current_select: dict[str, str | None] | None = None
        self._current_option: dict[str, str | None] | None = None
        self._option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)

        if tag == "form":
            self.forms.append(
                {
                    "method": values.get("method"),
                    "action": values.get("action"),
                    "id": values.get("id"),
                    "name": values.get("name"),
                }
            )
        elif tag == "input":
            self.inputs.append(
                {
                    "type": values.get("type"),
                    "name": values.get("name"),
                    "value": values.get("value"),
                    "id": values.get("id"),
                    "onclick": values.get("onclick"),
                    "ondblclick": values.get("ondblclick"),
                }
            )
        elif tag == "select":
            item = {
                "name": values.get("name"),
                "id": values.get("id"),
                "onchange": values.get("onchange"),
                "ondblclick": values.get("ondblclick"),
            }
            self.selects.append(item)
            self._current_select = item
        elif tag == "option":
            self._current_option = {
                "select": self._current_select.get("name") if self._current_select else None,
                "value": values.get("value"),
                "text": "",
            }
            self._option_text = []
        elif tag == "script" and values.get("src"):
            self.scripts.append(urljoin(URL, values["src"]))
        elif tag == "a" and values.get("href"):
            self.links.append(urljoin(URL, values["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._current_option is not None:
            self._current_option["text"] = " ".join("".join(self._option_text).split())
            self.options.append(self._current_option)
            self._current_option = None
            self._option_text = []
        elif tag == "select":
            self._current_select = None

    def handle_data(self, data: str) -> None:
        if self._current_option is not None:
            self._option_text.append(data)


def main() -> int:
    print("=== OFFICIAL HISTORICAL RESOLVER PROBE ===")
    print("url:", URL)
    print("preservation: NO")
    print("purpose: discover the existing official older-draw lookup contract\n")

    request = Request(URL, headers={"User-Agent": "Mozilla/5.0 Nokku-Habitat-Probe"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
        print("status:", response.status)
        print("content-type:", response.headers.get("Content-Type"))
        print("bytes:", len(raw))

    parser = ResolverHTMLProbe()
    parser.feed(html)

    print("\nforms:")
    for item in parser.forms:
        print("  ", item)

    print("\ninputs:")
    for item in parser.inputs:
        print("  ", item)

    print("\nselects:")
    for item in parser.selects:
        print("  ", item)

    print("\noptions:")
    for item in parser.options:
        print("  ", item)

    print("\nscripts:")
    for item in parser.scripts:
        print("  ", item)

    print("\nlinks:")
    for item in parser.links:
        print("  ", item)

    print("\nNo history was changed by this probe.")
    print("================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
