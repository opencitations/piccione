---
title: Triplestore
description: Execute SPARQL updates on a triplestore endpoint
---

## Prerequisites

- SPARQL endpoint with update support
- Redis server (for progress tracking)
- Folder containing `.sparql` files

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

Example:

```bash
python -m piccione.upload.on_triplestore http://localhost:8890/sparql ./sparql_queries
```

## Caching

The module uses Redis to track processed files. This allows resuming interrupted uploads without re-executing completed queries.

- Redis host: `localhost`
- Redis port: `6379`
- Redis DB: `4`
- Key: `processed_files` (SET)

## Graceful interruption

Create the stop file (default: `.stop_upload`) in the working directory to stop processing after the current query completes:

```bash
touch .stop_upload
```

## Features

- Redis-backed progress tracking
- Automatic retry (3 retries with 5s backoff)
- Failed queries logged to file
- Progress bar
