"""Collect public publisher materials; run from any working directory."""
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)

    def text(self):
        return "\n".join(
            line for raw in "".join(self.parts).splitlines()
            if (line := " ".join(raw.split()))
        ) + "\n"


SOURCES = [
    ("way_out_west_official.html",
     "https://www.freeformgames.com/product/way-out-west-free/"),
    ("way_out_west_intro.pdf",
     "https://www.freeformgames.com/new/wp-content/uploads/2024/06/game_wow_intro.pdf"),
    ("way_out_west_background.pdf",
     "https://www.freeformgames.com/new/wp-content/uploads/2024/06/wow_03_background.pdf"),
    ("ravenel_complete_kit.html",
     "https://www.your-scenario.com/en/murder-mystery-party/kit"),
    ("ravenel_complete_kit.pdf",
     "https://www.your-scenario.com/kits/halloween-murder-mystery-party-kit.pdf"),
]


def main():
    options = argparse.ArgumentParser()
    options.add_argument("--reuse-existing", action="store_true")
    args = options.parse_args()
    output = Path(__file__).resolve().parent
    manifest = []
    for name, url in SOURCES:
        entry = {"file": name, "url": url}
        try:
            if args.reuse_existing and (output / name).exists():
                data = (output / name).read_bytes()
                entry["reused_local_file"] = True
            else:
                request = Request(url, headers={
                    "User-Agent": "PublicScriptResearch/1.0",
                    "Accept": "text/html,application/pdf",
                })
                with urlopen(request, timeout=40) as response:
                    data = response.read()
                    entry["final_url"] = response.url
                    entry["content_type"] = response.headers.get("Content-Type", "")
            if data.startswith(b"\x1f\x8b"):
                data = gzip.decompress(data)
            if name.endswith(".pdf") and not data.startswith(b"%PDF-"):
                raise ValueError("Publisher response is not a PDF")
            (output / name).write_bytes(data)
            entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if name.endswith(".html"):
                parser = VisibleText()
                parser.feed(data.decode("utf-8"))
                text = parser.text()
                text_name = name.replace(".html", ".txt")
                (output / text_name).write_text(text, encoding="utf-8")
                entry.update(text_file=text_name, text_characters=len(text))
            print(f"Saved {name}: {len(data)} bytes")
        except Exception as error:
            entry["error"] = str(error)
            print(f"Could not fetch {name}: {error}")
        manifest.append(entry)
    (output / "sources.json").write_text(
        json.dumps({
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Publisher public materials for local reading; "
                     "no permission to republish or adapt is inferred.",
            "sources": manifest,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
