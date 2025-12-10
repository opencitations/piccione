import shutil
import subprocess
import tempfile
import time

import pytest
import redis
from virtuoso_utilities.launch_virtuoso import launch_virtuoso, remove_container

VIRTUOSO_CONTAINER_NAME = "piccione-test-virtuoso"
VIRTUOSO_HTTP_PORT = 28890
VIRTUOSO_ISQL_PORT = 21111
DBA_PASSWORD = "dba"

REDIS_CONTAINER_NAME = "piccione-test-redis"
REDIS_IMAGE = "redis:7"
REDIS_PORT = 26379
REDIS_DB = 2


@pytest.fixture(scope="session")
def virtuoso_container():
    data_dir = tempfile.mkdtemp(prefix="virtuoso_data_")
    launch_virtuoso(
        name=VIRTUOSO_CONTAINER_NAME,
        data_dir=data_dir,
        http_port=VIRTUOSO_HTTP_PORT,
        isql_port=VIRTUOSO_ISQL_PORT,
        dba_password=DBA_PASSWORD,
        memory="2g",
        detach=True,
        wait_ready=True,
        enable_write_permissions=True,
        force_remove=True,
    )
    yield VIRTUOSO_CONTAINER_NAME
    remove_container(VIRTUOSO_CONTAINER_NAME)
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def redis_container():
    subprocess.run(
        ["docker", "rm", "-f", REDIS_CONTAINER_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cmd = [
        "docker", "run", "-d",
        "--name", REDIS_CONTAINER_NAME,
        "-p", f"{REDIS_PORT}:6379",
        REDIS_IMAGE,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    time.sleep(2)
    yield REDIS_CONTAINER_NAME
    subprocess.run(["docker", "rm", "-f", REDIS_CONTAINER_NAME], check=True)


@pytest.fixture
def clean_virtuoso(virtuoso_container):
    cleanup_cmd = [
        "docker", "exec", virtuoso_container,
        "/opt/virtuoso-opensource/bin/isql",
        "-U", "dba", "-P", DBA_PASSWORD,
        "exec=log_enable(3,1); RDF_GLOBAL_RESET();",
    ]
    subprocess.run(cleanup_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield virtuoso_container


@pytest.fixture
def clean_redis(redis_container):
    r = redis.Redis(host="localhost", port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    r.flushdb()
    yield r
    r.flushdb()
    r.close()


@pytest.fixture
def temp_dir():
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)
