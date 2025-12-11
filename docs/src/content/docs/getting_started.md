---
title: Getting started
description: How to install and use piccione
---

## Installation

Install the package using pip:

```bash
pip install piccione
```

Or with uv:

```bash
uv add piccione
```

## Modules overview

| Module | Description |
|--------|-------------|
| [Figshare upload](/piccione/upload/figshare/) | Upload files to Figshare articles |
| [Zenodo upload](/piccione/upload/zenodo/) | Upload files to Zenodo depositions |
| [Internet Archive upload](/piccione/upload/internet_archive/) | Upload files to Internet Archive items |
| [Triplestore upload](/piccione/upload/triplestore/) | Execute SPARQL updates on triplestore endpoints |
| [Figshare download](/piccione/download/figshare/) | Download files from Figshare articles |
| [SharePoint download](/piccione/download/sharepoint/) | Download files from SharePoint sites |

## Configuration

Most modules use YAML configuration files. Example configurations are available in the [examples folder](https://github.com/opencitations/piccione/tree/main/examples).

## Next steps

- Check out the [upload modules](/piccione/upload/figshare/) for uploading data
- Check out the [download modules](/piccione/download/figshare/) for downloading data
- Browse the [example configurations](https://github.com/opencitations/piccione/tree/main/examples)
