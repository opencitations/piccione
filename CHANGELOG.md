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
