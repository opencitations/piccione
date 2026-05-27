# Copyright (C) 2025 Arcangelo Massari <arcangelo.massari@unibo.it>
# SPDX-FileCopyrightText: 2025 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

"""
Download files from a Figshare article using the Figshare API.

This script downloads all files associated with a Figshare article ID.
It uses the public Figshare API which works reliably unlike direct wget/curl
on Figshare URLs.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import TypedDict

import requests
from rich.console import Console
from tqdm import tqdm

console = Console()

BASE_URL = "https://api.figshare.com/v2"
CHUNK_SIZE = 8192


class FigshareFileEntry(TypedDict):
    name: str
    size: int
    download_url: str
    supplied_md5: str | None


class FigshareArticleMetadata(TypedDict):
    files: list[FigshareFileEntry]


def get_article_metadata(article_id: int) -> FigshareArticleMetadata:
    url = f"{BASE_URL}/articles/{article_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    article_data = response.json()

    # Figshare API has a default limit of 10 files. We need to fetch files separately with pagination.
    files_url = f"{BASE_URL}/articles/{article_id}/files"
    files_response = requests.get(files_url, params={"page_size": 1000}, timeout=30)
    files_response.raise_for_status()
    article_data["files"] = files_response.json()

    return article_data


def download_file(
    download_url: str,
    output_path: str | Path,
    expected_size: int,
    expected_md5: str | None = None,
) -> None:
    response = requests.get(download_url, stream=True, timeout=(30, 300))
    response.raise_for_status()

    md5_hash = hashlib.md5(usedforsecurity=False)

    with (
        Path(output_path).open("wb") as f,
        tqdm(total=expected_size, unit="B", unit_scale=True, unit_divisor=1024) as pbar,
    ):
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            f.write(chunk)
            md5_hash.update(chunk)
            pbar.update(len(chunk))

    if expected_md5:
        actual_md5 = md5_hash.hexdigest()
        if actual_md5 != expected_md5:
            msg = f"MD5 mismatch: expected {expected_md5}, got {actual_md5}"
            raise ValueError(msg)
        console.print(f"  MD5 checksum verified: {actual_md5}")


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Download files from a Figshare article")
    parser.add_argument("article_id", type=int, help="Figshare article ID")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(),
        help="Output directory for downloaded files (default: current directory)",
    )

    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Fetching metadata for article {args.article_id}...")
    metadata = get_article_metadata(args.article_id)

    files = metadata["files"]
    if not files:
        console.print("No files found in this article")
        return 1

    console.print(f"\nFound {len(files)} file(s) to download:")
    for f in files:
        size_mb = f["size"] / (1024 * 1024)
        console.print(f"  - {f['name']} ({size_mb:.2f} MB)")

    console.print(f"\nDownloading to: {args.output_dir.absolute()}\n")

    for file_info in files:
        filename = file_info["name"]
        download_url = file_info["download_url"]
        size = file_info["size"]
        md5 = file_info["supplied_md5"]

        output_path = args.output_dir / filename

        console.print(f"Downloading {filename}...")
        download_file(download_url, output_path, size, md5)
        console.print(f"  Saved to {output_path}\n")

    console.print("All files downloaded successfully")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
