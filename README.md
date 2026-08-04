# Shelfmark News

A Newznab/SABnzbd API wrapper around [shelfmark](https://github.com/calibrain/shelfmark) for book searching and downloading from "direct download" sources. This allows applications like **Chaptarr** to search and download books from various sources that aren't in the standard usenet or torrenting options.

**Why?**: Shelfmark already has a battle-tested workflow for downloading this, but has [closed](https://github.com/calibrain/shelfmark/issues/397) requests for adding this feature in. 

DISCLOSURE: The base of this project was LLM-generated. I've done my best to review and maintain the code to ensure it doesn't become complete slop. I didn't/don't have the time to devote to writing this 100% from scratch!

## Features

- **Newznab API** - Compatible with Chaptarr and other \*arr applications for book searching
- **SABnzbd API** - Download management compatible with Chaptarr's download client integration
- **Environment Configuration** - Fully configurable via environment variables
- **Docker Ready** - Includes Dockerfile and docker-compose.yml

## Setup

Setup is fairly straightforward and done entirely through docker environment variables.

### Run using Docker

1. Download the docker compose file:
   ```bash
   wget https://raw.githubusercontent.com/pittman6/shelfmark-news/refs/heads/main/docker-compose.yml.example -O docker-compose.yml
   ```

2. Edit environment variables in docker-compose.yml as needed (See [Configuration](#configuration)).

2. Start the container:
   ```bash
   docker-compose up -d
   ```

### Adding as Download Client in Chaptarr

1. Go to **Settings → Download Clients → Add**
2. Select **SABnzbd**
3. Configure:
   - **Name**: Shelfmark
   - **Host**: `localhost`
   - **Port**: `8080`
   - **API Key**: Your configured `SERVER_API_KEY`
   - **Url Base**: `sabnzbd` (enable advanced settings at the bottom to see this)

### Adding as Indexer in Chaptarr

1. Go to **Settings → Indexers → Add**
2. Select **Newznab**
3. Configure:
   - **Name**: Shelfmark
   - **URL**: `http://localhost:8080`
   - **API Key**: Your configured `SERVER_API_KEY`
   - **Categories**: `7020` (Ebooks)
   - **Download Client**: Shelfmark (enable advanced settings at the bottom to see this)

## Configuration

All config is done through enviroment variables.

### Wrapper Environment Variables

These are the only env vars this wrapper defines:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8080` | Server port |
| `SERVER_API_KEY` | *(empty)* | API key for authentication |
| `SERVER_DEBUG` | `false` | Enable debug mode |

### Shelfmark Environment Variables

All other configuration — download directories, source settings, IRC, mirrors, rate limits — is handled by shelfmark.

At minimum, set these shelfmark variables for the wrapper to work:

| Variable | Description |
|----------|-------------|
| `INGEST_DIR` | Completed downloads directory (default: `/books`) |
| `LIBGEN_MIRROR_URLS` | Libgen URL |
| `ZLIB_MIRROR_URLS` | Zlib URL |
| `AA_MIRROR_URLS` | AA URL(s) |
| `WELIB_MIRROR_URLS` | Welib URL |


For the full list of shelfmark environment variables, see the [shelfmark environment variables docs](https://github.com/calibrain/shelfmark/blob/main/docs/environment-variables.md).

## Supported API Endpoints

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


## Development

### Install

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/calibrain/shelfmark-news.git
   cd shelfmark-news
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

3. Set environment variables and run:
   ```bash
   export SERVER_API_KEY=your-api-key
   export INGEST_DIR=/path/to/downloads
   shelfmark-news
   ```

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

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [shelfmark](https://github.com/calibrain/shelfmark) - The underlying book search and download library
- [Newznab](https://newznab.readthedocs.io/) - API specification
- [SABnzbd](https://sabnzbd.org/) - API specification
