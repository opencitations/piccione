---
title: Zenodo
description: Upload files to Zenodo depositions
---

## Prerequisites

- Zenodo account
- Access token (obtain from Account Settings > Applications > Personal access tokens)

## Configuration

Create a YAML file with the following fields. Metadata fields follow the [InvenioRDM REST API schema](https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/).

### Required fields

| Field | Description |
|-------|-------------|
| `zenodo_url` | API base URL: `https://zenodo.org/api` or `https://sandbox.zenodo.org/api` |
| `access_token` | Zenodo access token |
| `user_agent` | User-Agent string for API requests (e.g., `piccione/2.0.0`). See note below |
| `title` | Deposition title |
| `publication_date` | Publication date (YYYY-MM-DD) |
| `resource_type` | Object with `id` field (e.g., `{id: dataset}`) |
| `creators` | List of InvenioRDM creator objects (see example below) |
| `access` | Access settings: `{record: public, files: public}` |
| `files` | List of file paths to upload |

### Optional fields

| Field | Description |
|-------|-------------|
| `record_id` | Existing record ID to create a new version of |
| `community` | Community ID for submission review (skipped on sandbox) |
| `description` | Plain text (converted to HTML with paragraph and list support) |
| `additional_descriptions` | List of objects: `description` (plain text, converted to HTML), `type` |
| `keywords` | List of keyword strings |
| `subjects` | List of subject objects |
| `rights` | List of license objects (`{id: cc-by-4.0}` or custom with `title`, `description`, `link`) |
| `related_identifiers` | List of InvenioRDM related identifier objects |
| `contributors` | List of InvenioRDM contributor objects |
| `dates` | List of InvenioRDM date objects |
| `version` | Version string |
| `language` | InvenioRDM language object (e.g., `{id: eng}`) |
| `locations` | InvenioRDM locations object |
| `identifiers` | List of alternate identifier objects |
| `publisher` | Publisher name |
| `references` | List of reference strings |

**Note on User-Agent:** Specifying a `user_agent` is strongly recommended. Without a proper User-Agent header, Zenodo is more likely to return 403 Forbidden errors or block uploads, especially during periods of high server load.

Example:

```yaml
zenodo_url: https://zenodo.org/api
access_token: <YOUR_ZENODO_TOKEN>
user_agent: piccione/2.0.0

title: My Dataset
publication_date: "2024-01-15"
resource_type:
  id: dataset

access:
  record: public
  files: public

creators:
  - person_or_org:
      type: personal
      given_name: John
      family_name: Doe
      identifiers:
        - scheme: orcid
          identifier: 0000-0000-0000-0000
    affiliations:
      - name: University of Bologna

keywords:
  - data
  - research

rights:
  - id: cc-by-4.0

description: |
  Dataset description here.

  Multiple paragraphs supported.

  - Bullet lists work too
  - Another item

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

- Create new depositions or new versions via InvenioRDM API
- Community submission review support
- Automatic retry with exponential backoff for network errors (unlimited attempts, max 60s delay)
- Rich progress bar with transfer speed and ETA
- Sandbox support for testing
- Optional auto-publish with `--publish` flag
- Plain text to HTML conversion with paragraph and bullet list support
