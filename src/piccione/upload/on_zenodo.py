import argparse
import time
from pathlib import Path

import requests
import yaml
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn


def get_headers(token, user_agent, content_type=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': user_agent
    }
    if content_type:
        headers['Content-Type'] = content_type
    return headers


class ProgressFileWrapper:
    def __init__(self, file_path, progress, task_id):
        self.file_path = file_path
        self.file_size = Path(file_path).stat().st_size
        self.fp = open(file_path, 'rb')
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


def upload_file_with_retry(bucket_url, file_path, token, user_agent, max_retries=5):
    filename = Path(file_path).name
    file_size = Path(file_path).stat().st_size
    url = f"{bucket_url}/{filename}"

    for attempt in range(max_retries):
        try:
            print(f"\nAttempt {attempt + 1}/{max_retries}: {filename}")

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
                        url,
                        data=wrapper,
                        headers=get_headers(token, user_agent),
                        timeout=(30, 3600)
                    )
                    response.raise_for_status()

            print(f"[OK] {filename} uploaded successfully")
            return response

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ERROR] Network error: {e}")
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP error: {e}")
            raise


def create_new_deposition(base_url, token, user_agent):
    response = requests.post(
        f"{base_url}/deposit/depositions",
        headers=get_headers(token, user_agent, 'application/json'),
        json={}
    )
    response.raise_for_status()
    draft = response.json()
    print(f"Created new deposition: {draft['id']}")
    return draft


def create_new_version(base_url, token, project_id, user_agent):
    headers = get_headers(token, user_agent)
    response = requests.post(
        f"{base_url}/deposit/depositions/{project_id}/actions/newversion",
        headers=headers
    )

    if response.status_code == 400:
        get_response = requests.get(
            f"{base_url}/deposit/depositions/{project_id}",
            headers=headers
        )
        get_response.raise_for_status()
        conceptrecid = get_response.json()['conceptrecid']

        drafts_response = requests.get(
            f"{base_url}/deposit/depositions?status=draft",
            headers=headers
        )
        drafts_response.raise_for_status()
        for d in drafts_response.json():
            if d['conceptrecid'] == conceptrecid:
                draft_response = requests.get(d['links']['self'], headers=headers)
                draft_response.raise_for_status()
                draft = draft_response.json()
                print(f"Using existing draft: {draft['id']} (from {project_id})")
                return draft

        raise RuntimeError(f"No draft found for concept {conceptrecid}")

    response.raise_for_status()
    latest_draft_url = response.json()['links']['latest_draft']
    draft_response = requests.get(latest_draft_url, headers=headers)
    draft_response.raise_for_status()
    draft = draft_response.json()
    print(f"Created new version draft: {draft['id']} (from {project_id})")
    return draft


def text_to_html(text):
    paragraphs = text.strip().split('\n\n')
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split('\n')
        if lines[0].strip().startswith('- '):
            items = [f"<li>{line.strip()[2:]}</li>" for line in lines if line.strip().startswith('- ')]
            html_parts.append(f"<ul>{''.join(items)}</ul>")
        else:
            html_parts.append(f"<p>{('<br>'.join(lines))}</p>")
    return ''.join(html_parts)


def update_metadata(base_url, token, draft_id, config, user_agent):
    headers = get_headers(token, user_agent, 'application/json')

    get_response = requests.get(
        f"{base_url}/deposit/depositions/{draft_id}",
        headers=headers
    )
    get_response.raise_for_status()
    existing = get_response.json()['metadata']

    if 'dates' in existing:
        existing['dates'] = [d for d in existing['dates'] if d.get('start') or d.get('end')]
        if not existing['dates']:
            del existing['dates']

    for field in ('title', 'upload_type', 'creators', 'keywords', 'license'):
        if field in config:
            existing[field] = config[field]

    if 'description' in config:
        existing['description'] = text_to_html(config['description'])

    response = requests.put(
        f"{base_url}/deposit/depositions/{draft_id}",
        headers=headers,
        json={'metadata': existing}
    )
    if response.status_code != 200:
        print(f"Error updating metadata: {response.status_code}")
        print(f"Response: {response.text}")
        response.raise_for_status()
    print(f"Metadata updated for draft {draft_id}")


def delete_existing_files(base_url, token, draft, user_agent, max_retries=3):
    headers = get_headers(token, user_agent)

    if draft['files']:
        print(f"Deleting {len(draft['files'])} existing files from draft...")
        for f in draft['files']:
            file_url = f['links']['self']
            for attempt in range(max_retries):
                response = requests.delete(file_url, headers=headers)
                if response.status_code == 204:
                    print(f"  Deleted: {f['filename']}")
                    break
                if response.status_code >= 500 and attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"  Server error, retrying in {wait}s...")
                    time.sleep(wait)
                elif response.status_code >= 500:
                    print(f"  Skipping {f['filename']} (server error, will be replaced)")
                    break
                else:
                    response.raise_for_status()


def publish_draft(base_url, token, draft_id, user_agent):
    response = requests.post(
        f"{base_url}/deposit/depositions/{draft_id}/actions/publish",
        headers=get_headers(token, user_agent)
    )
    response.raise_for_status()
    published = response.json()
    print(f"Published: https://zenodo.org/records/{published['id']}")
    return published


def main(config_file, publish=False):
    with open(config_file) as f:
        config = yaml.safe_load(f)

    base_url = config['zenodo_url'].rstrip('/')
    token = config['access_token']
    user_agent = config['user_agent']
    project_id = config.get('project_id')

    if project_id:
        draft = create_new_version(base_url, token, project_id, user_agent)
        delete_existing_files(base_url, token, draft, user_agent)
    else:
        draft = create_new_deposition(base_url, token, user_agent)

    draft_id = draft['id']
    bucket_url = draft['links']['bucket']

    print(f"Draft ID: {draft_id}")
    print(f"Bucket: {bucket_url}")
    print(f"Files to upload: {len(config['files'])}")

    update_metadata(base_url, token, draft_id, config, user_agent)

    for file_path in config['files']:
        upload_file_with_retry(bucket_url, file_path, token, user_agent)

    if publish:
        publish_draft(base_url, token, draft_id, user_agent)
    else:
        print(f"\nDraft ready for review: https://zenodo.org/uploads/{draft_id}")
        print("Run with --publish to publish automatically")


if __name__ == '__main__':  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file')
    parser.add_argument('--publish', action='store_true', help='Publish after upload')
    args = parser.parse_args()
    main(args.config_file, args.publish)