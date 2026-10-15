#!/usr/bin/env python3
"""Fetch candidate official snapshots; never promote capability claims automatically."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

HOSTS = {"docs.aws.amazon.com", "aws.amazon.com", "developers.openai.com",
         "platform.openai.com", "learn.chatgpt.com"}


def official(url):
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in HOSTS or p.username or p.password:
        raise ValueError("Only official HTTPS documentation is allowed")
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "img" and not self.skip:
            alt = dict(attrs).get("alt", "")
            if alt:
                self.parts.append("[" + alt + "]")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def fetch(source, output):
    item = dict(source)
    try:
        official(source["url"])
        if not source["id"].replace("-", "").replace(".", "").isalnum():
            raise ValueError("Invalid source ID")
        opener = urllib.request.build_opener(Redirect())
        request = urllib.request.Request(source["url"], headers={"User-Agent": "MigrationEvidence/0.4"})
        with opener.open(request, timeout=30) as response:
            raw = response.read(15_000_001)
            if len(raw) > 15_000_000:
                raise ValueError("Documentation exceeds size limit")
            item["retrieved_url"] = official(response.url)
        text = raw.decode("utf-8")
        if "<html" in text[:2000].lower() or "<!doctype" in text[:2000].lower():
            parser = Extract()
            parser.feed(text)
            text = "\n".join(parser.parts) + "\n"
        path = output / "evidence" / (source["id"] + ".txt")
        path.write_text(text)
        item.update(status="retrieved", retrieved_at=datetime.now(timezone.utc).isoformat(),
                    snapshot_path="evidence/" + path.name,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    raw_sha256=hashlib.sha256(raw).hexdigest(), review_status="pending")
    except Exception as exc:
        item.update(status="failed", error=str(exc), review_status="pending")
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path, help="New candidate directory; never the live registry directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "evidence").mkdir()
    sources = json.loads(args.manifest.read_text())
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda s: fetch(s, args.output), sources))
    (args.output / "sources.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"retrieved": sum(s["status"] == "retrieved" for s in results),
                      "failed": [s["id"] for s in results if s["status"] == "failed"],
                      "review": "All capability claims require manual review before promotion."}))


if __name__ == "__main__":
    main()
