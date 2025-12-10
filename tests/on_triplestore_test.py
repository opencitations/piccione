import os

import pytest
from tests.conftest import REDIS_DB, REDIS_PORT
from piccione.upload.cache_manager import CacheManager
from piccione.upload.on_triplestore import save_failed_query_file, upload_sparql_updates
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

        assert test_file in cache_manager.processed_files
        assert cache_manager._redis.sismember(CacheManager.REDIS_KEY, test_file)
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

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            stop_file=stop_file,
            cache_manager=cache_manager,
        )

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

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            cache_manager=cache_manager,
        )

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

        cache_manager = CacheManager(redis_port=REDIS_PORT, redis_db=REDIS_DB)
        upload_sparql_updates(
            SPARQL_ENDPOINT,
            sparql_dir,
            failed_file=failed_file,
            cache_manager=cache_manager,
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
