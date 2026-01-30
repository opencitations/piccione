import argparse
import re
import time
from pathlib import Path

import requests
import yaml
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


def get_headers(token, user_agent, content_type=None):
    headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


class ProgressFileWrapper:
    def __init__(self, file_path, progress, task_id):
        self.file_path = file_path
        self.file_size = Path(file_path).stat().st_size
        self.fp = open(file_path, "rb")
        self.progress = progress
        self.task_id = task_id

    def read(self, size=-1):
        data = self.fp.read(size)
        self.progress.update(self.task_id, advance=len(data))
        return data

    def __len__(self):
        return self.file_size

    def close(self):
        self.fp.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def upload_file_with_retry(files_url, file_path, token, user_agent):
    filename = Path(file_path).name
    file_size = Path(file_path).stat().st_size
    headers_json = get_headers(token, user_agent, "application/json")
    headers_octet = get_headers(token, user_agent, "application/octet-stream")

    attempt = 0
    while True:
        attempt += 1
        try:
            print(f"\nAttempt {attempt}: {filename}")
            response = requests.post(
                files_url,
                headers=headers_json,
                json=[{"key": filename}],
                timeout=30,
            )
            response.raise_for_status()
            file_entry = response.json()["entries"][0]
            content_url = file_entry["links"]["content"]
            commit_url = file_entry["links"]["commit"]

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
                        headers=headers_octet,
                        timeout=(30, 3600),
                    )
                    response.raise_for_status()

            response = requests.post(commit_url, headers=headers_json, timeout=30)
            response.raise_for_status()

            print(f"[OK] {filename} uploaded successfully")
            return response

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ERROR] Network error: {e}")
            wait = min(2 ** (attempt - 1), 60)
            print(f"Retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP error: {e}")
            raise


def create_new_draft(base_url, token, user_agent, metadata):
    response = requests.post(
        f"{base_url}/api/records",
        headers=get_headers(token, user_agent, "application/json"),
        json=metadata,
        timeout=30,
    )
    if response.status_code != 201:
        print(f"Error creating draft: {response.status_code}")
        print(f"Response: {response.text}")
        response.raise_for_status()
    draft = response.json()
    print(f"Created new draft: {draft['id']}")
    return draft


def publish_draft(base_url, token, user_agent, draft_id):
    response = requests.post(
        f"{base_url}/api/records/{draft_id}/draft/actions/publish",
        headers=get_headers(token, user_agent, "application/json"),
        timeout=30,
    )
    if response.status_code != 202:
        print(f"Error publishing: {response.status_code}")
        print(f"Response: {response.text}")
        response.raise_for_status()
    published = response.json()
    record_id = published["id"]
    print(f"Published: {base_url}/records/{record_id}")
    return published


def linkify_urls(text):
    url_pattern = r"(https?://[^\s<>\"')]+)"
    return re.sub(url_pattern, r'<a href="\1">\1</a>', text)


def text_to_html(text):
    paragraphs = text.strip().split("\n\n")
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split("\n")
        if lines[0].strip().startswith("- "):
            items = [
                f"<li>{linkify_urls(line.strip()[2:])}</li>"
                for line in lines
                if line.strip().startswith("- ")
            ]
            html_parts.append(f"<ul>{''.join(items)}</ul>")
        else:
            html_parts.append(f"<p>{linkify_urls('<br>'.join(lines))}</p>")
    return "".join(html_parts)


def build_inveniordm_metadata(config: dict) -> dict:
    metadata = {
        "title": config["title"],
        "publication_date": config["publication_date"],
        "resource_type": {"id": config.get("upload_type", "dataset")},
        "publisher": config.get("publisher", "Zenodo"),
    }

    if "description" in config:
        metadata["description"] = text_to_html(config["description"])

    if "creators" in config:
        creators = []
        for c in config["creators"]:
            name = c["name"]
            if "," in name:
                family, given = name.split(",", 1)
                family = family.strip()
                given = given.strip()
            else:
                parts = name.split()
                given = parts[0] if parts else ""
                family = " ".join(parts[1:]) if len(parts) > 1 else ""

            creator = {
                "person_or_org": {
                    "type": "personal",
                    "given_name": given,
                    "family_name": family,
                }
            }
            if c.get("orcid"):
                creator["person_or_org"]["identifiers"] = [
                    {"scheme": "orcid", "identifier": c["orcid"]}
                ]
            if c.get("affiliation"):
                creator["affiliations"] = [{"name": c["affiliation"]}]
            creators.append(creator)
        metadata["creators"] = creators

    if "rights" in config:
        metadata["rights"] = config["rights"]

    if "keywords" in config:
        metadata["subjects"] = [{"subject": kw} for kw in config["keywords"]]

    if "related_identifiers" in config:
        related = []
        for ri in config["related_identifiers"]:
            identifier = ri["identifier"]
            if identifier.startswith("10."):
                scheme = "doi"
            elif identifier.startswith("http"):
                scheme = "url"
            else:
                scheme = ri.get("scheme", "other")
            related.append({
                "identifier": identifier,
                "relation_type": {"id": _map_relation_type(ri["relation"])},
                "scheme": scheme,
            })
        metadata["related_identifiers"] = related

    if "version" in config:
        metadata["version"] = config["version"]

    if "language" in config:
        metadata["languages"] = [{"id": config["language"]}]

    additional_descriptions = []
    if "notes" in config:
        additional_descriptions.append({
            "description": text_to_html(config["notes"]),
            "type": {"id": "notes"},
        })
    if "method" in config:
        additional_descriptions.append({
            "description": text_to_html(config["method"]),
            "type": {"id": "methods"},
        })
    if additional_descriptions:
        metadata["additional_descriptions"] = additional_descriptions

    if "locations" in config:
        metadata["locations"] = {
            "features": [
                {
                    "geometry": {
                        "type": "Point",
                        "coordinates": [loc["lon"], loc["lat"]],
                    },
                    "place": loc.get("place", ""),
                    "description": loc.get("description", ""),
                }
                for loc in config["locations"]
            ]
        }

    return metadata


def _map_relation_type(legacy_relation: str) -> str:
    mapping = {
        "isDocumentedBy": "isdocumentedby",
        "isDescribedBy": "isdescribedby",
        "isAlternateIdentifier": "isidenticalto",
        "isPartOf": "ispartof",
        "hasPart": "haspart",
        "isReferencedBy": "isreferencedby",
        "references": "references",
        "isSupplementTo": "issupplementto",
        "isSupplementedBy": "issupplementedby",
        "isCitedBy": "iscitedby",
        "cites": "cites",
        "isNewVersionOf": "isnewversionof",
        "isPreviousVersionOf": "ispreviousversionof",
        "isSourceOf": "issourceof",
        "isDerivedFrom": "isderivedfrom",
        "isIdenticalTo": "isidenticalto",
    }
    return mapping.get(legacy_relation, legacy_relation.lower())


def main(config_file, publish=False):
    with open(config_file) as f:
        config = yaml.safe_load(f)

    base_url = config["zenodo_url"].rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    token = config["access_token"]
    user_agent = config["user_agent"]

    record_metadata = {
        "access": {
            "record": "public",
            "files": "public",
        },
        "files": {"enabled": True},
        "metadata": build_inveniordm_metadata(config),
    }

    draft = create_new_draft(base_url, token, user_agent, record_metadata)
    draft_id = draft["id"]
    files_url = draft["links"]["files"]

    print(f"Draft ID: {draft_id}")
    print(f"Files URL: {files_url}")
    print(f"Files to upload: {len(config['files'])}")

    for file_path in config["files"]:
        upload_file_with_retry(files_url, file_path, token, user_agent)

    if publish:
        return publish_draft(base_url, token, user_agent, draft_id)

    print(f"\nDraft ready for review: {base_url}/uploads/{draft_id}")
    print("Run with --publish to publish automatically")
    return draft


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("--publish", action="store_true", help="Publish after upload")
    args = parser.parse_args()
    main(args.config_file, args.publish)