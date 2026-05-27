# SPDX-FileCopyrightText: 2025-2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from typing import Self

import requests
import yaml
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TaskID, TimeRemainingColumn, TransferSpeedColumn

console = Console()


class AdditionalDescription(TypedDict):
    description: str
    type: dict[str, str]


class _InvenioRDMMetadataRequired(TypedDict):
    title: str
    publication_date: str
    resource_type: dict[str, str]
    creators: list[dict[str, object]]


class InvenioRDMMetadata(_InvenioRDMMetadataRequired, total=False):
    description: str
    additional_descriptions: list[AdditionalDescription]
    subjects: list[dict[str, str]]
    languages: list[dict[str, str]]
    dates: list[dict[str, object]]
    related_identifiers: list[dict[str, object]]
    rights: list[dict[str, object]]
    contributors: list[dict[str, object]]
    funding: list[dict[str, object]]
    version: str
    locations: list[dict[str, object]]
    identifiers: list[dict[str, str]]
    publisher: str
    references: list[str | dict[str, str]]


class InvenioRDMPayload(TypedDict):
    access: dict[str, str]
    files: dict[str, bool]
    metadata: InvenioRDMMetadata


class ZenodoDraft(TypedDict):
    id: str | int


class ZenodoPublished(TypedDict):
    id: str | int
    links: dict[str, str]


class _ZenodoConfigRequired(InvenioRDMMetadata):
    zenodo_url: str
    access_token: str
    user_agent: str
    access: dict[str, str]
    files: list[str]


class ZenodoConfig(_ZenodoConfigRequired, total=False):
    record_id: str
    community: str


def get_headers(token: str, user_agent: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


class ProgressFileWrapper:
    def __init__(self, file_path: str, progress: Progress, task_id: TaskID) -> None:
        self.file_path = file_path
        self.file_size = Path(file_path).stat().st_size
        self.fp = Path(file_path).open("rb")  # noqa: SIM115
        self.progress = progress
        self.task_id = task_id

    def read(self, size: int = -1) -> bytes:
        data = self.fp.read(size)
        self.progress.update(self.task_id, advance=len(data))
        return data

    def __len__(self) -> int:
        return self.file_size

    def close(self) -> None:
        self.fp.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object,
    ) -> None:
        self.close()


def upload_file_with_retry(base_url: str, record_id: str, file_path: str, token: str, user_agent: str) -> None:
    filename = Path(file_path).name
    file_size = Path(file_path).stat().st_size
    files_url = f"{base_url}/records/{record_id}/draft/files"

    attempt = 0
    while True:
        attempt += 1
        try:
            console.print(f"\nAttempt {attempt}: {filename}")

            response = requests.post(
                files_url,
                headers=get_headers(token, user_agent, "application/json"),
                json=[{"key": filename}],
                timeout=30,
            )
            response.raise_for_status()

            content_url = f"{files_url}/{filename}/content"
            with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task_id = progress.add_task(filename, total=file_size)
                with ProgressFileWrapper(file_path, progress, task_id) as wrapper:
                    response = requests.put(
                        content_url,
                        data=wrapper,
                        headers=get_headers(token, user_agent, "application/octet-stream"),
                        timeout=(30, 3600),
                    )
                    response.raise_for_status()

            commit_url = f"{files_url}/{filename}/commit"
            response = requests.post(commit_url, headers=get_headers(token, user_agent), timeout=30)
            response.raise_for_status()

            console.print(f"[OK] {filename} uploaded successfully")
            break

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            console.print(f"[ERROR] Network error: {e}")
            wait = min(2 ** (attempt - 1), 60)
            console.print(f"Retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            console.print(f"[ERROR] HTTP error: {e}")
            raise


def create_draft(base_url: str, token: str, user_agent: str, metadata: InvenioRDMPayload) -> ZenodoDraft:
    response = requests.post(
        f"{base_url}/records",
        headers=get_headers(token, user_agent, "application/json"),
        json=metadata,
        timeout=30,
    )
    if not response.ok:
        console.print(f"Error creating draft: {response.status_code}")
        console.print(f"Response: {response.text}")
    response.raise_for_status()
    draft = response.json()
    console.print(f"Created new draft: {draft['id']}")
    return draft


def create_new_version(base_url: str, token: str, record_id: str, user_agent: str) -> ZenodoDraft:
    headers = get_headers(token, user_agent)
    response = requests.post(
        f"{base_url}/records/{record_id}/versions",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    draft = response.json()
    console.print(f"Created new version draft: {draft['id']} (from {record_id})")
    return draft


def delete_draft_files(base_url: str, token: str, record_id: str, user_agent: str) -> None:
    headers = get_headers(token, user_agent)
    response = requests.get(
        f"{base_url}/records/{record_id}/draft/files",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    files = response.json()["entries"]

    if files:
        console.print(f"Deleting {len(files)} existing files from draft...")
        for f in files:
            filename = f["key"]
            delete_url = f"{base_url}/records/{record_id}/draft/files/{filename}"
            delete_response = requests.delete(delete_url, headers=headers, timeout=30)
            delete_response.raise_for_status()
            console.print(f"  Deleted: {filename}")


def update_draft_metadata(
    base_url: str,
    token: str,
    record_id: str,
    metadata: InvenioRDMPayload,
    user_agent: str,
) -> None:
    response = requests.put(
        f"{base_url}/records/{record_id}/draft",
        headers=get_headers(token, user_agent, "application/json"),
        json=metadata,
        timeout=30,
    )
    if not response.ok:
        console.print(f"Error updating metadata: {response.status_code}")
        console.print(f"Response: {response.text}")
    response.raise_for_status()
    console.print(f"Metadata updated for draft {record_id}")


def _resolve_community_id(base_url: str, community_slug: str) -> str:
    response = requests.get(f"{base_url}/communities/{community_slug}", timeout=30)
    response.raise_for_status()
    return response.json()["id"]


def submit_community_review(base_url: str, token: str, record_id: str, community_slug: str, user_agent: str) -> None:
    headers = get_headers(token, user_agent, "application/json")
    community_uuid = _resolve_community_id(base_url, community_slug)
    response = requests.put(
        f"{base_url}/records/{record_id}/draft/review",
        headers=headers,
        json={"receiver": {"community": community_uuid}, "type": "community-submission"},
        timeout=30,
    )
    if not response.ok:
        console.print(f"Error creating community review: {response.status_code}")
        console.print(f"Response: {response.text}")
    response.raise_for_status()
    response = requests.post(
        f"{base_url}/records/{record_id}/draft/actions/submit-review",
        headers=headers,
        json={"payload": {"content": "Automated submission", "format": "html"}},
        timeout=30,
    )
    if not response.ok:
        console.print(f"Error submitting community review: {response.status_code}")
        console.print(f"Response: {response.text}")
    response.raise_for_status()
    console.print(f"Submitted review for community {community_slug}")


def publish_draft(base_url: str, token: str, record_id: str, user_agent: str) -> ZenodoPublished:
    response = requests.post(
        f"{base_url}/records/{record_id}/draft/actions/publish",
        headers=get_headers(token, user_agent),
        timeout=30,
    )
    if not response.ok:
        console.print(f"Error publishing draft: {response.status_code}")
        console.print(f"Response: {response.text}")
    response.raise_for_status()
    published = response.json()
    console.print(f"Published: {published['links']['self_html']}")
    return published


def text_to_html(text: str) -> str:
    paragraphs = text.strip().split("\n\n")
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split("\n")
        if lines[0].strip().startswith("- "):
            items = [f"<li>{line.strip()[2:]}</li>" for line in lines if line.strip().startswith("- ")]
            html_parts.append(f"<ul>{''.join(items)}</ul>")
        else:
            html_parts.append(f"<p>{('<br>'.join(lines))}</p>")
    return "".join(html_parts)


def build_inveniordm_payload(metadata_config: InvenioRDMMetadata, access: dict[str, str]) -> InvenioRDMPayload:
    metadata: dict[str, object] = {}

    metadata["title"] = metadata_config["title"]
    metadata["resource_type"] = metadata_config["resource_type"]
    metadata["creators"] = metadata_config["creators"]
    metadata["publication_date"] = metadata_config["publication_date"]

    if "description" in metadata_config:
        metadata["description"] = text_to_html(metadata_config["description"])

    if "additional_descriptions" in metadata_config:
        metadata["additional_descriptions"] = [
            {"description": text_to_html(d["description"]), "type": d["type"]}
            for d in metadata_config["additional_descriptions"]
        ]

    config_dict = cast("dict[str, object]", metadata_config)
    for field in (
        "subjects",
        "languages",
        "dates",
        "related_identifiers",
        "rights",
        "contributors",
        "funding",
        "version",
        "locations",
        "identifiers",
    ):
        if field in config_dict:
            metadata[field] = config_dict[field]

    metadata["publisher"] = metadata_config.get("publisher", "Zenodo")

    if "references" in metadata_config:
        metadata["references"] = [
            {"reference": ref} if isinstance(ref, str) else ref for ref in metadata_config["references"]
        ]

    return cast(
        "InvenioRDMPayload",
        {
            "access": access,
            "files": {"enabled": True},
            "metadata": metadata,
        },
    )


def main(config_file: str, *, publish: bool = False) -> ZenodoDraft | ZenodoPublished:
    with Path(config_file).open() as f:
        config = cast("ZenodoConfig", yaml.safe_load(f))

    base_url = config["zenodo_url"].rstrip("/")
    token = config["access_token"]
    user_agent = config["user_agent"]
    record_id = config.get("record_id")
    community = config.get("community")

    payload = build_inveniordm_payload(config, config["access"])

    if record_id:
        draft = create_new_version(base_url, token, record_id, user_agent)
        draft_id = str(draft["id"])
        delete_draft_files(base_url, token, draft_id, user_agent)
        update_draft_metadata(base_url, token, draft_id, payload, user_agent)
    else:
        draft = create_draft(base_url, token, user_agent, payload)
        draft_id = str(draft["id"])

    console.print(f"Draft ID: {draft_id}")
    console.print(f"Files to upload: {len(config['files'])}")

    for file_path in config["files"]:
        upload_file_with_retry(base_url, draft_id, str(file_path), token, user_agent)

    if community and "sandbox" not in base_url and not record_id:
        submit_community_review(base_url, token, draft_id, str(community), user_agent)

    if publish:
        return publish_draft(base_url, token, draft_id, user_agent)
    console.print(f"\nDraft ready for review: {base_url.replace('/api', '')}/uploads/{draft_id}")
    console.print("Run with --publish to publish automatically")
    return draft


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("--publish", action="store_true", help="Publish after upload")
    args = parser.parse_args()
    main(args.config_file, publish=args.publish)
