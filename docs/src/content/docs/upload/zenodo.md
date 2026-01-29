---
title: Zenodo
description: Upload files to Zenodo depositions
---

## Prerequisites

- Zenodo account
- Access token (obtain from Account Settings > Applications > Personal access tokens)

## Configuration

Create a YAML file with the following fields:

### Required fields

| Field | Description |
|-------|-------------|
| `zenodo_url` | Full API URL: `https://zenodo.org/api` or `https://sandbox.zenodo.org/api` |
| `access_token` | Zenodo access token |
| `files` | List of file paths to upload |

### Optional fields

| Field | Description |
|-------|-------------|
| `user_agent` | User-Agent string for API requests (e.g., `piccione/2.0.0`). See note below |
| `project_id` | Existing deposition ID to create new version from |
| `title` | Deposition title |
| `upload_type` | `publication`, `poster`, `presentation`, `dataset`, `image`, `video`, `software`, `lesson`, `physicalobject`, `other` |
| `publication_type` | Required when `upload_type` is `publication`. Values: `annotationcollection`, `book`, `section`, `conferencepaper`, `datamanagementplan`, `article`, `patent`, `preprint`, `deliverable`, `milestone`, `proposal`, `report`, `softwaredocumentation`, `taxonomictreatment`, `technicalnote`, `thesis`, `workingpaper`, `other` |
| `image_type` | Required when `upload_type` is `image`. Values: `figure`, `plot`, `drawing`, `diagram`, `photo`, `other` |
| `creators` | List of objects: `name` (required, format: "Family, Given"), `affiliation`, `orcid`, `gnd` |
| `contributors` | List of objects: `name` (required), `type` (required), `affiliation`, `orcid`, `gnd`. Type values: `ContactPerson`, `DataCollector`, `DataCurator`, `DataManager`, `Distributor`, `Editor`, `HostingInstitution`, `Producer`, `ProjectLeader`, `ProjectManager`, `ProjectMember`, `RegistrationAgency`, `RegistrationAuthority`, `RelatedPerson`, `Researcher`, `ResearchGroup`, `RightsHolder`, `Supervisor`, `Sponsor`, `WorkPackageLeader`, `Other` |
| `keywords` | List of keywords |
| `license` | License identifier via `/api/licenses`. Default: `cc-zero` (datasets), `cc-by` (others) |
| `access_right` | `open` (default), `embargoed`, `restricted`, `closed` |
| `embargo_date` | ISO date, required when `access_right` is `embargoed` |
| `access_conditions` | HTML text, required when `access_right` is `restricted` |
| `description` | Plain text (converted to HTML with paragraph support) |
| `notes` | Plain text (converted to HTML) |
| `method` | Methodology, plain text (converted to HTML) |
| `publication_date` | ISO date (YYYY-MM-DD) |
| `doi` | Digital Object Identifier |
| `prereserve_doi` | Boolean, pre-reserve a DOI |
| `related_identifiers` | List of objects: `identifier`, `relation`, `resource_type`. Relation values: `isCitedBy`, `cites`, `isSupplementTo`, `isSupplementedBy`, `isContinuedBy`, `continues`, `isDescribedBy`, `describes`, `hasMetadata`, `isMetadataFor`, `isNewVersionOf`, `isPreviousVersionOf`, `isPartOf`, `hasPart`, `isReferencedBy`, `references`, `isDocumentedBy`, `documents`, `isCompiledBy`, `compiles`, `isVariantFormOf`, `isOriginalFormOf`, `isIdenticalTo`, `isAlternateIdentifier`, `isReviewedBy`, `reviews`, `isDerivedFrom`, `isSourceOf`, `requires`, `isRequiredBy`, `isObsoletedBy`, `obsoletes` |
| `references` | List of reference strings |
| `communities` | List of objects with `identifier` (community ID) |
| `grants` | List of objects with `id` (grant ID from OpenAIRE) |
| `subjects` | List of objects: `term`, `identifier`, `scheme` |
| `version` | Version string |
| `language` | ISO 639-2 or 639-3 language code |
| `locations` | List of objects: `place` (required), `lat`, `lon`, `description` |
| `dates` | List of objects: `start` and/or `end` (ISO dates), `type` (`Collected`, `Valid`, `Withdrawn`), `description` |
| `thesis_supervisors` | List of objects with same structure as `creators` |
| `thesis_university` | University name |
| `journal_title` | Journal title |
| `journal_volume` | Journal volume |
| `journal_issue` | Journal issue |
| `journal_pages` | Journal pages |
| `conference_title` | Conference title |
| `conference_acronym` | Conference acronym |
| `conference_dates` | Conference dates |
| `conference_place` | Conference place |
| `conference_url` | Conference URL |
| `conference_session` | Conference session |
| `conference_session_part` | Conference session part |
| `imprint_publisher` | Publisher |
| `imprint_isbn` | ISBN |
| `imprint_place` | Publication place |
| `partof_title` | Title of larger work |
| `partof_pages` | Pages in larger work |

**Note on User-Agent:** Specifying a `user_agent` is strongly recommended. Without a proper User-Agent header, Zenodo is more likely to return 403 Forbidden errors or block uploads, especially during periods of high server load.

For complete field documentation, see the [Zenodo REST API documentation](https://developers.zenodo.org/).

Example:

```yaml
zenodo_url: https://zenodo.org/api
access_token: <YOUR_ZENODO_TOKEN>
user_agent: piccione/2.0.0

# Optional: omit to create new deposition
# project_id: 12345678

title: My Dataset
upload_type: dataset
creators:
  - name: Doe, John
    affiliation: University
    orcid: 0000-0000-0000-0000
keywords:
  - data
  - research
license: cc-by-4.0
description: |
  Dataset description here.

  Multiple paragraphs supported.

files:
  - /path/to/dataset.zip
  - /path/to/readme.txt
```

See [examples/zenodo_upload.yaml](https://github.com/opencitations/piccione/blob/main/examples/zenodo_upload.yaml) for a complete example.

## Usage

```bash
# Upload and create draft for review
python -m piccione.upload.on_zenodo config.yaml

# Upload and publish automatically
python -m piccione.upload.on_zenodo config.yaml --publish
```

## Features

- Create new depositions or new versions of existing ones
- Automatic metadata update from configuration
- Automatic retry with exponential backoff for network errors (unlimited attempts, max 60s delay)
- Rich progress bar with transfer speed and ETA
- Sandbox support for testing
- Optional auto-publish with `--publish` flag
