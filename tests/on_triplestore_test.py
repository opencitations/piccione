# SPDX-FileCopyrightText: 2025 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import redis
from sparqlite import SPARQLClient

from piccione.upload.cache_manager import CacheManager
from piccione.upload.on_triplestore import remove_stop_file, save_failed_query_file, upload_sparql_updates
from tests.conftest import REDIS_DB, REDIS_PORT

SPARQL_ENDPOINT = "http://localhost:28890/sparql"


class TestCacheManager:
    def test_cache_initialization(self, clean_redis: redis.Redis) -> None:
        initial_files = ["file1.sparql", "file2.sparql"]
        clean_redis.sadd(CacheManager.REDIS_KEY, *initial_files)

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)

        assert cache_manager.get_all() == set(initial_files)

    def test_add_and_contains(self, clean_redis: redis.Redis) -> None:
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)

        test_file = "test.sparql"
        cache_manager.add(test_file)

        assert test_file in cache_manager

    def test_persistence(self, clean_redis: redis.Redis) -> None:
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        test_files = ["test1.sparql", "test2.sparql"]
        for file in test_files:
            cache_manager.add(file)

        new_cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert new_cache_manager.get_all() == set(test_files)

    def test_redis_required(self) -> None:
        with pytest.raises(RuntimeError):
            CacheManager(redis_port=9999, redis_db=REDIS_DB)


class TestOnTriplestore:
    def test_failed_query_logging(self, temp_dir: str) -> None:
        failed_file = str(Path(temp_dir) / "failed_queries.txt")
        test_file = "failed_test.sparql"
        save_failed_query_file(test_file, failed_file)

        content = Path(failed_file).read_text()
        assert content == "failed_test.sparql\n"

    def test_upload_with_stop_file(self, temp_dir: str, clean_redis: redis.Redis, clean_virtuoso: str) -> None:
        temp = Path(temp_dir)
        sparql_dir = str(temp / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)
        failed_file = str(temp / "failed_queries.txt")
        stop_file = str(temp / ".stop_upload")

        test_query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "test object" .
            }
        }
        """
        for i in range(3):
            (Path(sparql_dir) / f"test{i}.sparql").write_text(test_query)

        Path(stop_file).write_text("")

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            stop_file=stop_file,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert cache_manager.get_all() == set()

    def test_upload_with_failures(self, temp_dir: str, clean_redis: redis.Redis, clean_virtuoso: str) -> None:
        temp = Path(temp_dir)
        sparql_dir = str(temp / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)
        failed_file = str(temp / "failed_queries.txt")

        valid_query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "test object" .
            }
        }
        """
        (Path(sparql_dir) / "valid.sparql").write_text(valid_query)

        invalid_query = "INVALID SPARQL QUERY"
        (Path(sparql_dir) / "invalid.sparql").write_text(invalid_query)

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert "valid.sparql" in cache_manager
        assert "invalid.sparql" not in cache_manager

        failed_content = Path(failed_file).read_text()
        assert failed_content == "invalid.sparql\n"

    def test_data_loaded_to_triplestore(
        self,
        temp_dir: str,
        clean_redis: redis.Redis,
        clean_virtuoso: str,
    ) -> None:
        temp = Path(temp_dir)
        sparql_dir = str(temp / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)
        failed_file = str(temp / "failed_queries.txt")

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://example.org/subject> <http://example.org/predicate> "test value" .
            }
        }
        """
        (Path(sparql_dir) / "insert.sparql").write_text(query)

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
            show_progress=False,
        )

        with SPARQLClient(SPARQL_ENDPOINT) as client:
            result = client.query("""
                SELECT ?o WHERE {
                    GRAPH <http://test.graph> {
                        <http://example.org/subject> <http://example.org/predicate> ?o .
                    }
                }
            """)

        bindings = result["results"]["bindings"]
        assert len(bindings) == 1
        assert bindings[0]["o"]["value"] == "test value"

    def test_nonexistent_folder_returns_early(self, temp_dir: str, clean_redis: redis.Redis) -> None:
        upload_sparql_updates(
            SPARQL_ENDPOINT,
            str(Path(temp_dir) / "nonexistent"),
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert cache_manager.get_all() == set()

    def test_empty_folder_returns_early(
        self,
        temp_dir: str,
        clean_redis: redis.Redis,
        clean_virtuoso: str,
    ) -> None:
        sparql_dir = str(Path(temp_dir) / "empty_sparql")
        Path(sparql_dir).mkdir(parents=True)

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert cache_manager.get_all() == set()

    def test_empty_query_file_is_skipped(
        self,
        temp_dir: str,
        clean_redis: redis.Redis,
        clean_virtuoso: str,
    ) -> None:
        sparql_dir = str(Path(temp_dir) / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)

        (Path(sparql_dir) / "empty.sparql").write_text("   \n  ")

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
            show_progress=False,
        )
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert "empty.sparql" in cache_manager

    def test_remove_stop_file_when_exists(self, temp_dir: str) -> None:
        stop_file = str(Path(temp_dir) / ".stop_upload")
        Path(stop_file).write_text("")

        assert Path(stop_file).exists()
        remove_stop_file(stop_file)
        assert not Path(stop_file).exists()

    def test_remove_stop_file_when_not_exists(self, temp_dir: str) -> None:
        stop_file = str(Path(temp_dir) / ".stop_upload")
        assert not Path(stop_file).exists()
        remove_stop_file(stop_file)

    def test_creates_cache_manager_when_redis_params_provided(self, temp_dir: str, clean_virtuoso: str) -> None:
        sparql_dir = str(Path(temp_dir) / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "value" .
            }
        }
        """
        (Path(sparql_dir) / "test.sparql").write_text(query)

        mock_cache = MagicMock()
        mock_cache.__contains__ = MagicMock(return_value=False)

        with patch("piccione.upload.on_triplestore.CacheManager", return_value=mock_cache):
            upload_sparql_updates(
                SPARQL_ENDPOINT,
                sparql_dir,
                redis_host="localhost",
                redis_port=6379,
                redis_db=0,
                show_progress=False,
            )

        mock_cache.add.assert_called_once_with("test.sparql")

    def test_upload_without_cache(self, temp_dir: str, clean_virtuoso: str) -> None:
        sparql_dir = str(Path(temp_dir) / "sparql_files")
        Path(sparql_dir).mkdir(parents=True)

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "no cache value" .
            }
        }
        """
        (Path(sparql_dir) / "test.sparql").write_text(query)

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            show_progress=False,
        )

        with SPARQLClient(SPARQL_ENDPOINT) as client:
            result = client.query("""
                SELECT ?o WHERE {
                    GRAPH <http://test.graph> {
                        <http://test.subject> <http://test.predicate> ?o .
                    }
                }
            """)

        bindings = result["results"]["bindings"]
        assert len(bindings) == 1
        assert bindings[0]["o"]["value"] == "no cache value"
