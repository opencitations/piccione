---
title: SharePoint
description: Download files from SharePoint sites
---

## Prerequisites

- SharePoint site access
- Authentication cookies (FedAuth and rtFa)

## Obtaining authentication cookies

1. Log in to SharePoint in your browser
2. Open browser developer tools (F12)
3. Navigate to Application > Cookies
4. Copy the values of `FedAuth` and `rtFa` cookies

## Configuration

Create a YAML file with the following fields:

| Field | Description |
|-------|-------------|
| `site_url` | SharePoint site URL |
| `fedauth` | FedAuth cookie value |
| `rtfa` | rtFa cookie value |
| `folders` | List of folders to download |

Example:

```yaml
site_url: https://example.sharepoint.com/sites/MySite
fedauth: <FEDAUTH_COOKIE_VALUE>
rtfa: <RTFA_COOKIE_VALUE>
folders:
  - /Shared Documents/Project A
  - /Shared Documents/Project B/Data
```

See [examples/sharepoint_download.yaml](https://github.com/opencitations/piccione/blob/main/examples/sharepoint_download.yaml) for a complete example.

## Usage

Download all files:

```bash
python -m piccione.download.from_sharepoint config.yaml /output/directory
```

Discover folder structure only (no download):

```bash
python -m piccione.download.from_sharepoint config.yaml /output/directory --structure-only
```

Resume download using existing structure file:

```bash
python -m piccione.download.from_sharepoint config.yaml /output/directory --structure structure.json
```

## Arguments

| Argument | Description |
|----------|-------------|
| `config` | Path to YAML configuration file |
| `output_dir` | Output directory |
| `--structure-only` | Only discover folder structure without downloading |
| `--structure` | Path to existing `structure.json` file |

## Output

The module creates a `structure.json` file containing the discovered folder structure. This file can be reused with `--structure` to skip the discovery phase on subsequent runs.

Existing files are automatically skipped during download.

## Features

- Two-phase operation: discovery and download
- Rate limiting with automatic retry
- Skips existing files
- Progress reporting with download statistics
