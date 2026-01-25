import argparse
import hashlib
import json
import os
import time

import requests
import yaml
from requests.exceptions import HTTPError
from tqdm import tqdm

BASE_URL = "https://api.figshare.com/v2/account/articles"
CHUNK_SIZE = 1048576


def get_file_check_data(file_name):
    with open(file_name, "rb") as fin:
        md5 = hashlib.md5()
        size = 0
        data = fin.read(CHUNK_SIZE)
        while data:
            size += len(data)
            md5.update(data)
            data = fin.read(CHUNK_SIZE)
        return md5.hexdigest(), size


def issue_request(method, url, token, data=None, binary=False):
    headers = {"Authorization": "token " + token}
    if data is not None and not binary:
        data = json.dumps(data)

    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.request(method, url, headers=headers, data=data, timeout=(30, 300))
            if response.status_code >= 500:
                print(f"[ERROR] Server error {response.status_code}: {response.text[:200]}")
                wait = min(2 ** (attempt - 1), 60)
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            try:
                return json.loads(response.content)
            except ValueError:
                return response.content
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ERROR] Network error: {e}")
            wait = min(2 ** (attempt - 1), 60)
            print(f"Retrying in {wait}s...")
            time.sleep(wait)
        except HTTPError as e:
            print(f"[ERROR] HTTP error: {e}")
            print("Body:", response.text)
            raise


def upload_parts(file_info, file_path, token):
    url = file_info["upload_url"]
    result = issue_request(method="GET", url=url, token=token)
    print(f"\nUploading {os.path.basename(file_path)}:")

    total_size = sum(
        part["endOffset"] - part["startOffset"] + 1 for part in result["parts"]
    )

    with open(file_path, "rb") as fin:
        with tqdm(
            total=total_size, unit="B", unit_scale=True, unit_divisor=1024
        ) as pbar:
            for part in result["parts"]:
                chunk_size = part["endOffset"] - part["startOffset"] + 1
                upload_part(file_info, fin, part, token)
                pbar.update(chunk_size)


def upload_part(file_info, stream, part, token):
    udata = file_info.copy()
    udata.update(part)
    url = "{upload_url}/{partNo}".format(**udata)
    stream.seek(part["startOffset"])
    data = stream.read(part["endOffset"] - part["startOffset"] + 1)
    issue_request(method="PUT", url=url, data=data, binary=True, token=token)
    print("  Uploaded part {partNo} from {startOffset} to {endOffset}".format(**part))


def get_existing_files(article_id, token):
    url = f"{BASE_URL}/{article_id}/files"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return {f["name"]: {"id": f["id"], "md5": f["computed_md5"]} for f in response.json()}


def delete_file(article_id, file_id, token):
    url = f"{BASE_URL}/{article_id}/files/{file_id}"
    headers = {"Authorization": f"token {token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def create_file(article_id, file_name, file_path, token):
    url = f"{BASE_URL}/{article_id}/files"
    headers = {"Authorization": f"token {token}"}
    md5, size = get_file_check_data(file_path)
    data = {"name": os.path.basename(file_name), "md5": md5, "size": size}
    post_response = requests.post(url, headers=headers, json=data)
    post_response.raise_for_status()
    get_response = requests.get(post_response.json()["location"], headers=headers)
    get_response.raise_for_status()
    return get_response.json()


def complete_upload(article_id, file_id, token):
    url = f"{BASE_URL}/{article_id}/files/{file_id}"
    issue_request(method="POST", url=url, token=token)
    print(f"  Upload completion confirmed for file {file_id}")


def main(config_path):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    token = config["TOKEN"]
    article_id = config["ARTICLE_ID"]
    files_to_upload = config["files_to_upload"]

    print(f"Starting upload of {len(files_to_upload)} files to Figshare...")
    existing_files = get_existing_files(article_id, token)
    print(f"Found {len(existing_files)} existing files in article")

    for file_path in tqdm(files_to_upload, desc="Total progress", unit="file"):
        file_name = os.path.basename(file_path)
        local_md5, _ = get_file_check_data(file_path)

        if file_name in existing_files:
            if existing_files[file_name]["md5"] == local_md5:
                print(f"\n[SKIP] {file_name} (already uploaded, MD5 matches)")
                continue
            print(f"\n[REPLACE] {file_name} (MD5 mismatch, deleting old version)")
            delete_file(article_id, existing_files[file_name]["id"], token)

        print(f"\nPreparing {file_name}...")
        file_info = create_file(article_id, file_name, file_path, token)
        upload_parts(file_info, file_path, token)
        complete_upload(article_id, file_info["id"], token)
        print(f"[OK] {file_name} completed")

    print("\nAll files uploaded successfully to Figshare!")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Upload files to Figshare.")
    parser.add_argument("config", help="Path to the YAML configuration file.")
    args = parser.parse_args()
    main(args.config)