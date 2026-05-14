#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.request


URLS = [
    "https://aihot.virxact.com/api/public/items?mode=selected&take=1",
    "https://github.com",
    "https://openai.com",
]


def probe_url(url: str) -> dict:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 aihot-skill/0.2.0 knowledge-vault-probe"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"url": url, "ok": True, "status": resp.status}
    except Exception as exc:
        return {"url": url, "ok": False, "error": repr(exc)}


def probe_url_curl(url: str) -> dict:
    try:
        result = subprocess.run(
            [
                "curl.exe",
                "-L",
                "--silent",
                "--show-error",
                "--max-time",
                "15",
                "-o",
                "NUL",
                "-w",
                "%{http_code}",
                "-H",
                "User-Agent: Mozilla/5.0 aihot-skill/0.2.0 knowledge-vault-probe",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return {
            "url": url,
            "ok": result.returncode == 0 and result.stdout.strip().isdigit() and result.stdout.strip() != "000",
            "status": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {"url": url, "ok": False, "error": repr(exc)}


def main() -> None:
    result = {
        "python": sys.executable,
        "cwd": os.getcwd(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "computer": os.environ.get("COMPUTERNAME"),
        "proxies": {k: v for k, v in os.environ.items() if "PROXY" in k.upper()},
        "dns": {},
        "urllib_urls": [],
        "curl_urls": [],
    }
    for host in ["aihot.virxact.com", "github.com", "openai.com"]:
        try:
            result["dns"][host] = socket.gethostbyname(host)
        except Exception as exc:
            result["dns"][host] = repr(exc)
    result["urllib_urls"] = [probe_url(url) for url in URLS]
    result["curl_urls"] = [probe_url_curl(url) for url in URLS]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
