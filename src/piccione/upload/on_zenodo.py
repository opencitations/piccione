import argparse
import time
from pathlib import Path

import requests
import yaml
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn


def get_headers(token: str, user_agent: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


class ProgressFileWrapper:
    def __init__(self, file_path: str, progress: Progress, task_id: int):
        self.file_path = file_path
        self.file_size = Path(file_path).stat().st_size
        self.fp = open(file_path, "rb")
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def upload_file_with_retry(base_url: str, record_id: str, file_path: str, token: str, user_agent: str) -> None:
    filename = Path(file_path).name
    file_size = Path(file_path).stat().st_size
    files_url = f"{base_url}/records/{record_id}/draft/files"

    attempt = 0
    while True:
        attempt += 1
        try:
            print(f"\nAttempt {attempt}: {filename}")

            response = requests.post(
                files_url,
                headers=get_headers(token, user_agent, "application/json"),
                json=[{"key": filename}],
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
            response = requests.post(commit_url, headers=get_headers(token, user_agent))
            response.raise_for_status()

            print(f"[OK] {filename} uploaded successfully")
            break

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ERROR] Network error: {e}")
            wait = min(2 ** (attempt - 1), 60)
            print(f"Retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP error: {e}")
            raise


def create_draft(base_url: str, token: str, user_agent: str, metadata: dict) -> dict:
    response = requests.post(
        f"{base_url}/records",
        headers=get_headers(token, user_agent, "application/json"),
        json=metadata,
    )
    if not response.ok:
        print(f"Error creating draft: {response.status_code}")
        print(f"Response: {response.text}")
    response.raise_for_status()
    draft = response.json()
    print(f"Created new draft: {draft['id']}")
    return draft


def create_new_version(base_url: str, token: str, record_id: str, user_agent: str) -> dict:
    headers = get_headers(token, user_agent)
    response = requests.post(
        f"{base_url}/records/{record_id}/versions",
        headers=headers,
    )
    response.raise_for_status()
    draft = response.json()
    print(f"Created new version draft: {draft['id']} (from {record_id})")
    return draft


def delete_draft_files(base_url: str, token: str, record_id: str, user_agent: str) -> None:
    headers = get_headers(token, user_agent)
    response = requests.get(
        f"{base_url}/records/{record_id}/draft/files",
        headers=headers,
    )
    response.raise_for_status()
    files = response.json()["entries"]

    if files:
        print(f"Deleting {len(files)} existing files from draft...")
        for f in files:
            filename = f["key"]
            delete_url = f"{base_url}/records/{record_id}/draft/files/{filename}"
            delete_response = requests.delete(delete_url, headers=headers)
            delete_response.raise_for_status()
            print(f"  Deleted: {filename}")


def update_draft_metadata(base_url: str, token: str, record_id: str, metadata: dict, user_agent: str) -> None:
    response = requests.put(
        f"{base_url}/records/{record_id}/draft",
        headers=get_headers(token, user_agent, "application/json"),
        json=metadata,
    )
    if not response.ok:
        print(f"Error updating metadata: {response.status_code}")
        print(f"Response: {response.text}")
    response.raise_for_status()
    print(f"Metadata updated for draft {record_id}")


def submit_community_review(base_url: str, token: str, record_id: str, community_id: str, user_agent: str) -> None:
    headers = get_headers(token, user_agent, "application/json")
    response = requests.put(
        f"{base_url}/records/{record_id}/draft/review",
        headers=headers,
        json={"receiver": {"community": community_id}, "type": "community-submission"},
    )
    response.raise_for_status()
    response = requests.post(
        f"{base_url}/records/{record_id}/draft/actions/submit-review",
        headers=headers,
        json={"body": "", "format": "html"},
    )
    response.raise_for_status()
    print(f"Submitted review for community {community_id}")


def publish_draft(base_url: str, token: str, record_id: str, user_agent: str) -> dict:
    response = requests.post(
        f"{base_url}/records/{record_id}/draft/actions/publish",
        headers=get_headers(token, user_agent),
    )
    if not response.ok:
        print(f"Error publishing draft: {response.status_code}")
        print(f"Response: {response.text}")
    response.raise_for_status()
    published = response.json()
    print(f"Published: {published['links']['self_html']}")
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


def build_inveniordm_payload(config: dict) -> dict:
    metadata = {}

    metadata["title"] = config["title"]
    metadata["resource_type"] = config["resource_type"]
    metadata["creators"] = config["creators"]
    metadata["publication_date"] = config["publication_date"]

    if "description" in config:
        metadata["description"] = text_to_html(config["description"])

    if "additional_descriptions" in config:
        metadata["additional_descriptions"] = [
            {
                "description": text_to_html(d["description"]),
                "type": d["type"],
            }
            for d in config["additional_descriptions"]
        ]

    for field in ("keywords", "subjects", "dates", "related_identifiers",
                   "rights", "contributors", "references", "version", "language",
                   "locations", "identifiers", "publisher"):
        if field in config:
            metadata[field] = config[field]

    return {
        "access": config["access"],
        "files": {"enabled": True},
        "metadata": metadata,
    }


def main(config_file: str, publish: bool = False) -> None:
    with open(config_file) as f:
        config = yaml.safe_load(f)

    base_url = config["zenodo_url"].rstrip("/")
    token = config["access_token"]
    user_agent = config["user_agent"]
    record_id = config.get("record_id")
    community = config.get("community")

    payload = build_inveniordm_payload(config)

    if record_id:
        draft = create_new_version(base_url, token, record_id, user_agent)
        draft_id = draft["id"]
        delete_draft_files(base_url, token, draft_id, user_agent)
        update_draft_metadata(base_url, token, draft_id, payload, user_agent)
    else:
        draft = create_draft(base_url, token, user_agent, payload)
        draft_id = draft["id"]

    print(f"Draft ID: {draft_id}")
    print(f"Files to upload: {len(config['files'])}")

    for file_path in config["files"]:
        upload_file_with_retry(base_url, draft_id, file_path, token, user_agent)

    if community and "sandbox" not in base_url:
        submit_community_review(base_url, token, draft_id, community, user_agent)

    if publish:
        publish_draft(base_url, token, draft_id, user_agent)
    else:
        print(f"\nDraft ready for review: {base_url.replace('/api', '')}/uploads/{draft_id}")
        print("Run with --publish to publish automatically")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("--publish", action="store_true", help="Publish after upload")
    args = parser.parse_args()
    main(args.config_file, args.publish)