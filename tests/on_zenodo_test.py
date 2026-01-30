from unittest.mock import MagicMock, patch

import pytest
import requests

from piccione.upload.on_zenodo import (
    ProgressFileWrapper,
    _map_relation_type,
    build_inveniordm_metadata,
    linkify_urls,
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


class TestLinkifyUrls:
    def test_linkify_single_url(self):
        text = "Visit https://example.com for more info"
        result = linkify_urls(text)
        assert result == 'Visit <a href="https://example.com">https://example.com</a> for more info'

    def test_linkify_multiple_urls(self):
        text = "See https://a.com and http://b.com"
        result = linkify_urls(text)
        assert result == 'See <a href="https://a.com">https://a.com</a> and <a href="http://b.com">http://b.com</a>'

    def test_no_urls(self):
        text = "No URLs here"
        result = linkify_urls(text)
        assert result == "No URLs here"


class TestTextToHtml:
    def test_single_paragraph(self):
        text = "Single paragraph"
        result = text_to_html(text)
        assert result == "<p>Single paragraph</p>"

    def test_multiple_paragraphs(self):
        text = "First paragraph\n\nSecond paragraph"
        result = text_to_html(text)
        assert result == "<p>First paragraph</p><p>Second paragraph</p>"

    def test_paragraph_with_line_breaks(self):
        text = "Line one\nLine two"
        result = text_to_html(text)
        assert result == "<p>Line one<br>Line two</p>"

    def test_bullet_list(self):
        text = "- Item one\n- Item two"
        result = text_to_html(text)
        assert result == "<ul><li>Item one</li><li>Item two</li></ul>"

    def test_paragraph_then_list(self):
        text = "Introduction\n\n- Item one\n- Item two"
        result = text_to_html(text)
        assert result == "<p>Introduction</p><ul><li>Item one</li><li>Item two</li></ul>"

    def test_urls_in_paragraph(self):
        text = "Visit https://example.com"
        result = text_to_html(text)
        assert result == '<p>Visit <a href="https://example.com">https://example.com</a></p>'


class TestMapRelationType:
    def test_known_relation(self):
        assert _map_relation_type("isDocumentedBy") == "isdocumentedby"
        assert _map_relation_type("isPartOf") == "ispartof"
        assert _map_relation_type("references") == "references"

    def test_unknown_relation_lowercased(self):
        assert _map_relation_type("CustomRelation") == "customrelation"


class TestBuildInvenioRdmMetadata:
    def test_minimal_config(self):
        config = {
            "title": "Test Title",
            "publication_date": "2024-01-15",
        }
        result = build_inveniordm_metadata(config)
        assert result == {
            "title": "Test Title",
            "publication_date": "2024-01-15",
            "resource_type": {"id": "dataset"},
            "publisher": "Zenodo",
        }

    def test_with_description(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "description": "Test description",
        }
        result = build_inveniordm_metadata(config)
        assert result["description"] == "<p>Test description</p>"

    def test_with_creators_comma_format(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "creators": [
                {"name": "Doe, John", "orcid": "0000-0001-2345-6789", "affiliation": "University"}
            ],
        }
        result = build_inveniordm_metadata(config)
        assert result["creators"] == [
            {
                "person_or_org": {
                    "type": "personal",
                    "given_name": "John",
                    "family_name": "Doe",
                    "identifiers": [{"scheme": "orcid", "identifier": "0000-0001-2345-6789"}],
                },
                "affiliations": [{"name": "University"}],
            }
        ]

    def test_with_creators_space_format(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "creators": [{"name": "John Doe"}],
        }
        result = build_inveniordm_metadata(config)
        assert result["creators"][0]["person_or_org"]["given_name"] == "John"
        assert result["creators"][0]["person_or_org"]["family_name"] == "Doe"

    def test_with_keywords(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "keywords": ["data", "research"],
        }
        result = build_inveniordm_metadata(config)
        assert result["subjects"] == [{"subject": "data"}, {"subject": "research"}]

    def test_with_rights(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "rights": [{"id": "cc-by-4.0"}],
        }
        result = build_inveniordm_metadata(config)
        assert result["rights"] == [{"id": "cc-by-4.0"}]

    def test_with_related_identifiers(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "related_identifiers": [
                {"identifier": "10.1234/example", "relation": "isPartOf"},
                {"identifier": "https://example.com", "relation": "isDocumentedBy"},
            ],
        }
        result = build_inveniordm_metadata(config)
        assert result["related_identifiers"] == [
            {"identifier": "10.1234/example", "relation_type": {"id": "ispartof"}, "scheme": "doi"},
            {"identifier": "https://example.com", "relation_type": {"id": "isdocumentedby"}, "scheme": "url"},
        ]

    def test_with_version(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "version": "1.0.0",
        }
        result = build_inveniordm_metadata(config)
        assert result["version"] == "1.0.0"

    def test_with_language(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "language": "eng",
        }
        result = build_inveniordm_metadata(config)
        assert result["languages"] == [{"id": "eng"}]

    def test_with_notes(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "notes": "Some notes",
        }
        result = build_inveniordm_metadata(config)
        assert result["additional_descriptions"] == [
            {"description": "<p>Some notes</p>", "type": {"id": "notes"}}
        ]

    def test_with_method(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "method": "Methodology description",
        }
        result = build_inveniordm_metadata(config)
        assert result["additional_descriptions"] == [
            {"description": "<p>Methodology description</p>", "type": {"id": "methods"}}
        ]

    def test_with_locations(self):
        config = {
            "title": "Test",
            "publication_date": "2024-01-15",
            "locations": [
                {"lat": 44.49, "lon": 11.34, "place": "Bologna", "description": "Site A"}
            ],
        }
        result = build_inveniordm_metadata(config)
        assert result["locations"] == {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [11.34, 44.49]},
                    "place": "Bologna",
                    "description": "Site A",
                }
            ]
        }


class TestPublishDraft:
    def test_successful_publish(self):
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"id": "abc123"}

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response) as mock_post:
            result = publish_draft("https://zenodo.org", "token", "Agent/1.0", "draft-id")

        assert result == {"id": "abc123"}
        mock_post.assert_called_once_with(
            "https://zenodo.org/api/records/draft-id/draft/actions/publish",
            headers={"Authorization": "Bearer token", "User-Agent": "Agent/1.0", "Content-Type": "application/json"},
            timeout=30,
        )

    def test_publish_error_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                publish_draft("https://zenodo.org", "token", "Agent/1.0", "draft-id")


class TestUploadFileWithRetry:
    def test_successful_upload(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_register_response = MagicMock()
        mock_register_response.status_code = 200
        mock_register_response.json.return_value = {
            "entries": [
                {
                    "links": {
                        "content": "https://zenodo.org/content/123",
                        "commit": "https://zenodo.org/commit/123",
                    }
                }
            ]
        }

        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200

        mock_commit_response = MagicMock()
        mock_commit_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put", return_value=mock_upload_response):
                with patch("piccione.upload.on_zenodo.Progress"):
                    mock_post.side_effect = [mock_register_response, mock_commit_response]
                    result = upload_file_with_retry(
                        "https://zenodo.org/files", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert result == mock_commit_response
        assert mock_post.call_count == 2

    def test_retry_on_timeout(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_register_response = MagicMock()
        mock_register_response.status_code = 200
        mock_register_response.json.return_value = {
            "entries": [{"links": {"content": "https://zenodo.org/c", "commit": "https://zenodo.org/m"}}]
        }
        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200
        mock_commit_response = MagicMock()
        mock_commit_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
                with patch("piccione.upload.on_zenodo.Progress"):
                    with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                        mock_post.side_effect = [
                            requests.exceptions.Timeout(),
                            mock_register_response,
                            mock_commit_response,
                        ]
                        mock_put.return_value = mock_upload_response
                        result = upload_file_with_retry(
                            "https://zenodo.org/files", str(test_file), "token123", "TestAgent/1.0"
                        )

        assert result == mock_commit_response
        mock_sleep.assert_called_once_with(1)

    def test_retry_on_connection_error(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_register_response = MagicMock()
        mock_register_response.status_code = 200
        mock_register_response.json.return_value = {
            "entries": [{"links": {"content": "https://zenodo.org/c", "commit": "https://zenodo.org/m"}}]
        }
        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200
        mock_commit_response = MagicMock()
        mock_commit_response.status_code = 200

        with patch("piccione.upload.on_zenodo.requests.post") as mock_post:
            with patch("piccione.upload.on_zenodo.requests.put") as mock_put:
                with patch("piccione.upload.on_zenodo.Progress"):
                    with patch("piccione.upload.on_zenodo.time.sleep") as mock_sleep:
                        mock_post.side_effect = [
                            requests.exceptions.ConnectionError(),
                            requests.exceptions.ConnectionError(),
                            mock_register_response,
                            mock_commit_response,
                        ]
                        mock_put.return_value = mock_upload_response
                        result = upload_file_with_retry(
                            "https://zenodo.org/files", str(test_file), "token123", "TestAgent/1.0"
                        )

        assert result == mock_commit_response
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_http_error_raises_immediately(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")

        with patch("piccione.upload.on_zenodo.requests.post", return_value=mock_response) as mock_post:
            with patch("piccione.upload.on_zenodo.Progress"):
                with pytest.raises(requests.exceptions.HTTPError):
                    upload_file_with_retry(
                        "https://zenodo.org/files", str(test_file), "token123", "TestAgent/1.0"
                    )

        assert mock_post.call_count == 1


class TestMain:
    def test_creates_draft_and_uploads(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org
access_token: test_token
user_agent: TestAgent/1.0
title: Test Dataset
publication_date: "2024-01-15"
files:
  - {test_file}
""")

        mock_draft = {
            "id": "abc123",
            "links": {"files": "https://zenodo.org/api/records/abc123/draft/files"},
        }

        with patch("piccione.upload.on_zenodo.create_new_draft", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.upload_file_with_retry") as mock_upload:
                result = main(str(config_file))

        assert result == mock_draft
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "https://zenodo.org"
        assert call_args[0][1] == "test_token"
        assert call_args[0][2] == "TestAgent/1.0"
        mock_upload.assert_called_once()

    def test_sandbox_url_handling(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://sandbox.zenodo.org
access_token: test_token
user_agent: TestAgent/1.0
title: Test Dataset
publication_date: "2024-01-15"
files:
  - {test_file}
""")

        mock_draft = {
            "id": "abc123",
            "links": {"files": "https://sandbox.zenodo.org/api/records/abc123/draft/files"},
        }

        with patch("piccione.upload.on_zenodo.create_new_draft", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                main(str(config_file))

        call_args = mock_create.call_args
        assert call_args[0][0] == "https://sandbox.zenodo.org"

    def test_url_with_api_suffix(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org/api
access_token: test_token
user_agent: TestAgent/1.0
title: Test Dataset
publication_date: "2024-01-15"
files:
  - {test_file}
""")

        mock_draft = {
            "id": "abc123",
            "links": {"files": "https://zenodo.org/api/records/abc123/draft/files"},
        }

        with patch("piccione.upload.on_zenodo.create_new_draft", return_value=mock_draft) as mock_create:
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                main(str(config_file))

        call_args = mock_create.call_args
        assert call_args[0][0] == "https://zenodo.org"

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
title: Test
publication_date: "2024-01-15"
files:
  - {file1}
  - {file2}
""")

        mock_draft = {
            "id": "abc123",
            "links": {"files": "https://zenodo.org/api/records/abc123/draft/files"},
        }

        with patch("piccione.upload.on_zenodo.create_new_draft", return_value=mock_draft):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry") as mock_upload:
                main(str(config_file))

        assert mock_upload.call_count == 2

    def test_publish_flag(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        test_file = tmp_path / "data.txt"
        test_file.write_text("data")
        config_file.write_text(f"""
zenodo_url: https://zenodo.org
access_token: token
user_agent: TestAgent/1.0
title: Test
publication_date: "2024-01-15"
files:
  - {test_file}
""")

        mock_draft = {
            "id": "abc123",
            "links": {"files": "https://zenodo.org/api/records/abc123/draft/files"},
        }
        mock_published = {"id": "published123"}

        with patch("piccione.upload.on_zenodo.create_new_draft", return_value=mock_draft):
            with patch("piccione.upload.on_zenodo.upload_file_with_retry"):
                with patch("piccione.upload.on_zenodo.publish_draft", return_value=mock_published) as mock_publish:
                    result = main(str(config_file), publish=True)

        assert result == mock_published
        mock_publish.assert_called_once_with("https://zenodo.org", "token", "TestAgent/1.0", "abc123")
