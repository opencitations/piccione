---
title: Zenodo
description: Upload files to Zenodo depositions
---

## Prerequisites

- Zenodo account
- Access token (obtain from Account Settings > Applications > Personal access tokens)

## Configuration

Create a YAML file with the following fields:

### Required fields

| Field | Description |
|-------|-------------|
| `zenodo_url` | Base URL: `https://zenodo.org` or `https://sandbox.zenodo.org` (or with `/api` suffix) |
| `access_token` | Zenodo access token |
| `title` | Deposition title |
| `publication_date` | Publication date (YYYY-MM-DD) |
| `files` | List of file paths to upload |

### Optional fields

| Field | Description |
|-------|-------------|
| `user_agent` | User-Agent string for API requests (e.g., `piccione/2.0.0`). See note below |
| `upload_type` | Resource type: `dataset` (default), `publication`, `poster`, `presentation`, `image`, `video`, `software`, `lesson`, `physicalobject`, `other` |
| `publisher` | Publisher name (default: `Zenodo`) |
| `creators` | List of objects: `name` (format: "Family, Given" or "Given Family"), `affiliation`, `orcid` |
| `description` | Plain text (converted to HTML with paragraph and list support) |
| `notes` | Additional notes, plain text (converted to HTML) |
| `method` | Methodology description, plain text (converted to HTML) |
| `keywords` | List of keywords (mapped to subjects) |
| `rights` | List of license objects. Each object can have either `id` (e.g., `cc-by-4.0`) for standard licenses, or `title`, `description`, and `link` for custom licenses |
| `related_identifiers` | List of objects: `identifier`, `relation`. Relation values: `isCitedBy`, `cites`, `isSupplementTo`, `isSupplementedBy`, `isDescribedBy`, `isNewVersionOf`, `isPreviousVersionOf`, `isPartOf`, `hasPart`, `isReferencedBy`, `references`, `isDocumentedBy`, `isDerivedFrom`, `isSourceOf`, `isIdenticalTo`, `isAlternateIdentifier` |
| `version` | Version string |
| `language` | ISO 639-2 or 639-3 language code |
| `locations` | List of objects: `lat`, `lon`, `place`, `description` |

**Note on User-Agent:** Specifying a `user_agent` is strongly recommended. Without a proper User-Agent header, Zenodo is more likely to return 403 Forbidden errors or block uploads, especially during periods of high server load.

For complete field documentation, see the [Zenodo REST API documentation](https://developers.zenodo.org/).

Example:

```yaml
zenodo_url: https://zenodo.org
access_token: <YOUR_ZENODO_TOKEN>
user_agent: piccione/2.0.0

title: My Dataset
publication_date: "2024-01-15"
upload_type: dataset

creators:
  - name: Doe, John
    affiliation: University
    orcid: 0000-0000-0000-0000

keywords:
  - data
  - research

rights:
  - id: cc-by-4.0
  # Or for custom licenses:
  # - title: Custom License
  #   description: License terms here
  #   link: https://example.com/license

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

- Create new depositions via InvenioRDM API
- Automatic metadata building from configuration
- Automatic retry with exponential backoff for network errors (unlimited attempts, max 60s delay)
- Rich progress bar with transfer speed and ETA
- Sandbox support for testing
- Optional auto-publish with `--publish` flag
- Plain text to HTML conversion with paragraph and bullet list support
- URL auto-linking in descriptions
