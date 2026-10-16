"""Static UI smoke checks for the judge-facing walkthrough.
Does not claim browser usability or live FalkorDB verification.
"""
from pathlib import Path
from html.parser import HTMLParser
import re
import subprocess

PAGE = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"

class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d:
            self.ids.add(d["id"])

def main():
    html = PAGE.read_text(encoding="utf-8")
    parser = Scan()
    parser.feed(html)
    embedded = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.S|re.I)
    assert len(embedded) == 1, "Expected one bundled script"
    refs = set(re.findall(r'\$\("([a-zA-Z0-9_-]+)"\)', embedded[0]))
    missing = refs - parser.ids
    assert not missing, "Undefined UI element IDs: " + ", ".join(sorted(missing))
    for text in ("PUBLIC SYNTHETIC SIMULATION", "LIVE FALKORDB", "REVIEW_SETTLEMENT",
                 "ASK_SUPPLIER", "DISPUTE", "UNKNOWN", "approve", "scenario"):
        assert text in html, "Missing expected behavior: " + text
    subprocess.run(["node", "--check", "-"], input=embedded[0].encode("utf-8"), check=True)
    print("Frontend static checks passed: " + str(len(refs)) + " referenced elements, JS syntax verified.")

if __name__ == "__main__":
    main()
