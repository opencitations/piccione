---
title: Figshare
description: Upload files to Figshare articles
---

## Prerequisites

- Figshare account
- API token (obtain from Account Settings > Applications > Personal tokens)
- Existing article ID

## Configuration

Create a YAML file with the following fields:

| Field | Description |
|-------|-------------|
| `TOKEN` | Figshare API token |
| `ARTICLE_ID` | Target article ID |
| `files_to_upload` | List of file paths to upload |

Example:

```yaml
TOKEN: <YOUR_FIGSHARE_TOKEN>
ARTICLE_ID: 12345678
files_to_upload:
  - /path/to/dataset.zip
  - /path/to/supplementary_materials.pdf
```

See [examples/figshare_upload.yaml](https://github.com/opencitations/piccione/blob/main/examples/figshare_upload.yaml) for a complete example.

## Usage

```bash
python -m piccione.upload.on_figshare config.yaml
```

## Features

- Chunked uploads (1MB chunks)
- MD5 hash verification
- Progress bar for each file
