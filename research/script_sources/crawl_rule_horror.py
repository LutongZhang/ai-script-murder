"""Archive a small, explicit set of public rule-horror research sources."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = "LocalDungeonResearch/1.0"
OUTPUT = Path(__file__).resolve().parents[1] / "rule_horror_sources"
SOURCES = [
    ("scp_3008_original", "https://scp-wiki.wikidot.com/scp-3008",
     "SCP-3008 — A Perfectly Normal, Regular Old IKEA", "Mortos", None),
    ("scp_3008_chinese", "https://scp-wiki-cn.wikidot.com/scp-3008",
     "SCP-3008 — 非常普通标准的老宜家", "Mortos", "ashausesall"),
    ("scp_licensing", "https://scp-wiki.wikidot.com/licensing-guide",
     "SCP Wiki Licensing Guide", "SCP Wiki", None),
]


class ArticleText(HTMLParser):
    """Keep page-content, including collapsed diary text; discard site chrome."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if not self.depth:
            if tag == "div" and dict(attrs).get("id") == "page-content":
                self.depth = 1
            return
        if tag == "div":
            self.depth += 1
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"div", "p", "li", "br", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "li", "div", "tr"}:
            self.parts.append("\n")
        if tag == "div":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(
            line for raw in "".join(self.parts).splitlines()
            if (line := " ".join(raw.split()))
        ) + "\n"


def fetch(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
    with urlopen(request, timeout=40) as response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("Source exceeds the 2 MiB collection limit")
        if response.headers.get("Content-Encoding") == "gzip" or data.startswith(b"\x1f\x8b"):
            data = gzip.decompress(data)
        return data, response.url, response.headers.get("Content-Type", "")


def main():
    if not OUTPUT.is_dir():
        raise RuntimeError(f"Create the source directory first: {OUTPUT}")
    robots = {}
    entries = []
    for name, url, title, author, translator in SOURCES:
        entry = {"id": name, "url": url, "title": title, "author": author,
                 "translator": translator, "license": "CC BY-SA 3.0",
                 "license_url": "https://creativecommons.org/licenses/by-sa/3.0/"}
        try:
            host = urlsplit(url).netloc
            if host not in robots:
                robot_url = f"https://{host}/robots.txt"
                data, _, _ = fetch(robot_url)
                parser = RobotFileParser(robot_url)
                parser.parse(data.decode("utf-8").splitlines())
                robots[host] = parser
                (OUTPUT / f"{host}_robots.txt").write_bytes(data)
            if not robots[host].can_fetch(USER_AGENT, url):
                raise ValueError("robots.txt disallows this research client")
            data, final_url, content_type = fetch(url)
            if "html" not in content_type:
                raise ValueError(f"Expected HTML, received {content_type}")
            parser = ArticleText()
            parser.feed(data.decode("utf-8"))
            text = parser.text()
            if len(text) < 4000 or (name.startswith("scp_3008") and "SCP-3008" not in text):
                raise ValueError("Article body was missing or unexpectedly short")
            (OUTPUT / f"{name}.html").write_bytes(data)
            (OUTPUT / f"{name}.txt").write_text(text, encoding="utf-8")
            entry.update(status="collected", final_url=final_url, content_type=content_type,
                         file=f"{name}.html", text_file=f"{name}.txt", bytes=len(data),
                         text_characters=len(text), sha256=hashlib.sha256(data).hexdigest())
            print(f"Collected {name}: {len(text)} article characters")
        except Exception as exc:
            entry.update(status="failed", error=str(exc))
            print(f"Could not collect {name}: {exc}")
        entries.append(entry)
    (OUTPUT / "sources.json").write_text(json.dumps({
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "method": "Explicit URL allowlist; robots.txt checked; article body extracted without images.",
        "scope": "Original and Chinese translation are two versions of one story, not independent evidence.",
        "adaptation": "Night Ward uses the enclosed survival/day-night/exit motifs. "
                      "Hospital, characters, rules, variants and endings are newly written derivative content.",
        "sources": entries,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if any(entry["status"] != "collected" for entry in entries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
