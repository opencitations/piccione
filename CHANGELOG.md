# [3.1.0](https://github.com/opencitations/piccione/compare/v3.0.1...v3.1.0) (2026-02-28)


### Features

* **zenodo:** add funding as passthrough field in InvenioRDM payload [release] ([970a065](https://github.com/opencitations/piccione/commit/970a065af7c0b562bc58a3913157cda864ff0191))

## [3.0.1](https://github.com/opencitations/piccione/compare/v3.0.0...v3.0.1) (2026-02-18)


### Bug Fixes

* **zenodo:** use correct InvenioRDM field names for languages and subjects [release] ([45dbfb0](https://github.com/opencitations/piccione/commit/45dbfb015e4a09df8fb9684fe5d7efd76a72a7d3))

# [3.0.0](https://github.com/opencitations/piccione/compare/v2.2.0...v3.0.0) (2026-02-18)


* feat(zenodo)!: complete InvenioRDM migration with versioning, community review, and config passthrough [release] ([aac11ee](https://github.com/opencitations/piccione/commit/aac11ee19c18d99c1eee6f1a640be6dbe3a2b47d))
* feat(zenodo)!: migrate from legacy API to InvenioRDM ([73bb09b](https://github.com/opencitations/piccione/commit/73bb09b484af77d4b3d4e5270633fa2aa825e196))


### BREAKING CHANGES

* config format now requires InvenioRDM-native structures
for creators, resource_type, access, and other metadata fields. The fields
upload_type, notes, method, and legacy creator name parsing are removed.
* Configuration format changed for InvenioRDM compatibility.
- `license` renamed to `rights` (now accepts `id` or `title`/`description`/`link`)
- `project_id` removed (versioning not supported)
- Removed fields: `contributors`, `access_right`, `embargo_date`, `access_conditions`,
  `doi`, `prereserve_doi`, `communities`, `grants`, `dates`, `references`, `subjects`,
  `thesis_*`, `journal_*`, `conference_*`, `imprint_*`, `partof_*`, `publication_type`,
  `image_type`
- `title` and `publication_date` now required

# [2.2.0](https://github.com/opencitations/piccione/compare/v2.1.0...v2.2.0) (2026-01-29)


### Features

* **zenodo:** add support for all Zenodo API metadata fields [release] ([220679f](https://github.com/opencitations/piccione/commit/220679f14a6258ba23592b540a6cda2f7217e020))

# [2.1.0](https://github.com/opencitations/piccione/compare/v2.0.0...v2.1.0) (2026-01-25)


### Features

* **upload:** add infinite retry with exponential backoff for figshare and zenodo ([57649b3](https://github.com/opencitations/piccione/commit/57649b39a855ebb32128d8fc2da50bf812714d55))
* **zenodo:** add metadata management, new deposition creation, and auto-publish ([8a8be0c](https://github.com/opencitations/piccione/commit/8a8be0c7c6966d5ddd73ed43f0b055686673fded))

# [2.0.0](https://github.com/opencitations/piccione/compare/v1.0.0...v2.0.0) (2025-12-11)


* feat(triplestore)!: make Redis caching optional with explicit configuration ([03de90c](https://github.com/opencitations/piccione/commit/03de90c85dede89579151636430fd4cb073a6ad0))


### Bug Fixes

* **ci:** regenerate uv.lock during release to prevent sync failures ([5e7623d](https://github.com/opencitations/piccione/commit/5e7623de3b958b1dac9dcc2ba2d33d327ddcd3a3))
* **deps:** relax redis dependency from >=7.1.0 to >=4.5.5 ([17b750f](https://github.com/opencitations/piccione/commit/17b750f91b7657f3f86e0871e83181818ff6c827))
* **docs:** correct repository URLs to opencitations/piccione ([11e9037](https://github.com/opencitations/piccione/commit/11e90378e15a0a4c9836d106ef135765dbdee2c1))


### BREAKING CHANGES

* The cache_manager parameter has been removed from
upload_sparql_updates(). Use redis_host, redis_port, redis_db instead.

[release]

# 1.0.0 (2025-12-11)


### Features

* add SharePoint download module ([f5fdb98](https://github.com/opencitations/piccione/commit/f5fdb98f236897cd21996c6e4a73f5da744261dc))
* add upload and download modules for external services ([c81f36c](https://github.com/opencitations/piccione/commit/c81f36cf349c088a71b4ee250ccae05a2bc5bdf5))
* initial project setup ([5915b8d](https://github.com/opencitations/piccione/commit/5915b8d6599aa8d32ca54f43c2f2fa1dd12eb68d))

# Changelog

All notable changes to this project will be documented in this file.
