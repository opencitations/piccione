# SPDX-FileCopyrightText: 2025 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

import argparse
from pathlib import Path

from rich.console import Console
from sparqlite import SPARQLClient
from tqdm import tqdm

from piccione.upload.cache_manager import CacheManager

console = Console()


def save_failed_query_file(filename: str, failed_file: str | Path) -> None:
    with Path(failed_file).open("a", encoding="utf8") as f:
        f.write(f"{filename}\n")


def remove_stop_file(stop_file: str | Path) -> None:
    if Path(stop_file).exists():
        Path(stop_file).unlink()
        console.print(f"Existing stop file {stop_file} has been removed.")


def upload_sparql_updates(  # noqa: PLR0913
    endpoint: str,
    folder: str | Path,
    *,
    failed_file: str | Path = "failed_queries.txt",
    stop_file: str | Path = ".stop_upload",
    redis_host: str | None = None,
    redis_port: int = 6379,
    redis_db: int = 4,
    description: str = "Processing files",
    show_progress: bool = True,
) -> None:
    if not Path(folder).exists():
        return

    cache_manager = None
    if redis_host is not None:
        cache_manager = CacheManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
        )

    all_files = [f.name for f in Path(folder).iterdir() if f.name.endswith(".sparql")]
    files_to_process = [f for f in all_files if f not in cache_manager] if cache_manager is not None else all_files

    if not files_to_process:
        return

    iterator = tqdm(files_to_process, desc=description) if show_progress else files_to_process
    with SPARQLClient(endpoint, max_retries=3, backoff_factor=5) as client:
        for file in iterator:
            if Path(stop_file).exists():
                console.print(f"\nStop file {stop_file} detected. Interrupting the process...")
                break

            file_path = Path(folder) / file

            with file_path.open(encoding="utf-8") as f:
                query = f.read().strip()

            if not query:
                if cache_manager is not None:
                    cache_manager.add(file)
                continue

            try:
                client.update(query)
                if cache_manager is not None:
                    cache_manager.add(file)
            except Exception as e:  # noqa: BLE001
                console.print(f"Failed to execute {file}: {e}")
                save_failed_query_file(file, failed_file)


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Execute SPARQL update queries on a triple store.")
    parser.add_argument("endpoint", type=str, help="Endpoint URL of the triple store")
    parser.add_argument(
        "folder",
        type=str,
        help="Path to the folder containing SPARQL update query files",
    )
    parser.add_argument(
        "--failed_file",
        type=str,
        default="failed_queries.txt",
        help="Path to failed queries file",
    )
    parser.add_argument("--stop_file", type=str, default=".stop_upload", help="Path to stop file")
    parser.add_argument("--redis_host", type=str, help="Redis host for caching")
    parser.add_argument("--redis_port", type=int, help="Redis port")
    parser.add_argument("--redis_db", type=int, help="Redis database number")

    args = parser.parse_args()

    remove_stop_file(args.stop_file)

    upload_sparql_updates(
        args.endpoint,
        args.folder,
        failed_file=args.failed_file,
        stop_file=args.stop_file,
        redis_host=args.redis_host,
        redis_port=args.redis_port or 6379,
        redis_db=args.redis_db or 4,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
