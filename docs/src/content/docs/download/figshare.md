---
title: Figshare download
description: Download files from Figshare articles
---

## Usage

```bash
python -m piccione.download.from_figshare <article_id> [-o <output_dir>]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `article_id` | Figshare article ID (integer) |
| `-o`, `--output-dir` | Output directory (default: current directory) |

Example:

```bash
python -m piccione.download.from_figshare 12345678 -o ./downloads
```

## Features

- Downloads all files from a public Figshare article
- MD5 checksum verification (when available)
- Progress bar with transfer rate
- Automatic pagination for articles with many files
