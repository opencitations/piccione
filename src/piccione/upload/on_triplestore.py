import argparse
import os

from piccione.upload.cache_manager import CacheManager
from sparqlite import SPARQLClient
from tqdm import tqdm


def save_failed_query_file(filename, failed_file):
    with open(failed_file, "a", encoding="utf8") as failed_file:
        failed_file.write(f"{filename}\n")


def remove_stop_file(stop_file):
    if os.path.exists(stop_file):
        os.remove(stop_file)
        print(f"Existing stop file {stop_file} has been removed.")


def upload_sparql_updates(
    endpoint,
    folder,
    failed_file="failed_queries.txt",
    stop_file=".stop_upload",
    redis_host=None,
    redis_port=None,
    redis_db=None,
    description="Processing files",
    show_progress=True,
):
    if not os.path.exists(folder):
        return

    cache_manager = None
    if redis_host is not None:
        cache_manager = CacheManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
        )

    all_files = [f for f in os.listdir(folder) if f.endswith(".sparql")]
    if cache_manager is not None:
        files_to_process = [f for f in all_files if f not in cache_manager]
    else:
        files_to_process = all_files

    if not files_to_process:
        return

    iterator = tqdm(files_to_process, desc=description) if show_progress else files_to_process
    with SPARQLClient(endpoint, max_retries=3, backoff_factor=5) as client:
        for file in iterator:
            if os.path.exists(stop_file):
                print(f"\nStop file {stop_file} detected. Interrupting the process...")
                break

            file_path = os.path.join(folder, file)

            with open(file_path, "r", encoding="utf-8") as f:
                query = f.read().strip()

            if not query:
                if cache_manager is not None:
                    cache_manager.add(file)
                continue

            try:
                client.update(query)
                if cache_manager is not None:
                    cache_manager.add(file)
            except Exception as e:
                print(f"Failed to execute {file}: {e}")
                save_failed_query_file(file, failed_file)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Execute SPARQL update queries on a triple store."
    )
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
    parser.add_argument(
        "--stop_file", type=str, default=".stop_upload", help="Path to stop file"
    )
    parser.add_argument("--redis_host", type=str, help="Redis host for caching")
    parser.add_argument("--redis_port", type=int, help="Redis port")
    parser.add_argument("--redis_db", type=int, help="Redis database number")

    args = parser.parse_args()

    remove_stop_file(args.stop_file)

    upload_sparql_updates(
        args.endpoint,
        args.folder,
        args.failed_file,
        args.stop_file,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_db=args.redis_db,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
