from unittest.mock import MagicMock, patch

import pytest
import requests

from piccione.upload.on_zenodo import ProgressFileWrapper, main, upload_file_with_retry


class TestProgressFileWrapper:
    def test_read_updates_progress(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        with patch("piccione.upload.on_zenodo.tqdm") as mock_tqdm:
            mock_pbar = MagicMock()
            mock_tqdm.return_value = mock_pbar
            wrapper = ProgressFileWrapper(str(test_file))
            data = wrapper.read(3)
            wrapper.close()

        assert data == b"hel"
        mock_pbar.update.assert_called_once_with(3)

    def test_len_returns_file_size(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        with patch("piccione.upload.on_zenodo.tqdm"):
            wrapper = ProgressFileWrapper(str(test_file))
            size = len(wrapper)
            wrapper.close()

        assert size == 5

    def test_close_closes_resources(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        with patch("piccione.upload.on_zenodo.tqdm") as mock_tqdm:
            mock_pbar = MagicMock()
            mock_tqdm.return_value = mock_pbar
            wrapper = ProgressFileWrapper(str(test_file))
            wrapper.close()

        assert wrapper.fp.closed
        mock_pbar.close.assert_called_once()


class TestUploadFileWithRetry:
    def test_successful_upload(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_response) as mock_put:
            with patch("piccione.upload.on_zenodo.tqdm"):
                result = upload_file_with_retry(
                    "https://bucket.zenodo.org", str(test_file), "token123"
                )

        assert result == mock_response
        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["headers"] == {"Authorization": "Bearer token123"}
        assert call_kwargs["timeout"] == (30, 300)

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
            with patch("piccione.upload.on_zenodo.tqdm"):
                with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                    result = upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123"
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
            with patch("piccione.upload.on_zenodo.tqdm"):
                with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                    result = upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123"
                    )

        assert result == mock_response
        assert mock_put.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_max_retries_exceeded(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
            mock_put.side_effect = requests.exceptions.Timeout()
            with patch("piccione.upload.on_zenodo.tqdm"):
                with patch("piccione.upload.on_zenodo.time.sleep"):
                    with pytest.raises(requests.exceptions.Timeout):
                        upload_file_with_retry(
                            "https://bucket.zenodo.org",
                            str(test_file),
                            "token123",
                            max_retries=3,
                        )

        assert mock_put.call_count == 3

    def test_http_error_raises_immediately(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "403 Forbidden"
        )

        with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_response) as mock_put:
            with patch("piccione.upload.on_zenodo.tqdm"):
                with pytest.raises(requests.exceptions.HTTPError):
                    upload_file_with_retry(
                        "https://bucket.zenodo.org", str(test_file), "token123"
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
project_id: 12345
files:
  - {test_file}
""")

        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "links": {"bucket": "https://sandbox.zenodo.org/bucket/123"}
        }

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.get", return_value=mock_get_response) as mock_get:
            with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_put_response):
                with patch("piccione.upload.on_zenodo.tqdm"):
                    main(str(config_file))

        mock_get.assert_called_once_with(
            "https://sandbox.zenodo.org/api/deposit/depositions/12345",
            headers={"Authorization": "Bearer test_token"},
        )

    def test_production_url_detection(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org
access_token: prod_token
project_id: 67890
files:
  - {test_file}
""")

        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "links": {"bucket": "https://zenodo.org/bucket/456"}
        }

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.get", return_value=mock_get_response) as mock_get:
            with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_put_response):
                with patch("piccione.upload.on_zenodo.tqdm"):
                    main(str(config_file))

        mock_get.assert_called_once_with(
            "https://zenodo.org/api/deposit/depositions/67890",
            headers={"Authorization": "Bearer prod_token"},
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
project_id: 123
files:
  - {file1}
  - {file2}
""")

        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "links": {"bucket": "https://zenodo.org/bucket/123"}
        }

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.get", return_value=mock_get_response):
            with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_put_response) as mock_put:
                with patch("piccione.upload.on_zenodo.tqdm"):
                    main(str(config_file))

        assert mock_put.call_count == 2
        call_urls = [call[0][0] for call in mock_put.call_args_list]
        assert call_urls == [
            "https://zenodo.org/bucket/123/file1.txt",
            "https://zenodo.org/bucket/123/file2.txt",
        ]
