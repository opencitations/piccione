from unittest.mock import MagicMock, patch

import pytest
import requests

from piccione.upload.on_zenodo import ProgressFileWrapper, main, upload_file_with_retry


class TestProgressFileWrapper:
    def test_read_updates_progress(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, "task-1")
        data = wrapper.read(3)
        wrapper.close()

        assert data == b"hel"
        mock_progress.update.assert_called_once_with("task-1", advance=3)

    def test_len_returns_file_size(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, "task-1")
        size = len(wrapper)
        wrapper.close()

        assert size == 5

    def test_close_closes_resources(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, "task-1")
        wrapper.close()

        assert wrapper.fp.closed


class TestUploadFileWithRetry:
    def test_successful_upload(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_response) as mock_put:
            with patch("piccione.upload.on_zenodo.Progress"):
                result = upload_file_with_retry(
                    "https://bucket.zenodo.org", str(test_file), "token123", "TestAgent/1.0"
                )

        assert result == mock_response
        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["headers"] == {"Authorization": "Bearer token123", "User-Agent": "TestAgent/1.0"}
        assert call_kwargs["timeout"] == (30, 3600)

    def test_retry_on_timeout(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
            mock_put.side_effect = [
                requests.exceptions.Timeout(),
                mock_response,
            ]
            with patch("piccione.upload.on_zenodo.Progress"):
                with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                    result = upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert result == mock_response
        assert mock_put.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_retry_on_connection_error(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
            mock_put.side_effect = [
                requests.exceptions.ConnectionError(),
                requests.exceptions.ConnectionError(),
                mock_response,
            ]
            with patch("piccione.upload.on_zenodo.Progress"):
                with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                    result = upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert result == mock_response
        assert mock_put.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_http_error_raises_immediately(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "403 Forbidden"
        )

        with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_response) as mock_put:
            with patch("piccione.upload.on_zenodo.Progress"):
                with pytest.raises(requests.exceptions.HTTPError):
                    upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert mock_put.call_count == 1


class TestMain:
    def test_sandbox_url_detection(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://sandbox.zenodo.org
access_token: test_token
user_agent: TestAgent/1.0
project_id: 12345
files:
  - {test_file}
""")

        mock_draft = {"id": 999, "files": [], "links": {"bucket": "https://sandbox.zenodo.org/bucket/123"}}

        with patch("piccione.upload.on_zenodo.create_new_version", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.update_metadata"):
                with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                    main(str(config_file))

        mock_create.assert_called_once_with(
            "https://sandbox.zenodo.org",
            "test_token",
            12345,
            "TestAgent/1.0",
        )

    def test_production_url_detection(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org
access_token: prod_token
user_agent: TestAgent/1.0
project_id: 67890
files:
  - {test_file}
""")

        mock_draft = {"id": 999, "files": [], "links": {"bucket": "https://zenodo.org/bucket/456"}}

        with patch("piccione.upload.on_zenodo.create_new_version", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.update_metadata"):
                with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                    main(str(config_file))

        mock_create.assert_called_once_with(
            "https://zenodo.org",
            "prod_token",
            67890,
            "TestAgent/1.0",
        )

    def test_uploads_all_files(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org
access_token: token
user_agent: TestAgent/1.0
project_id: 123
files:
  - {file1}
  - {file2}
""")

        mock_draft = {"id": 999, "files": [], "links": {"bucket": "https://zenodo.org/bucket/123"}}

        with patch("piccione.upload.on_zenodo.create_new_version", return_value=mock_draft):
            with patch("piccione.upload.on_zenodo.update_metadata"):
                with patch("piccione.upload.on_zenodo.upload_file_with_retry") as mock_upload:
                    main(str(config_file))

        assert mock_upload.call_count == 2
        call_args = [call[0] for call in mock_upload.call_args_list]
        assert call_args[0] == ("https://zenodo.org/bucket/123", str(file1), "token", "TestAgent/1.0")
        assert call_args[1] == ("https://zenodo.org/bucket/123", str(file2), "token", "TestAgent/1.0")
