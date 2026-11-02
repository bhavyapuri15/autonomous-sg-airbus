#!/usr/bin/env python3
"""Download the two organiser workbooks from the public Challenge 4 Drive folder and verify their SHA256.
Idempotent: a file already in place with the expected hash is not refetched. Prints a network-call count.

Folder: https://drive.google.com/drive/folders/1FOw-3WXMylypPpY3wZMyzpYSbnKC4Ybt"""
import hashlib, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config

URL = "https://drive.usercontent.google.com/download?id={}&export=download"
FILES = (  # (Drive file id, destination, expected sha256)
    ("1GxEO1oh1Z5VBEHSI9fdrW6IbyINhx0b3", config.SHEET_XLSX, config.SHEET_SHA256),  # AD Notice of Proposed Rulemaking (AD NPRM).xlsx
    ("144lTTfdJLSmWH3Eeyqez6u6Tv7gMfz1I", config.INDEX_XLSX, config.INDEX_SHA256),  # challenge4_ad_index.xlsx
)


def main():
    calls = 0
    for fid, dest, want in FILES:
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == want:
            print(f"ok (cached) {dest.relative_to(config.ROOT)}"); continue
        calls += 1
        req = urllib.request.Request(URL.format(fid), headers={"User-Agent": config.HTTP_USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        got = hashlib.sha256(body).hexdigest()
        if got != want:
            sys.exit(f"SHA256 mismatch for {dest.name}: got {got}, expected {want}. "
                     f"The organiser file changed or Drive returned a non-file page; download it manually from the folder above.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        print(f"ok (downloaded) {dest.relative_to(config.ROOT)}")
    print("NETWORK_CALLS", calls)


if __name__ == "__main__":
    main()
