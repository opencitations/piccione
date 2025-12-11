import hashlib
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import requests

from piccione.upload.on_figshare import (
    complete_upload,
    create_file,
    get_file_check_data,
    issue_request,
    main,
    upload_part,
    upload_parts,
)


class TestGetFileCheckData:
    def test_returns_md5_and_size(self, tmp_path):
        test_file = tmp_path / "test.txt"
        content = b"hello world"
        test_file.write_bytes(content)

        md5, size = get_file_check_data(str(test_file))

        assert md5 == hashlib.md5(content).hexdigest()
        assert size == 11

    def test_handles_large_file_in_chunks(self, tmp_path):
        test_file = tmp_path / "large.bin"
        content = b"x" * 2097152  # 2MB (2 chunks)
        test_file.write_bytes(content)

        md5, size = get_file_check_data(str(test_file))

        assert md5 == hashlib.md5(content).hexdigest()
        assert size == 2097152


class TestIssueRequest:
    def test_successful_json_response(self):
        mock_response = MagicMock()
        mock_response.content = b'{"key": "value"}'
        mock_response.raise_for_status = MagicMock()

        with patch("piccione.upload.on_figshare.requests.request", return_value=mock_response) as mock_req:
            result = issue_request("GET", "https://api.figshare.com/test", "mytoken")

        assert result == {"key": "value"}
        mock_req.assert_called_once_with(
            "GET",
            "https://api.figshare.com/test",
            headers={"Authorization": "token mytoken"},
            data=None,
        )

    def test_successful_binary_response(self):
        mock_response = MagicMock()
        mock_response.content = b"binary data"
        mock_response.raise_for_status = MagicMock()

        with patch("piccione.upload.on_figshare.requests.request", return_value=mock_response):
            result = issue_request("GET", "https://api.figshare.com/test", "token")

        assert result == b"binary data"

    def test_sends_json_data_when_not_binary(self):
        mock_response = MagicMock()
        mock_response.content = b'{"result": "ok"}'
        mock_response.raise_for_status = MagicMock()

        with patch("piccione.upload.on_figshare.requests.request", return_value=mock_response) as mock_req:
            issue_request("POST", "https://api.figshare.com/test", "token", data={"foo": "bar"})

        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["data"] == '{"foo": "bar"}'

    def test_sends_raw_data_when_binary(self):
        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        with patch("piccione.upload.on_figshare.requests.request", return_value=mock_response) as mock_req:
            issue_request("PUT", "https://api.figshare.com/test", "token", data=b"raw bytes", binary=True)

        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["data"] == b"raw bytes"

    def test_http_error_is_raised(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_response.text = "Resource not found"

        with patch("piccione.upload.on_figshare.requests.request", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                issue_request("GET", "https://api.figshare.com/test", "token")


class TestUploadPart:
    def test_uploads_correct_chunk(self):
        file_info = {"upload_url": "https://upload.figshare.com/parts"}
        stream = BytesIO(b"0123456789")
        part = {"partNo": 1, "startOffset": 2, "endOffset": 5}

        with patch("piccione.upload.on_figshare.issue_request") as mock_issue:
            upload_part(file_info, stream, part, "token123")

        mock_issue.assert_called_once_with(
            method="PUT",
            url="https://upload.figshare.com/parts/1",
            data=b"2345",
            binary=True,
            token="token123",
        )


class TestUploadParts:
    def test_uploads_all_parts(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"0123456789")

        file_info = {"upload_url": "https://upload.figshare.com/parts"}
        parts_response = {
            "parts": [
                {"partNo": 1, "startOffset": 0, "endOffset": 4},
                {"partNo": 2, "startOffset": 5, "endOffset": 9},
            ]
        }

        with patch("piccione.upload.on_figshare.issue_request", return_value=parts_response) as mock_issue:
            with patch("piccione.upload.on_figshare.tqdm"):
                upload_parts(file_info, str(test_file), "token")

        assert mock_issue.call_count == 3  # 1 GET + 2 PUTs
        calls = mock_issue.call_args_list
        assert calls[0][1]["method"] == "GET"
        assert calls[1][1]["method"] == "PUT"
        assert calls[1][1]["data"] == b"01234"
        assert calls[2][1]["method"] == "PUT"
        assert calls[2][1]["data"] == b"56789"


class TestCreateFile:
    def test_creates_file_and_returns_info(self, tmp_path):
        test_file = tmp_path / "data.txt"
        test_file.write_bytes(b"content")

        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {"location": "https://api.figshare.com/files/123"}

        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {"id": 123, "name": "data.txt"}

        with patch("piccione.upload.on_figshare.requests.post", return_value=mock_post_response) as mock_post:
            with patch("piccione.upload.on_figshare.requests.get", return_value=mock_get_response) as mock_get:
                result = create_file("article_1", "data.txt", str(test_file), "token")

        assert result == {"id": 123, "name": "data.txt"}

        mock_post.assert_called_once()
        post_call = mock_post.call_args
        assert post_call[0][0] == "https://api.figshare.com/v2/account/articles/article_1/files"
        assert post_call[1]["headers"] == {"Authorization": "token token"}
        assert post_call[1]["json"]["name"] == "data.txt"
        assert post_call[1]["json"]["size"] == 7
        assert post_call[1]["json"]["md5"] == hashlib.md5(b"content").hexdigest()

        mock_get.assert_called_once_with(
            "https://api.figshare.com/files/123",
            headers={"Authorization": "token token"},
        )


class TestCompleteUpload:
    def test_sends_post_request(self):
        with patch("piccione.upload.on_figshare.issue_request") as mock_issue:
            complete_upload("article_1", "file_123", "mytoken")

        mock_issue.assert_called_once_with(
            method="POST",
            url="https://api.figshare.com/v2/account/articles/article_1/files/file_123",
            token="mytoken",
        )


class TestMain:
    def test_uploads_all_files(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(f"""
TOKEN: test_token
ARTICLE_ID: "12345"
files_to_upload:
  - {file1}
  - {file2}
""")

        with patch("piccione.upload.on_figshare.create_file") as mock_create:
            mock_create.side_effect = [
                {"id": "f1", "upload_url": "https://upload/1"},
                {"id": "f2", "upload_url": "https://upload/2"},
            ]
            with patch("piccione.upload.on_figshare.upload_parts"):
                with patch("piccione.upload.on_figshare.complete_upload") as mock_complete:
                    with patch("piccione.upload.on_figshare.tqdm", side_effect=lambda x, **kw: x):
                        main(str(config_file))

        assert mock_create.call_count == 2
        assert mock_complete.call_count == 2
        mock_complete.assert_any_call("12345", "f1", "test_token")
        mock_complete.assert_any_call("12345", "f2", "test_token")
