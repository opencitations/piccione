# Piccione

[![Run tests](https://github.com/arcangelo7/piccione/actions/workflows/tests.yml/badge.svg)](https://github.com/arcangelo7/piccione/actions/workflows/tests.yml)
[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](https://opensource.org/licenses/ISC)

A Python toolkit for uploading and downloading data to external repositories and cloud services..

## Installation

```bash
pip install piccione
```

## Usage

```python
from piccione import example_function

result = example_function()
print(result)
```

## Documentation

Full documentation is available at: https://arcangelo7.github.io/piccione/

## Development

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
# Clone the repository
git clone https://github.com/arcangelo7/piccione.git
cd piccione

# Install dependencies
uv sync --all-extras --dev
```

### Running tests

```bash
uv run pytest tests/
```

### Building documentation locally

```bash
cd docs
npm install
npm run dev
```

## License

This project is licensed under the ISC License - see the [LICENSE.md](LICENSE.md) file for details.
