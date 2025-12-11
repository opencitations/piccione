import hashlib
from unittest.mock import MagicMock, patch

import pytest

from piccione.download.from_figshare import download_file, get_article_metadata


class TestGetArticleMetadata:
    def test_fetches_article_and_files(self):
        mock_article_response = MagicMock()
        mock_article_response.json.return_value = {"id": 123, "title": "Test Article"}

        mock_files_response = MagicMock()
        mock_files_response.json.return_value = [
            {"name": "file1.txt", "size": 100},
            {"name": "file2.txt", "size": 200},
        ]

        with patch("piccione.download.from_figshare.requests.get") as mock_get:
            mock_get.side_effect = [mock_article_response, mock_files_response]
            result = get_article_metadata(123)

        assert result == {
            "id": 123,
            "title": "Test Article",
            "files": [
                {"name": "file1.txt", "size": 100},
                {"name": "file2.txt", "size": 200},
            ],
        }

        assert mock_get.call_count == 2
        mock_get.assert_any_call("https://api.figshare.com/v2/articles/123")
        mock_get.assert_any_call(
            "https://api.figshare.com/v2/articles/123/files",
            params={"page_size": 1000},
        )


class TestDownloadFile:
    def test_downloads_and_writes_file(self, tmp_path):
        output_path = tmp_path / "downloaded.txt"
        content = b"file content here"

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [content]

        with patch("piccione.download.from_figshare.requests.get", return_value=mock_response):
            with patch("piccione.download.from_figshare.tqdm", side_effect=lambda **kw: MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock())):
                download_file("https://example.com/file", output_path, len(content))

        assert output_path.read_bytes() == content

    def test_verifies_md5_when_provided(self, tmp_path):
        output_path = tmp_path / "downloaded.txt"
        content = b"test content"
        expected_md5 = hashlib.md5(content).hexdigest()

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [content]

        with patch("piccione.download.from_figshare.requests.get", return_value=mock_response):
            with patch("piccione.download.from_figshare.tqdm", side_effect=lambda **kw: MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock())):
                download_file("https://example.com/file", output_path, len(content), expected_md5)

        assert output_path.read_bytes() == content

    def test_raises_on_md5_mismatch(self, tmp_path):
        output_path = tmp_path / "downloaded.txt"
        content = b"test content"
        wrong_md5 = "0" * 32

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [content]

        with patch("piccione.download.from_figshare.requests.get", return_value=mock_response):
            with patch("piccione.download.from_figshare.tqdm", side_effect=lambda **kw: MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock())):
                with pytest.raises(ValueError) as exc_info:
                    download_file("https://example.com/file", output_path, len(content), wrong_md5)

        actual_md5 = hashlib.md5(content).hexdigest()
        assert str(exc_info.value) == f"MD5 mismatch: expected {wrong_md5}, got {actual_md5}"
