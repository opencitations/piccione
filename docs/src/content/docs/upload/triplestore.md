---
title: Triplestore
description: Execute SPARQL updates on a triplestore endpoint
---

## Prerequisites

- SPARQL endpoint with update support
- Folder containing `.sparql` files
- Redis server (optional, for progress tracking)

## Usage

```bash
python -m piccione.upload.on_triplestore <endpoint> <folder> [options]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `endpoint` | SPARQL endpoint URL (e.g., `http://localhost:8890/sparql`) |
| `folder` | Path to folder containing `.sparql` files |
| `--failed_file` | File to record failed queries (default: `failed_queries.txt`) |
| `--stop_file` | File to stop the process (default: `.stop_upload`) |
| `--redis_host` | Redis host for caching |
| `--redis_port` | Redis port |
| `--redis_db` | Redis database number |

Example without caching:

```bash
python -m piccione.upload.on_triplestore http://localhost:8890/sparql ./sparql_queries
```

Example with caching:

```bash
python -m piccione.upload.on_triplestore http://localhost:8890/sparql ./sparql_queries \
    --redis_host localhost --redis_port 6379 --redis_db 0
```

## Caching

Caching is optional. When enabled, the module uses Redis to track processed files, allowing interrupted uploads to resume without re-executing completed queries.

To enable caching, specify all three Redis parameters: `--redis_host`, `--redis_port`, `--redis_db`.

The cache uses the key `processed_files` (Redis SET).

## Programmatic usage

```python
from piccione.upload.on_triplestore import upload_sparql_updates

# Without caching
upload_sparql_updates(
    endpoint="http://localhost:8890/sparql",
    folder="./sparql_queries",
)

# With caching
upload_sparql_updates(
    endpoint="http://localhost:8890/sparql",
    folder="./sparql_queries",
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
)
```

## Graceful interruption

Create the stop file (default: `.stop_upload`) in the working directory to stop processing after the current query completes:

```bash
touch .stop_upload
```

## Features

- Optional Redis-backed progress tracking
- Automatic retry (3 retries with 5s backoff)
- Failed queries logged to file
- Progress bar
