from unittest.mock import MagicMock, patch

import pytest
import requests

from piccione.upload.on_zenodo import (
    ProgressFileWrapper,
    build_inveniordm_payload,
    main,
    publish_draft,
    text_to_html,
    upload_file_with_retry,
)


class TestProgressFileWrapper:
    def test_read_updates_progress(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, 1)
        data = wrapper.read(3)
        wrapper.close()

        assert data == b"hel"
        mock_progress.update.assert_called_once_with(1, advance=3)

    def test_len_returns_file_size(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, 1)
        size = len(wrapper)
        wrapper.close()

        assert size == 5

    def test_close_closes_resources(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_progress = MagicMock()
        wrapper = ProgressFileWrapper(str(test_file), mock_progress, 1)
        wrapper.close()

        assert wrapper.fp.closed


class TestTextToHtml:
    def test_single_paragraph(self):
        assert text_to_html("Single paragraph") == "<p>Single paragraph</p>"

    def test_multiple_paragraphs(self):
        assert text_to_html("First paragraph\n\nSecond paragraph") == "<p>First paragraph</p><p>Second paragraph</p>"

    def test_paragraph_with_line_breaks(self):
        assert text_to_html("Line one\nLine two") == "<p>Line one<br>Line two</p>"

    def test_bullet_list(self):
        assert text_to_html("- Item one\n- Item two") == "<ul><li>Item one</li><li>Item two</li></ul>"

    def test_paragraph_then_list(self):
        assert text_to_html("Introduction\n\n- Item one\n- Item two") == "<p>Introduction</p><ul><li>Item one</li><li>Item two</li></ul>"


class TestBuildInvenioRdmPayload:
    def test_minimal_config(self):
        config = {
            "title": "Test Title",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "creators": [{"person_or_org": {"type": "personal", "given_name": "John", "family_name": "Doe"}}],
            "access": {"record": "public", "files": "public"},
        }
        result = build_inveniordm_payload(config)
        assert result == {
            "access": {"record": "public", "files": "public"},
            "files": {"enabled": True},
            "metadata": {
                "title": "Test Title",
                "publication_date": "2024-01-15",
                "resource_type": {"id": "dataset"},
                "creators": [{"person_or_org": {"type": "personal", "given_name": "John", "family_name": "Doe"}}],
            },
        }

    def test_with_description(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "creators": [{"person_or_org": {"type": "personal", "given_name": "J", "family_name": "D"}}],
            "access": {"record": "public", "files": "public"},
            "description": "Test description",
        }
        result = build_inveniordm_payload(config)
        assert result["metadata"]["description"] == "<p>Test description</p>"

    def test_with_additional_descriptions(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "creators": [{"person_or_org": {"type": "personal", "given_name": "J", "family_name": "D"}}],
            "access": {"record": "public", "files": "public"},
            "additional_descriptions": [
                {"description": "Some notes", "type": {"id": "notes"}},
            ],
        }
        result = build_inveniordm_payload(config)
        assert result["metadata"]["additional_descriptions"] == [
            {"description": "<p>Some notes</p>", "type": {"id": "notes"}},
        ]

    def test_passthrough_fields(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "creators": [{"person_or_org": {"type": "personal", "given_name": "J", "family_name": "D"}}],
            "access": {"record": "public", "files": "public"},
            "keywords": ["data", "research"],
            "rights": [{"id": "cc-by-4.0"}],
            "version": "1.0.0",
            "language": {"id": "eng"},
            "publisher": "Zenodo",
        }
        result = build_inveniordm_payload(config)
        assert result["metadata"]["keywords"] == ["data", "research"]
        assert result["metadata"]["rights"] == [{"id": "cc-by-4.0"}]
        assert result["metadata"]["version"] == "1.0.0"
        assert result["metadata"]["language"] == {"id": "eng"}
        assert result["metadata"]["publisher"] == "Zenodo"

    def test_files_always_enabled(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "creators": [{"person_or_org": {"type": "personal", "given_name": "J", "family_name": "D"}}],
            "access": {"record": "public", "files": "public"},
        }
        result = build_inveniordm_payload(config)
        assert result["files"] == {"enabled": True}


class TestPublishDraft:
    def test_successful_publish(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"id": "abc123", "links": {"self_html": "https://zenodo.org/records/abc123"}}

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response) as mock_post:
            result = publish_draft("https://zenodo.org/api", "token", "draft-id", "Agent/1.0")

        assert result == {"id": "abc123", "links": {"self_html": "https://zenodo.org/records/abc123"}}
        mock_post.assert_called_once_with(
            "https://zenodo.org/api/records/draft-id/draft/actions/publish",
            headers={"Authorization": "Bearer token", "User-Agent": "Agent/1.0"},
        )

    def test_publish_error_raises(self):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                publish_draft("https://zenodo.org/api", "token", "draft-id", "Agent/1.0")


class TestUploadFileWithRetry:
    def test_successful_upload(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_init_response = MagicMock()
        mock_init_response.status_code = 200
        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200
        mock_commit_response = MagicMock()
        mock_commit_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_upload_response):
                with patch("piccione.upload.on_zenodo.Progress"):
                    mock_post.side_effect = [mock_init_response, mock_commit_response]
                    upload_file_with_retry(
                        "https://zenodo.org/api", "rec123", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert mock_post.call_count == 2
        mock_post.assert_any_call(
            "https://zenodo.org/api/records/rec123/draft/files",
            headers={"Authorization": "Bearer token123", "User-Agent": "TestAgent/1.0", "Content-Type": "application/json"},
            json=[{"key": "test.txt"}],
        )

    def test_retry_on_timeout(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_init_response = MagicMock()
        mock_upload_response = MagicMock()
        mock_commit_response = MagicMock()

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
                with patch("piccione.upload.on_zenodo.Progress"):
                    with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                        mock_post.side_effect = [
                            requests.exceptions.Timeout(),
                            mock_init_response,
                            mock_commit_response,
                        ]
                        mock_put.return_value = mock_upload_response
                        upload_file_with_retry(
                            "https://zenodo.org/api", "rec123", str(test_file), "token123", "TestAgent/1.0"
                        )

        mock_sleep.assert_called_once_with(1)

    def test_retry_on_connection_error(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_init_response = MagicMock()
        mock_upload_response = MagicMock()
        mock_commit_response = MagicMock()

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
                with patch("piccione.upload.on_zenodo.Progress"):
                    with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                        mock_post.side_effect = [
                            requests.exceptions.ConnectionError(),
                            requests.exceptions.ConnectionError(),
                            mock_init_response,
                            mock_commit_response,
                        ]
                        mock_put.return_value = mock_upload_response
                        upload_file_with_retry(
                            "https://zenodo.org/api", "rec123", str(test_file), "token123", "TestAgent/1.0"
                        )

        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_http_error_raises_immediately(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response):
            with patch("piccione.upload.on_zenodo.Progress"):
                with pytest.raises(requests.exceptions.HTTPError):
                    upload_file_with_retry(
                        "https://zenodo.org/api", "rec123", str(test_file), "token123", "TestAgent/1.0"
                    )


def _base_config(tmp_path):
    test_file = tmp_path / "data.txt"
    test_file.write_text("data")
    config_file = tmp_path / "config.yaml"
    return config_file, test_file


class TestMain:
    def test_creates_draft_and_uploads(self, tmp_path):
        config_file, test_file = _base_config(tmp_path)
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: test_token
user_agent: TestAgent/1.0
title: Test Dataset
publication_date: "2024-01-15"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: John
      family_name: Doe
access:
  record: public
  files: public
files:
  - {test_file}
""")

        mock_draft = {"id": "abc123"}

        with patch("piccione.upload.on_zenodo.create_draft", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.upload_file_with_retry") as mock_upload:
                main(str(config_file))

        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        assert args[0] == "https://zenodo.org/api"
        assert args[1] == "test_token"
        assert args[2] == "TestAgent/1.0"
        mock_upload.assert_called_once_with("https://zenodo.org/api", "abc123", str(test_file), "test_token", "TestAgent/1.0")

    def test_new_version_flow(self, tmp_path):
        config_file, test_file = _base_config(tmp_path)
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: test_token
user_agent: TestAgent/1.0
record_id: existing-123
title: Test Dataset v2
publication_date: "2024-06-01"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: John
      family_name: Doe
access:
  record: public
  files: public
files:
  - {test_file}
""")

        mock_draft = {"id": "new-456"}

        with patch("piccione.upload.on_zenodo.create_new_version", return_value=mock_draft) as mock_version:
            with patch("piccione.upload.on_zenodo.delete_draft_files") as mock_delete:
                with patch("piccione.upload.on_zenodo.update_draft_metadata") as mock_update:
                    with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                        main(str(config_file))

        mock_version.assert_called_once_with("https://zenodo.org/api", "test_token", "existing-123", "TestAgent/1.0")
        mock_delete.assert_called_once_with("https://zenodo.org/api", "test_token", "new-456", "TestAgent/1.0")
        mock_update.assert_called_once()

    def test_uploads_all_files(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: token
user_agent: TestAgent/1.0
title: Test
publication_date: "2024-01-15"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: J
      family_name: D
access:
  record: public
  files: public
files:
  - {file1}
  - {file2}
""")

        with patch("piccione.upload.on_zenodo.create_draft", return_value={"id": "abc123"}):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry") as mock_upload:
                main(str(config_file))

        assert mock_upload.call_count == 2

    def test_publish_flag(self, tmp_path):
        config_file, test_file = _base_config(tmp_path)
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: token
user_agent: TestAgent/1.0
title: Test
publication_date: "2024-01-15"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: J
      family_name: D
access:
  record: public
  files: public
files:
  - {test_file}
""")

        mock_published = {"id": "published123", "links": {"self_html": "https://zenodo.org/records/published123"}}

        with patch("piccione.upload.on_zenodo.create_draft", return_value={"id": "abc123"}):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                with patch("piccione.upload.on_zenodo.publish_draft", return_value=mock_published) as mock_publish:
                    main(str(config_file), publish=True)

        mock_publish.assert_called_once_with("https://zenodo.org/api", "token", "abc123", "TestAgent/1.0")

    def test_community_submission(self, tmp_path):
        config_file, test_file = _base_config(tmp_path)
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: token
user_agent: TestAgent/1.0
community: my-community
title: Test
publication_date: "2024-01-15"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: J
      family_name: D
access:
  record: public
  files: public
files:
  - {test_file}
""")

        with patch("piccione.upload.on_zenodo.create_draft", return_value={"id": "abc123"}):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                with patch("piccione.upload.on_zenodo.submit_community_review") as mock_review:
                    main(str(config_file))

        mock_review.assert_called_once_with("https://zenodo.org/api", "token", "abc123", "my-community", "TestAgent/1.0")

    def test_community_skipped_on_sandbox(self, tmp_path):
        config_file, test_file = _base_config(tmp_path)
        config_file.write_text(f"""
zenodo_url: https://sandbox.zenodo.org/api
access_token: token
user_agent: TestAgent/1.0
community: my-community
title: Test
publication_date: "2024-01-15"
resource_type:
  id: dataset
creators:
  - person_or_org:
      type: personal
      given_name: J
      family_name: D
access:
  record: public
  files: public
files:
  - {test_file}
""")

        with patch("piccione.upload.on_zenodo.create_draft", return_value={"id": "abc123"}):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                with patch("piccione.upload.on_zenodo.submit_community_review") as mock_review:
                    main(str(config_file))

        mock_review.assert_not_called()
