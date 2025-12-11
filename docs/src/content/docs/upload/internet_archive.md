---
title: Internet Archive
description: Upload files to Internet Archive items
---

## Prerequisites

- Internet Archive account
- API keys (obtain from https://archive.org/account/s3.php)

## Configuration

Create a YAML file with the following fields:

| Field | Description |
|-------|-------------|
| `identifier` | Unique item identifier |
| `access_key` | S3-like access key |
| `secret_key` | S3-like secret key |
| `file_paths` | List of files to upload |
| `metadata` | Item metadata |

### Metadata fields

| Field | Description |
|-------|-------------|
| `title` | Item title |
| `description` | Item description |
| `creator` | Creator name |
| `mediatype` | Type: `data`, `texts`, `audio`, `video`, etc. |
| `collection` | Collection name (e.g., `opensource`) |
| `subject` | Tags separated by semicolons |
| `date` | Publication date |
| `language` | Language code (e.g., `eng`) |

Example:

```yaml
identifier: my-dataset-2025
access_key: <YOUR_ACCESS_KEY>
secret_key: <YOUR_SECRET_KEY>
file_paths:
  - /path/to/dataset.tar.gz
  - /path/to/documentation.pdf
metadata:
  title: My research dataset
  description: Dataset containing research data
  creator: Author Name
  mediatype: data
  collection: opensource
  subject: research;data;science
```

See [examples/internet_archive_upload.yaml](https://github.com/opencitations/piccione/blob/main/examples/internet_archive_upload.yaml) for a complete example.

## Usage

```bash
python -m piccione.upload.on_internet_archive config.yaml
```

## Features

- MD5 verification
- Automatic retry (3 retries with 10s delay)
- Progress bar
