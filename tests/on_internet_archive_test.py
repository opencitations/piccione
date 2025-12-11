from unittest.mock import MagicMock, patch

from piccione.upload.on_internet_archive import upload_files


class TestUploadFiles:
    def test_successful_upload(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
identifier: test-item-123
file_paths:
  - /path/to/file1.txt
  - /path/to/file2.txt
metadata:
  title: Test Item
  creator: Test Author
access_key: my_access_key
secret_key: my_secret_key
""")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("piccione.upload.on_internet_archive.upload", return_value=[mock_response]) as mock_upload:
            upload_files(str(config_file))

        mock_upload.assert_called_once_with(
            identifier="test-item-123",
            files=["/path/to/file1.txt", "/path/to/file2.txt"],
            metadata={"title": "Test Item", "creator": "Test Author"},
            access_key="my_access_key",
            secret_key="my_secret_key",
            verbose=True,
            verify=True,
            retries=3,
            retries_sleep=10,
            validate_identifier=True,
        )

    def test_failed_upload_prints_message(self, tmp_path, capsys):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
identifier: test-item
file_paths:
  - /path/to/file.txt
metadata:
  title: Test
access_key: key
secret_key: secret
""")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("piccione.upload.on_internet_archive.upload", return_value=[mock_response]):
            upload_files(str(config_file))

        captured = capsys.readouterr()
        assert captured.out == "Upload failed.\n"
