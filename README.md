# Piccione

Pronounced *Py-ccione*.

[![Run tests](https://github.com/opencitations/piccione/actions/workflows/tests.yml/badge.svg)](https://github.com/opencitations/piccione/actions/workflows/tests.yml)
[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](https://opensource.org/licenses/ISC)

**PICCIONE** - Python Interface for Cloud Content Ingest and Outbound Network Export

A Python toolkit for uploading and downloading data to external repositories and cloud services.

## Installation

```bash
pip install piccione
```

## Modules

### Upload

#### Figshare
Upload files to Figshare.

```bash
python -m piccione.upload.on_figshare config.yaml
```

Configuration file format:
```yaml
TOKEN: your_figshare_token
ARTICLE_ID: 12345678
files_to_upload:
  - /path/to/file1.zip
  - /path/to/file2.zip
```

#### Zenodo
Upload files to Zenodo.

```bash
python -m piccione.upload.on_zenodo config.yaml
```

Configuration file format:
```yaml
access_token: your_zenodo_token
project_id: 12345678
zenodo_url: https://zenodo.org
files:
  - /path/to/file1.zip
  - /path/to/file2.zip
```

#### Internet Archive
Upload files to the Internet Archive.

```bash
python -m piccione.upload.on_internet_archive config.yaml
```

Configuration file format:
```yaml
identifier: my-archive-item
access_key: your_access_key
secret_key: your_secret_key
file_paths:
  - /path/to/file1.zip
metadata:
  title: My Archive Item
  description: Description of the item
```

#### Triplestore
Execute SPARQL UPDATE queries on a triplestore.

```bash
python -m piccione.upload.on_triplestore http://localhost:8890/sparql /path/to/sparql/folder
```

### Download

#### Figshare
Download all files from a Figshare article.

```bash
python -m piccione.download.from_figshare 12345678 -o /output/directory
```

## Documentation

Full documentation is available at: https://opencitations.github.io/piccione/

## Development

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
git clone https://github.com/opencitations/piccione.git
cd piccione
uv sync --all-extras --dev
```

### Running tests

```bash
uv run pytest tests/
```

### Building documentation locally

```bash
cd docs
npm install
npm run dev
```

## License

This project is licensed under the ISC License - see the [LICENSE.md](LICENSE.md) file for details.
