---
title: Zenodo
description: Upload files to Zenodo depositions
---

## Prerequisites

- Zenodo account
- Access token (obtain from Account Settings > Applications > Personal access tokens)

## Configuration

Create a YAML file with the following fields:

| Field | Description |
|-------|-------------|
| `zenodo_url` | Full API URL: `https://zenodo.org/api` or `https://sandbox.zenodo.org/api` |
| `access_token` | Zenodo access token |
| `user_agent` | User-Agent string for API requests (e.g., `piccione/2.0.0`). See note below |
| `project_id` | (Optional) Existing deposition ID to create new version from |
| `title` | Deposition title |
| `upload_type` | Type: `dataset`, `publication`, `software`, `image`, `video`, `poster`, etc. |
| `creators` | List of creator objects with `name`, `affiliation`, `orcid` |
| `keywords` | List of keywords |
| `license` | License identifier (e.g., `cc-by-4.0`) |
| `description` | Plain text description (converted to HTML with paragraph support) |
| `files` | List of file paths to upload |

**Note on User-Agent:** Specifying a `user_agent` is strongly recommended. Without a proper User-Agent header, Zenodo is more likely to return 403 Forbidden errors or block uploads, especially during periods of high server load.

Example:

```yaml
zenodo_url: https://zenodo.org/api
access_token: <YOUR_ZENODO_TOKEN>
user_agent: piccione/2.0.0

# Optional: omit to create new deposition
# project_id: 12345678

title: My Dataset
upload_type: dataset
creators:
  - name: Doe, John
    affiliation: University
    orcid: 0000-0000-0000-0000
keywords:
  - data
  - research
license: cc-by-4.0
description: |
  Dataset description here.

  Multiple paragraphs supported.

files:
  - /path/to/dataset.zip
  - /path/to/readme.txt
```

See [examples/zenodo_upload.yaml](https://github.com/opencitations/piccione/blob/main/examples/zenodo_upload.yaml) for a complete example.

## Usage

```bash
# Upload and create draft for review
python -m piccione.upload.on_zenodo config.yaml

# Upload and publish automatically
python -m piccione.upload.on_zenodo config.yaml --publish
```

## Features

- Create new depositions or new versions of existing ones
- Automatic metadata update from configuration
- Automatic retry with exponential backoff (max 5 retries)
- Rich progress bar with transfer speed and ETA
- Sandbox support for testing
- Optional auto-publish with `--publish` flag
