# SPDX-FileCopyrightText: 2025-2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Generator

import httpx
import yaml
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

console = Console()


class SharePointFolder(TypedDict):
    Name: str
    ServerRelativeUrl: str


class SharePointFile(TypedDict):
    Name: str
    Length: str
    TimeLastModified: str
    ETag: str


class SharePointConfig(TypedDict):
    site_url: str
    fedauth: str
    rtfa: str
    folders: list[str]


@dataclass
class FileMetadata:
    size: int
    modified: str
    etag: str


@dataclass
class FolderNode:
    subfolders: dict[str, FolderNode] = field(default_factory=dict)
    files: dict[str, FileMetadata] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, child in self.subfolders.items():
            result[name] = child.to_dict()
        if self.files:
            result["_files"] = {
                name: {"size": meta.size, "modified": meta.modified, "etag": meta.etag}
                for name, meta in self.files.items()
            }
        return result

    @staticmethod
    def from_dict(data: dict[str, object]) -> FolderNode:
        node = FolderNode()
        for key, value in data.items():
            if not isinstance(value, dict):
                msg = f"Expected dict for key {key!r}, got {type(value).__name__}"
                raise TypeError(msg)
            if key == "_files":
                for filename, meta_raw in value.items():
                    if not isinstance(meta_raw, dict):
                        msg = f"Expected dict for file {filename!r}, got {type(meta_raw).__name__}"
                        raise TypeError(msg)
                    size, modified, etag = meta_raw["size"], meta_raw["modified"], meta_raw["etag"]
                    if not isinstance(size, int):
                        msg = f"Expected int for size of {filename!r}, got {type(size).__name__}"
                        raise TypeError(msg)
                    if not isinstance(modified, str):
                        msg = f"Expected str for modified of {filename!r}, got {type(modified).__name__}"
                        raise TypeError(msg)
                    if not isinstance(etag, str):
                        msg = f"Expected str for etag of {filename!r}, got {type(etag).__name__}"
                        raise TypeError(msg)
                    node.files[filename] = FileMetadata(size=size, modified=modified, etag=etag)
            else:
                node.subfolders[key] = FolderNode.from_dict(value)
        return node


def load_config(config_path: str | Path) -> SharePointConfig:
    with Path(config_path).open() as f:
        return cast("SharePointConfig", yaml.safe_load(f))


def get_site_relative_url(site_url: str) -> str:
    return "/" + "/".join(site_url.rstrip("/").split("/")[3:])


def sort_structure(node: FolderNode) -> FolderNode:
    sorted_subfolders = {k: sort_structure(v) for k, v in sorted(node.subfolders.items())}
    sorted_files = dict(sorted(node.files.items()))
    return FolderNode(subfolders=sorted_subfolders, files=sorted_files)


HTTP_TOO_MANY_REQUESTS = 429
HTTP_BAD_REQUEST = 400


def request_with_retry(client: httpx.Client, url: str, max_retries: int = 5) -> httpx.Response:  # pragma: no cover
    for attempt in range(max_retries):
        resp = client.get(url)
        if resp.status_code == HTTP_TOO_MANY_REQUESTS:
            wait_time = 2**attempt
            time.sleep(wait_time)
            continue
        resp.raise_for_status()
        return resp
    msg = f"Rate limited after {max_retries} retries for {url}"
    raise RuntimeError(msg)


@contextmanager
def stream_with_retry(  # pragma: no cover
    client: httpx.Client,
    url: str,
    max_retries: int = 5,
) -> Generator[httpx.Response, None, None]:
    for attempt in range(max_retries):
        with client.stream("GET", url) as resp:
            if resp.status_code == HTTP_TOO_MANY_REQUESTS:
                wait_time = 2**attempt
                time.sleep(wait_time)
                continue
            if resp.status_code >= HTTP_BAD_REQUEST:
                resp.raise_for_status()
            yield resp
            return
    msg = f"Rate limited after {max_retries} retries for {url}"
    raise RuntimeError(msg)


def get_folder_contents(
    client: httpx.Client,
    site_url: str,
    folder_path: str,
) -> tuple[list[SharePointFolder], list[SharePointFile]]:
    api_url = f"{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder_path}')"

    folders_resp = request_with_retry(client, f"{api_url}/Folders")
    folders_data = folders_resp.json()["d"]["results"]

    files_resp = request_with_retry(client, f"{api_url}/Files")
    files_data = files_resp.json()["d"]["results"]

    return folders_data, files_data


def get_folder_structure(client: httpx.Client, site_url: str, folder_path: str) -> FolderNode:
    node = FolderNode()

    folders, files = get_folder_contents(client, site_url, folder_path)

    for folder in folders:
        name = folder["Name"]
        if name.startswith("_") or name == "Forms":
            continue
        node.subfolders[name] = get_folder_structure(client, site_url, folder["ServerRelativeUrl"])

    for f in files:
        node.files[f["Name"]] = FileMetadata(
            size=int(f["Length"]),
            modified=f["TimeLastModified"],
            etag=f["ETag"],
        )

    return node


def process_folder(
    client: httpx.Client,
    folder_path: str,
    site_url: str,
    progress: Progress,
    task_id: TaskID,
) -> tuple[str, str, FolderNode]:
    folder_name = folder_path.rsplit("/", maxsplit=1)[-1]
    progress.update(task_id, description=f"Scanning {folder_name}...")
    structure = get_folder_structure(client, site_url, folder_path)
    progress.advance(task_id)
    return folder_name, folder_path, structure


def extract_structure(
    client: httpx.Client,
    site_url: str,
    folders: list[str],
    progress: Progress,
) -> tuple[dict[str, FolderNode], dict[str, str]]:
    site_relative_url = get_site_relative_url(site_url)

    task_id = progress.add_task("Discovering...", total=len(folders))

    results = []
    for folder in folders:
        normalized = folder if folder.startswith("/") else "/" + folder
        folder_path = site_relative_url + normalized
        result = process_folder(client, folder_path, site_url, progress, task_id)
        results.append(result)

    structure = {name: sort_structure(folder_structure) for name, _, folder_structure in sorted(results)}
    folder_paths = {name: path for name, path, _ in results}
    return structure, folder_paths


def collect_files_from_structure(
    structure: dict[str, FolderNode],
    folder_paths: dict[str, str],
) -> list[tuple[str, str, FileMetadata]]:
    files: list[tuple[str, str, FileMetadata]] = []

    def traverse(node: FolderNode, current_path: str, base_server_path: str) -> None:
        for filename, metadata in node.files.items():
            server_path = (
                f"{base_server_path}/{current_path}/{filename}" if current_path else f"{base_server_path}/{filename}"
            )
            local_path = f"{current_path}/{filename}" if current_path else filename
            files.append((server_path, local_path, metadata))
        for name, child in node.subfolders.items():
            new_path = f"{current_path}/{name}" if current_path else name
            traverse(child, new_path, base_server_path)

    for folder_name, folder_node in structure.items():
        base_path = folder_paths[folder_name]
        traverse(folder_node, folder_name, base_path.rsplit("/", 1)[0])

    return files


def should_download(remote_meta: FileMetadata, local_path: Path) -> bool:
    if not local_path.exists():
        return True
    local_size = local_path.stat().st_size
    local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
    remote_mtime = datetime.fromisoformat(remote_meta.modified.replace("Z", "+00:00"))
    return local_size != remote_meta.size or local_mtime < remote_mtime


def download_file(client: httpx.Client, site_url: str, file_server_relative_url: str, local_path: Path) -> int:
    url = f"{site_url}/_api/web/GetFileByServerRelativeUrl('{file_server_relative_url}')/$value"

    local_path.parent.mkdir(parents=True, exist_ok=True)

    with stream_with_retry(client, url) as response, local_path.open("wb") as f:
        f.writelines(response.iter_bytes(chunk_size=8192))

    return local_path.stat().st_size


def collect_all_remote_paths(structure: dict[str, FolderNode], folder_paths: dict[str, str]) -> set[Path]:
    return {Path(local_path) for _, local_path, _ in collect_files_from_structure(structure, folder_paths)}


def remove_orphans(output_dir: Path, remote_paths: set[Path]) -> int:
    local_files = {
        p.relative_to(output_dir) for p in output_dir.rglob("*") if p.is_file() and p.name != "structure.json"
    }
    orphans = local_files - remote_paths
    for orphan in orphans:
        (output_dir / orphan).unlink()
        console.print(f"[yellow]Removed: {orphan}")
    return len(orphans)


def download_all_files(
    client: httpx.Client,
    site_url: str,
    structure: dict[str, FolderNode],
    output_dir: Path,
    folder_paths: dict[str, str],
) -> None:
    files = collect_files_from_structure(structure, folder_paths)
    total = len(files)

    downloaded = 0
    updated = 0
    skipped = 0
    failed = 0

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Downloading...", total=total)

        for server_path, local_rel_path, metadata in files:
            local_path = output_dir / local_rel_path
            progress.update(task_id, description=f"[cyan]{local_rel_path}")

            if not should_download(metadata, local_path):
                skipped += 1
                progress.advance(task_id)
                continue

            try:
                was_update = local_path.exists()
                download_file(client, site_url, server_path, local_path)
                if was_update:
                    updated += 1
                else:
                    downloaded += 1
            except Exception as e:  # noqa: BLE001
                console.print(f"[red]Failed: {local_rel_path} ({e})")
                failed += 1

            progress.advance(task_id)

    remote_paths = collect_all_remote_paths(structure, folder_paths)
    removed = remove_orphans(output_dir, remote_paths)

    console.print(
        f"Downloaded: {downloaded}, Updated: {updated}, Skipped: {skipped}, Failed: {failed}, Removed: {removed}",
    )


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--structure-only", action="store_true")
    parser.add_argument("--structure", type=Path, help="Path to existing structure JSON file")
    args = parser.parse_args()

    config = load_config(args.config)

    site_url = config["site_url"]
    fedauth = config["fedauth"]
    rtfa = config["rtfa"]
    folders = config["folders"]

    if args.structure:
        console.print("[bold blue][Phase 1][/] Loading structure from file...")
        with args.structure.open() as f:
            data = json.load(f)
        structure = {name: FolderNode.from_dict(d) for name, d in data["structure"].items()}
        folder_paths = data["folder_paths"]
        console.print(f"Loaded structure from {args.structure}")
    else:
        console.print("[bold blue][Phase 1][/] Discovering files...")
        json_headers = {
            "Cookie": f"FedAuth={fedauth}; rtFa={rtfa}",
            "Accept": "application/json;odata=verbose",
        }

        with (
            Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress,
            httpx.Client(headers=json_headers) as client,
        ):
            structure, folder_paths = extract_structure(client, site_url, folders, progress)

        args.output_dir.mkdir(parents=True, exist_ok=True)

        structure_file = args.output_dir / "structure.json"
        output = {
            "site_url": site_url,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "structure": {name: node.to_dict() for name, node in structure.items()},
            "folder_paths": folder_paths,
        }
        with structure_file.open("w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        console.print(f"Structure saved to {structure_file}")

    if args.structure_only:
        return

    console.print("[bold blue][Phase 2][/] Downloading files...")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    download_headers = {
        "Cookie": f"FedAuth={fedauth}; rtFa={rtfa}",
    }

    with httpx.Client(headers=download_headers, timeout=300) as client:
        download_all_files(client, site_url, structure, args.output_dir, folder_paths)


if __name__ == "__main__":  # pragma: no cover
    main()
