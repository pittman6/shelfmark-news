# Shelfmark Wrapper

A Newznab/SABnzbd API wrapper around [shelfmark](https://github.com/calibrain/shelfmark) for book searching and downloading. This allows applications like **Readarr** to search and download books from various sources including Anna's Archive, Libgen, Z-Library, and IRC channels.

## Features

- **Newznab API** - Compatible with Readarr and other \*arr applications for book searching
- **SABnzbd API** - Download management compatible with Readarr's download client integration
- **Multiple Sources** - Anna's Archive, Libgen, Z-Library, and IRC
- **Environment Configuration** - Fully configurable via environment variables
- **Docker Ready** - Includes Dockerfile and docker-compose.yml

## Project Structure

```
shelfmark-wrapper/
├── src/shelfmark_wrapper/
│   ├── __init__.py           # Package init
│   ├── config.py             # Environment-based configuration system
│   ├── main.py               # FastAPI application entry point
│   └── api/
│       ├── __init__.py
│       ├── newznab.py        # Newznab API for searching
│       └── sabnzbd.py        # SABnzbd API for downloading
├── shelfmark/                # Submodule (book search/download library)
├── pyproject.toml            # Project dependencies
├── Dockerfile                # Docker image
├── docker-compose.yml        # Docker Compose setup
└── .gitignore
```

## Quick Start

### Using Docker (Recommended)

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/calibrain/shelfmark-wrapper.git
   cd shelfmark-wrapper
   ```

2. Start the container:
   ```bash
   docker-compose up -d
   ```

### Direct Installation

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/calibrain/shelfmark-wrapper.git
   cd shelfmark-wrapper
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

3. Set environment variables and run:
   ```bash
   export SERVER_API_KEY=your-api-key
   export INGEST_DIR=/path/to/downloads
   shelfmark-wrapper
   ```

## API Endpoints

### Newznab API (`/api`)

| Endpoint | Description |
|----------|-------------|
| `/api?t=caps` | Returns API capabilities |
| `/api?t=search&q=...&apikey=...` | General book search |
| `/api?t=book&author=...&title=...&apikey=...` | Book-specific search |

**Supported Parameters:**
- `q` - Search query
- `author` - Author name filter
- `title` - Book title filter
- `cat` - Category ID (7020=ebook)
- `limit` - Maximum results (default: 100)
- `offset` - Result offset for pagination

### SABnzbd API (`/sabnzbd/api`)

| Mode | Description |
|------|-------------|
| `version` | Returns API version |
| `auth` | Validates API key |
| `get_config` | Returns configuration |
| `queue` | Returns current download queue |
| `history` | Returns download history |
| `addurl&name=...` | Adds a download by ID |
| `delete&nzo_ids=...` | Removes from queue |
| `pause&nzo_ids=...` | Pauses downloads |
| `resume&nzo_ids=...` | Resumes downloads |
| `retry&nzo_ids=...` | Retries failed downloads |
| `fullstatus` | Returns full status information |

### Utility Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | API information |
| `/health` | Health check |
| `/api/v1/download/{id}` | Direct download by ID |

## Configuration

### Wrapper Environment Variables

These are the only env vars this wrapper defines:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8080` | Server port |
| `SERVER_API_KEY` | *(empty)* | API key for authentication |
| `SERVER_DEBUG` | `false` | Enable debug mode |

### Shelfmark Environment Variables

All other configuration — download directories, source settings, IRC, mirrors, rate limits — is handled by shelfmark. The wrapper imports `INGEST_DIR` and `TMP_DIR` from shelfmark's config and sets a default `CONFIG_DIR` if unset.

At minimum, set these shelfmark variables for the wrapper to work:

| Variable | Description |
|----------|-------------|
| `INGEST_DIR` | Completed downloads directory (default: `/books`) |
| `LIBGEN_MIRROR_URLS` | Libgen URL |
| `ZLIB_MIRROR_URLS` | Zlib URL |
| `AA_MIRROR_URLS` | AA URL(s) |
| `WELIB_MIRROR_URLS` | Welib URL |


For the full list of shelfmark environment variables, see the [shelfmark environment variables docs](https://github.com/calibrain/shelfmark/blob/main/docs/environment-variables.md).

## Readarr Integration

### Adding as Indexer

1. Go to **Settings → Indexers → Add**
2. Select **Newznab**
3. Configure:
   - **Name**: Shelfmark
   - **URL**: `http://localhost:8080`
   - **API Key**: Your configured `SERVER_API_KEY`
   - **Categories**: `7020` (Ebooks)

### Adding as Download Client

1. Go to **Settings → Download Clients → Add**
2. Select **SABnzbd**
3. Configure:
   - **Name**: Shelfmark
   - **Host**: `localhost`
   - **Port**: `8080`
   - **API Key**: Your configured `SERVER_API_KEY`
   - **Category**: `books`

## Sources

### Supported Sources

| Source | Type | Description |
|--------|------|-------------|
| **Anna's Archive** | Direct Download | Primary search source, cascades through multiple mirrors |
| **Libgen** | Direct Download | Library Genesis mirrors |
| **Z-Library** | Direct Download | Z-Library mirrors |
| **IRC** | DCC | IRC channel book sharing (requires separate IRC setup) |

### Source Priority

Downloads cascade through sources in priority order:
1. Anna's Archive Fast (requires donator key)
2. Libgen
3. Anna's Archive Slow (no waitlist)
4. Anna's Archive Slow (with waitlist)
5. Z-Library

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Project Dependencies

- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Settings management
- **shelfmark** - Book search/download library (submodule)

## Docker Volumes

| Path | Description |
|------|-------------|
| `$INGEST_DIR` | Completed downloads |
| `$TMP_DIR` | Temporary download staging |
| `$CONFIG_DIR` | Configuration files |

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [shelfmark](https://github.com/calibrain/shelfmark) - The underlying book search and download library
- [Readarr](https://readarr.com/) - Book collection manager
- [Newznab](https://newznab.readthedocs.io/) - API specification
- [SABnzbd](https://sabnzbd.org/) - API specification
