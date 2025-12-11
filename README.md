# Piccione

<p align="center">
  <img src="docs/public/piccione.png" alt="Piccione logo" width="200">
</p>

Pronounced *Py-ccione*.

[![Run tests](https://github.com/opencitations/piccione/actions/workflows/tests.yml/badge.svg)](https://github.com/opencitations/piccione/actions/workflows/tests.yml)
[![Coverage](https://opencitations.github.io/piccione/coverage/coverage-badge.svg)](https://opencitations.github.io/piccione/coverage/)
[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](https://opensource.org/licenses/ISC)

**PICCIONE** - Python Interface for Cloud Content Ingest and Outbound Network Export

A Python toolkit for uploading and downloading data to external repositories and cloud services.

## Installation

```bash
pip install piccione
```

## Quick start

### Upload to Figshare

```bash
python -m piccione.upload.on_figshare config.yaml
```

### Upload to Zenodo

```bash
python -m piccione.upload.on_zenodo config.yaml
```

### Upload to Internet Archive

```bash
python -m piccione.upload.on_internet_archive config.yaml
```

### Upload to triplestore

```bash
python -m piccione.upload.on_triplestore <endpoint> <folder>
```

### Download from Figshare

```bash
python -m piccione.download.from_figshare <article_id> -o <output_dir>
```

### Download from SharePoint

```bash
python -m piccione.download.from_sharepoint config.yaml <output_dir>
```

## Documentation

Full documentation: https://opencitations.github.io/piccione/

Configuration examples: [examples/](examples/)

## Development

```bash
git clone https://github.com/opencitations/piccione.git
cd piccione
uv sync --all-extras --dev
uv run pytest tests/
```

## License

ISC License - see [LICENSE.md](LICENSE.md)
