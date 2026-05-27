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

import httpx
import yaml
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

console = Console()


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
            assert isinstance(value, dict)
            if key == "_files":
                for filename, meta_raw in value.items():
                    assert isinstance(meta_raw, dict)
                    size, modified, etag = meta_raw["size"], meta_raw["modified"], meta_raw["etag"]
                    assert isinstance(size, int)
                    assert isinstance(modified, str)
                    assert isinstance(etag, str)
                    node.files[filename] = FileMetadata(size=size, modified=modified, etag=etag)
            else:
                node.subfolders[key] = FolderNode.from_dict(value)
        return node


def load_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_site_relative_url(site_url):
    return "/" + "/".join(site_url.rstrip("/").split("/")[3:])


def sort_structure(node: FolderNode) -> FolderNode:
    sorted_subfolders = {
        k: sort_structure(v) for k, v in sorted(node.subfolders.items())
    }
    sorted_files = dict(sorted(node.files.items()))
    return FolderNode(subfolders=sorted_subfolders, files=sorted_files)


def request_with_retry(client, url, max_retries=5):  # pragma: no cover
    for attempt in range(max_retries):
        resp = client.get(url)
        if resp.status_code == 429:
            wait_time = 2**attempt
            time.sleep(wait_time)
            continue
        resp.raise_for_status()
        return resp
    raise Exception(f"Rate limited after {max_retries} retries for {url}")


@contextmanager
def stream_with_retry(client, url, max_retries=5):  # pragma: no cover
    for attempt in range(max_retries):
        with client.stream("GET", url) as resp:
            if resp.status_code == 429:
                wait_time = 2**attempt
                time.sleep(wait_time)
                continue
            if resp.status_code >= 400:
                resp.raise_for_status()
            yield resp
            return
    raise Exception(f"Rate limited after {max_retries} retries for {url}")


def get_folder_contents(client, site_url, folder_path):
    api_url = f"{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder_path}')"

    folders_resp = request_with_retry(client, f"{api_url}/Folders")
    folders_data = folders_resp.json()["d"]["results"]

    files_resp = request_with_retry(client, f"{api_url}/Files")
    files_data = files_resp.json()["d"]["results"]

    return folders_data, files_data


def get_folder_structure(client, site_url, folder_path) -> FolderNode:
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


def process_folder(client, folder_path, site_url, progress, task_id):
    folder_name = folder_path.split("/")[-1]
    progress.update(task_id, description=f"Scanning {folder_name}...")
    structure = get_folder_structure(client, site_url, folder_path)
    progress.advance(task_id)
    return folder_name, folder_path, structure


def extract_structure(client, site_url, folders, progress):
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


def collect_files_from_structure(structure: dict[str, FolderNode], folder_paths: dict[str, str]):
    files: list[tuple[str, str, FileMetadata]] = []

    def traverse(node: FolderNode, current_path: str, base_server_path: str):
        for filename, metadata in node.files.items():
            server_path = f"{base_server_path}/{current_path}/{filename}" if current_path else f"{base_server_path}/{filename}"
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


def download_file(client, site_url, file_server_relative_url, local_path):
    url = f"{site_url}/_api/web/GetFileByServerRelativeUrl('{file_server_relative_url}')/$value"

    local_path.parent.mkdir(parents=True, exist_ok=True)

    with stream_with_retry(client, url) as response:
        with open(local_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)

    return local_path.stat().st_size


def collect_all_remote_paths(structure, folder_paths):
    return {Path(local_path) for _, local_path, _ in collect_files_from_structure(structure, folder_paths)}


def remove_orphans(output_dir, remote_paths):
    local_files = {p.relative_to(output_dir) for p in output_dir.rglob("*") if p.is_file() and p.name != "structure.json"}
    orphans = local_files - remote_paths
    for orphan in orphans:
        (output_dir / orphan).unlink()
        console.print(f"[yellow]Removed: {orphan}")
    return len(orphans)


def download_all_files(client, site_url, structure, output_dir, folder_paths):
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
            except Exception as e:
                console.print(f"[red]Failed: {local_rel_path} ({e})")
                failed += 1

            progress.advance(task_id)

    remote_paths = collect_all_remote_paths(structure, folder_paths)
    removed = remove_orphans(output_dir, remote_paths)

    console.print(f"Downloaded: {downloaded}, Updated: {updated}, Skipped: {skipped}, Failed: {failed}, Removed: {removed}")


def main():  # pragma: no cover
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
        with open(args.structure) as f:
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

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            with httpx.Client(headers=json_headers) as client:
                structure, folder_paths = extract_structure(client, site_url, folders, progress)

        args.output_dir.mkdir(parents=True, exist_ok=True)

        structure_file = args.output_dir / "structure.json"
        output = {
            "site_url": site_url,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "structure": {name: node.to_dict() for name, node in structure.items()},
            "folder_paths": folder_paths,
        }
        with open(structure_file, "w") as f:
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