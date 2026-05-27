# SPDX-FileCopyrightText: 2025-2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import BinaryIO, TypedDict, cast

import requests
import yaml
from requests.exceptions import HTTPError
from rich.console import Console
from tqdm import tqdm

console = Console()

BASE_URL = "https://api.figshare.com/v2/account/articles"
CHUNK_SIZE = 1048576
HTTP_INTERNAL_SERVER_ERROR = 500


class FigshareFileInfo(TypedDict):
    upload_url: str
    id: int | str


class FigsharePart(TypedDict):
    partNo: int
    startOffset: int
    endOffset: int


class FigsharePartsResponse(TypedDict):
    parts: list[FigsharePart]


class FigshareExistingFile(TypedDict):
    id: int | str
    md5: str


def get_file_check_data(file_name: str | Path) -> tuple[str, int]:
    with Path(file_name).open("rb") as fin:
        md5 = hashlib.md5(usedforsecurity=False)
        size = 0
        data = fin.read(CHUNK_SIZE)
        while data:
            size += len(data)
            md5.update(data)
            data = fin.read(CHUNK_SIZE)
        return md5.hexdigest(), size


def issue_request(
    method: str,
    url: str,
    token: str,
    data: str | bytes | dict[str, object] | None = None,
    *,
    binary: bool = False,
) -> dict[str, object] | bytes:
    headers = {"Authorization": "token " + token}
    if data is not None and not binary:
        data = json.dumps(data)

    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.request(method, url, headers=headers, data=data, timeout=(30, 300))
            if response.status_code >= HTTP_INTERNAL_SERVER_ERROR:
                console.print(f"[ERROR] Server error {response.status_code}: {response.text[:200]}")
                wait = min(2 ** (attempt - 1), 60)
                console.print(f"Retrying in {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            try:
                return json.loads(response.content)
            except ValueError:
                return response.content
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            console.print(f"[ERROR] Network error: {e}")
            wait = min(2 ** (attempt - 1), 60)
            console.print(f"Retrying in {wait}s...")
            time.sleep(wait)
        except HTTPError as e:
            console.print(f"[ERROR] HTTP error: {e}")
            if e.response is not None:
                console.print("Body:", e.response.text)
            raise


def upload_parts(file_info: FigshareFileInfo, file_path: str | Path, token: str) -> None:
    result = issue_request(method="GET", url=file_info["upload_url"], token=token)
    if not isinstance(result, dict):
        msg = "Expected dict response"
        raise TypeError(msg)
    console.print(f"\nUploading {Path(file_path).name}:")

    parts = cast("FigsharePartsResponse", result)["parts"]
    total_size = sum(part["endOffset"] - part["startOffset"] + 1 for part in parts)

    with (
        Path(file_path).open("rb") as fin,
        tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024) as pbar,
    ):
        for part in parts:
            chunk_size = part["endOffset"] - part["startOffset"] + 1
            upload_part(file_info, fin, part, token)
            pbar.update(chunk_size)


def upload_part(file_info: FigshareFileInfo, stream: BinaryIO, part: FigsharePart, token: str) -> None:
    url = f"{file_info['upload_url']}/{part['partNo']}"
    stream.seek(part["startOffset"])
    data = stream.read(part["endOffset"] - part["startOffset"] + 1)
    issue_request(method="PUT", url=url, data=data, binary=True, token=token)
    console.print("  Uploaded part {partNo} from {startOffset} to {endOffset}".format_map(part))


def get_existing_files(article_id: str, token: str) -> dict[str, FigshareExistingFile]:
    url = f"{BASE_URL}/{article_id}/files"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return {f["name"]: {"id": f["id"], "md5": f["computed_md5"]} for f in response.json()}


def delete_file(article_id: str, file_id: str, token: str) -> None:
    url = f"{BASE_URL}/{article_id}/files/{file_id}"
    headers = {"Authorization": f"token {token}"}
    response = requests.delete(url, headers=headers, timeout=30)
    response.raise_for_status()


def create_file(article_id: str, file_name: str, file_path: str | Path, token: str) -> FigshareFileInfo:
    url = f"{BASE_URL}/{article_id}/files"
    headers = {"Authorization": f"token {token}"}
    md5, size = get_file_check_data(file_path)
    data = {"name": Path(file_name).name, "md5": md5, "size": size}
    post_response = requests.post(url, headers=headers, json=data, timeout=30)
    post_response.raise_for_status()
    get_response = requests.get(post_response.json()["location"], headers=headers, timeout=30)
    get_response.raise_for_status()
    return get_response.json()


def complete_upload(article_id: str, file_id: str, token: str) -> None:
    url = f"{BASE_URL}/{article_id}/files/{file_id}"
    issue_request(method="POST", url=url, token=token)
    console.print(f"  Upload completion confirmed for file {file_id}")


def main(config_path: str | Path) -> None:
    with Path(config_path).open() as f:
        config = yaml.safe_load(f)

    token = config["TOKEN"]
    article_id = config["ARTICLE_ID"]
    files_to_upload = config["files_to_upload"]

    console.print(f"Starting upload of {len(files_to_upload)} files to Figshare...")
    existing_files = get_existing_files(article_id, token)
    console.print(f"Found {len(existing_files)} existing files in article")

    for file_path in tqdm(files_to_upload, desc="Total progress", unit="file"):
        file_name = Path(file_path).name
        local_md5, _ = get_file_check_data(file_path)

        if file_name in existing_files:
            if existing_files[file_name]["md5"] == local_md5:
                console.print(f"\n[SKIP] {file_name} (already uploaded, MD5 matches)")
                continue
            console.print(f"\n[REPLACE] {file_name} (MD5 mismatch, deleting old version)")
            delete_file(article_id, str(existing_files[file_name]["id"]), token)

        console.print(f"\nPreparing {file_name}...")
        file_info = create_file(article_id, file_name, file_path, token)
        upload_parts(file_info, file_path, token)
        complete_upload(article_id, str(file_info["id"]), token)
        console.print(f"[OK] {file_name} completed")

    console.print("\nAll files uploaded successfully to Figshare!")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Upload files to Figshare.")
    parser.add_argument("config", help="Path to the YAML configuration file.")
    args = parser.parse_args()
    main(args.config)
