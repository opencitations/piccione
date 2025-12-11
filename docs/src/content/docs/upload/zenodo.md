---
title: Zenodo
description: Upload files to Zenodo depositions
---

## Prerequisites

- Zenodo account
- Access token (obtain from Account Settings > Applications > Personal access tokens)
- Existing deposition ID

## Configuration

Create a YAML file with the following fields:

| Field | Description |
|-------|-------------|
| `zenodo_url` | `https://zenodo.org` or `https://sandbox.zenodo.org` for testing |
| `access_token` | Zenodo access token |
| `project_id` | Deposition ID |
| `files` | List of file paths to upload |

Example:

```yaml
zenodo_url: https://zenodo.org
access_token: <YOUR_ZENODO_TOKEN>
project_id: 12345678
files:
  - /path/to/dataset.zip
  - /path/to/readme.txt
```

See [examples/zenodo_upload.yaml](https://github.com/opencitations/piccione/blob/main/examples/zenodo_upload.yaml) for a complete example.

## Usage

```bash
python -m piccione.upload.on_zenodo config.yaml
```

## Features

- Automatic retry with exponential backoff (max 5 retries)
- Progress bar for each file
- Sandbox support for testing
