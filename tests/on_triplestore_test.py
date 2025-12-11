import os
from unittest.mock import MagicMock, patch

import pytest
from tests.conftest import REDIS_DB, REDIS_PORT
from piccione.upload.cache_manager import CacheManager
from piccione.upload.on_triplestore import remove_stop_file, save_failed_query_file, upload_sparql_updates
from sparqlite import SPARQLClient

SPARQL_ENDPOINT = "http://localhost:28890/sparql"


class TestCacheManager:
    def test_cache_initialization(self, clean_redis):
        initial_files = ["file1.sparql", "file2.sparql"]
        clean_redis.sadd(CacheManager.REDIS_KEY, *initial_files)

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)

        assert cache_manager.get_all() == set(initial_files)

    def test_add_and_contains(self, clean_redis):
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)

        test_file = "test.sparql"
        cache_manager.add(test_file)

        assert test_file in cache_manager

    def test_persistence(self, clean_redis):
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        test_files = ["test1.sparql", "test2.sparql"]
        for file in test_files:
            cache_manager.add(file)

        new_cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert new_cache_manager.get_all() == set(test_files)

    def test_redis_required(self):
        with pytest.raises(RuntimeError):
            CacheManager(redis_port=9999, redis_db=REDIS_DB)


class TestOnTriplestore:
    def test_failed_query_logging(self, temp_dir):
        failed_file = os.path.join(temp_dir, "failed_queries.txt")
        test_file = "failed_test.sparql"
        save_failed_query_file(test_file, failed_file)

        with open(failed_file, "r") as f:
            content = f.read()
        assert content == "failed_test.sparql\n"

    def test_upload_with_stop_file(self, temp_dir, clean_redis, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)
        failed_file = os.path.join(temp_dir, "failed_queries.txt")
        stop_file = os.path.join(temp_dir, ".stop_upload")

        test_query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "test object" .
            }
        }
        """
        for i in range(3):
            with open(os.path.join(sparql_dir, f"test{i}.sparql"), "w") as f:
                f.write(test_query)

        with open(stop_file, "w") as f:
            f.write("")

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

    def test_upload_with_failures(self, temp_dir, clean_redis, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)
        failed_file = os.path.join(temp_dir, "failed_queries.txt")

        valid_query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "test object" .
            }
        }
        """
        with open(os.path.join(sparql_dir, "valid.sparql"), "w") as f:
            f.write(valid_query)

        invalid_query = "INVALID SPARQL QUERY"
        with open(os.path.join(sparql_dir, "invalid.sparql"), "w") as f:
            f.write(invalid_query)

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

        with open(failed_file, "r") as f:
            failed_content = f.read()
        assert failed_content == "invalid.sparql\n"

    def test_data_loaded_to_triplestore(self, temp_dir, clean_redis, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)
        failed_file = os.path.join(temp_dir, "failed_queries.txt")

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://example.org/subject> <http://example.org/predicate> "test value" .
            }
        }
        """
        with open(os.path.join(sparql_dir, "insert.sparql"), "w") as f:
            f.write(query)

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

    def test_nonexistent_folder_returns_early(self, temp_dir, clean_redis):
        upload_sparql_updates(
            SPARQL_ENDPOINT,
            os.path.join(temp_dir, "nonexistent"),
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert cache_manager.get_all() == set()

    def test_empty_folder_returns_early(self, temp_dir, clean_redis, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "empty_sparql")
        os.makedirs(sparql_dir)

        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            redis_host="localhost",
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
        )
        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        assert cache_manager.get_all() == set()

    def test_empty_query_file_is_skipped(self, temp_dir, clean_redis, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)

        with open(os.path.join(sparql_dir, "empty.sparql"), "w") as f:
            f.write("   \n  ")

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

    def test_remove_stop_file_when_exists(self, temp_dir):
        stop_file = os.path.join(temp_dir, ".stop_upload")
        with open(stop_file, "w") as f:
            f.write("")

        assert os.path.exists(stop_file)
        remove_stop_file(stop_file)
        assert not os.path.exists(stop_file)

    def test_remove_stop_file_when_not_exists(self, temp_dir):
        stop_file = os.path.join(temp_dir, ".stop_upload")
        assert not os.path.exists(stop_file)
        remove_stop_file(stop_file)

    def test_creates_cache_manager_when_redis_params_provided(self, temp_dir, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "value" .
            }
        }
        """
        with open(os.path.join(sparql_dir, "test.sparql"), "w") as f:
            f.write(query)

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

    def test_upload_without_cache(self, temp_dir, clean_virtuoso):
        sparql_dir = os.path.join(temp_dir, "sparql_files")
        os.makedirs(sparql_dir)

        query = """
        INSERT DATA {
            GRAPH <http://test.graph> {
                <http://test.subject> <http://test.predicate> "no cache value" .
            }
        }
        """
        with open(os.path.join(sparql_dir, "test.sparql"), "w") as f:
            f.write(query)

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
