"""Newznab API implementation for book searching.

The Newznab API is commonly used by applications like Readarr to search
for books. This implements the subset of the API needed for book search.

Reference: https://newznab.readthedocs.io/en/latest/misc/api/
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from shelfmark_news.config import SERVER_API_KEY


router = APIRouter(tags=["newznab"])

ATOM_NS = "http://www.w3.org/2005/Atom"
NEWZNAB_NS = "http://www.newznab.com/DTD/2010/feeds/attributes/"

ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("newznab", NEWZNAB_NS)


# Newznab category IDs for books
CATEGORY_BOOKS = 7000
CATEGORY_EBOOK = 7020

CATEGORY_NAMES = {
    CATEGORY_BOOKS: "Books",
    CATEGORY_EBOOK: "Books > Ebook",
}


def _get_base_url(request: Request) -> str:
    """Get the base URL from the request for building absolute URLs."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", None) or request.headers.get(
        "host", "localhost"
    )
    return f"{scheme}://{host}"


def _create_xml_response(root: ET.Element) -> Response:
    """Create an XML response from an ElementTree element."""
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(content=xml_str, media_type="application/xml")


def _create_error_response(code: int, description: str) -> Response:
    """Create a Newznab error response."""
    root = ET.Element("error", code=str(code), description=description)
    return _create_xml_response(root)


def _generate_guid(source: str, source_id: str) -> str:
    """Generate a unique GUID for a release."""
    return hashlib.md5(f"{source}:{source_id}".encode()).hexdigest()


def _parse_size_to_bytes(size_str: Optional[str]) -> int:
    """Parse human-readable size to bytes."""
    if not size_str:
        return 0

    size_str = size_str.strip().upper()
    multipliers = {
        "TB": 1024**4,
        "GB": 1024**3,
        "MB": 1024**2,
        "KB": 1024,
        "B": 1,
    }

    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                num = float(size_str[: -len(suffix)].strip())
                return int(num * mult)
            except ValueError:
                return 0

    try:
        return int(float(size_str))
    except ValueError:
        return 0


@router.get("/api")
async def newznab_api(
    request: Request,
    t: str = Query(..., description="API function (caps, search, book)"),
    apikey: str = Query("", description="API key"),
    q: Optional[str] = Query(None, description="Search query"),
    author: Optional[str] = Query(None, description="Author name"),
    title: Optional[str] = Query(None, description="Book title"),
    cat: Optional[str] = Query(None, description="Category IDs (comma-separated)"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Result offset"),
):
    """Newznab API endpoint.

    Supports the following functions:
    - caps: Return API capabilities
    - search: General search
    - book: Book-specific search
    """
    if t == "caps":
        return _handle_caps(request)

    if SERVER_API_KEY and apikey != SERVER_API_KEY:
        return _create_error_response(100, "Incorrect user credentials")

    if t == "search":
        return await _handle_search(request, q, cat, limit, offset, apikey)
    elif t == "book":
        return await _handle_book_search(
            request, q, author, title, cat, limit, offset, apikey
        )
    else:
        return _create_error_response(202, f"No such function ({t})")


def _handle_caps(request: Request) -> Response:
    """Handle caps request - return API capabilities."""
    root = ET.Element("caps")

    ET.SubElement(
        root,
        "server",
        version="1.0",
        title="Shelfmark News",
        strapline="Book search via Newznab API",
        email="",
    )

    ET.SubElement(root, "limits", max="100", default="100")

    ET.SubElement(root, "registration", available="no", open="no")

    searching = ET.SubElement(root, "searching")
    ET.SubElement(searching, "search", available="yes", supportedParams="q")
    ET.SubElement(
        searching, "book-search", available="yes", supportedParams="q,author,title"
    )
    categories = ET.SubElement(root, "categories")

    books_cat = ET.SubElement(
        categories, "category", id=str(CATEGORY_BOOKS), name="Books"
    )
    ET.SubElement(books_cat, "subcat", id=str(CATEGORY_EBOOK), name="Ebook")

    return _create_xml_response(root)


async def _handle_search(
    request: Request,
    query: Optional[str],
    cat: Optional[str],
    limit: int,
    offset: int,
    apikey: str = "",
) -> Response:
    """Handle general search request."""
    # If no query, return empty results (this is a test request)
    if not query:
        return _create_empty_response(request, apikey)

    return await _perform_search(
        request, query, None, None, limit, offset, apikey
    )


def _create_empty_response(request: Request, apikey: str = "") -> Response:
    """Create a test response with dummy results (for Readarr connection test)."""
    root = ET.Element("rss", version="2.0")
    channel = _build_channel(root, request, "0", "1")
    _add_response_header(channel, "0", "1")

    download_url = f"{_get_base_url(request)}/api/v1/download/test"
    if apikey:
        download_url += f"?apikey={apikey}"

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = "Test Book - Test Author"
    ET.SubElement(item, "guid", isPermaLink="true").text = download_url
    ET.SubElement(item, "link").text = download_url
    ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )
    ET.SubElement(item, "category").text = CATEGORY_NAMES[CATEGORY_EBOOK]
    ET.SubElement(item, "size").text = "1000000"
    ET.SubElement(item, "description").text = "Test Book - Test Author"
    ET.SubElement(
        item,
        "enclosure",
        url=download_url,
        length="1000000",
        type="application/x-nzb",
    )
    _add_attr(item, "category", str(CATEGORY_BOOKS))
    _add_attr(item, "category", str(CATEGORY_EBOOK))

    return _create_xml_response(root)


async def _handle_book_search(
    request: Request,
    query: Optional[str],
    author: Optional[str],
    title: Optional[str],
    cat: Optional[str],
    limit: int,
    offset: int,
    apikey: str = "",
) -> Response:
    """Handle book-specific search request."""
    # Build search query from components
    search_parts = []
    if query:
        search_parts.append(query)
    if title:
        search_parts.append(title)
    if author:
        search_parts.append(author)

    # If no search parameters, return empty results (this is a test request)
    if not search_parts:
        return _create_empty_response(request, apikey)

    search_query = " ".join(search_parts)

    return await _perform_search(
        request,
        search_query,
        author,
        title,
        limit,
        offset,
        apikey,
    )


def _build_channel(
    root: ET.Element, request: Request, offset: str, total: str
) -> ET.Element:
    """Build the standard channel element for RSS responses."""
    base_url = _get_base_url(request)
    channel = ET.SubElement(root, "channel")

    ET.SubElement(
        channel,
        "{http://www.w3.org/2005/Atom}link",
        href=str(request.url),
        rel="self",
        type="application/rss+xml",
    )
    ET.SubElement(channel, "title").text = "Shelfmark News"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Book Search Results"
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "webMaster").text = ""
    ET.SubElement(channel, "category").text = ""

    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = f"{base_url}/favicon.ico"
    ET.SubElement(image, "title").text = "Shelfmark News"
    ET.SubElement(image, "link").text = base_url
    ET.SubElement(image, "description").text = "Shelfmark"

    return channel


def _add_response_header(channel: ET.Element, offset: str, total: str) -> ET.Element:
    """Add the newznab:response element to the channel."""
    return ET.SubElement(
        channel,
        f"{{{NEWZNAB_NS}}}response",
        offset=offset,
        total=total,
    )


def _add_attr(item: ET.Element, name: str, value: str) -> ET.Element:
    """Add a newznab:attr element to an item."""
    return ET.SubElement(
        item,
        f"{{{NEWZNAB_NS}}}attr",
        name=name,
        value=value,
    )


def _add_item(
    channel: ET.Element,
    record,
    base_url: str,
    apikey: str = "",
) -> None:
    """Add a single item element to the channel."""
    cat_id = CATEGORY_EBOOK
    parent_cat_id = str(CATEGORY_BOOKS)

    item = ET.SubElement(channel, "item")

    item_title = record.title
    if record.author:
        item_title = f"{record.title} - {record.author}"
    if record.format:
        item_title = f"{item_title} [{record.format}]"
    ET.SubElement(item, "title").text = item_title
    ET.SubElement(item, "description").text = item_title

    guid = _generate_guid("direct_download", record.id)
    download_url = f"{base_url}/api/v1/download/{record.id}"
    if apikey:
        download_url += f"?apikey={apikey}"
    ET.SubElement(item, "guid", isPermaLink="true").text = download_url

    ET.SubElement(item, "link").text = download_url
    ET.SubElement(item, "comments").text = download_url

    ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )

    ET.SubElement(item, "category").text = CATEGORY_NAMES[cat_id]

    size_bytes = _parse_size_to_bytes(record.size)
    ET.SubElement(item, "size").text = str(size_bytes)

    ET.SubElement(
        item,
        "enclosure",
        url=download_url,
        length=str(size_bytes),
        type="application/x-nzb",
    )

    _add_attr(item, "category", parent_cat_id)
    _add_attr(item, "category", str(cat_id))
    _add_attr(item, "guid", guid)

    if record.author:
        _add_attr(item, "author", record.author)

    if record.format:
        _add_attr(item, "format", record.format.lower())

    if record.language:
        _add_attr(item, "language", record.language)

    if size_bytes:
        _add_attr(item, "size", str(size_bytes))


async def _perform_search(
    request: Request,
    query: str,
    author: Optional[str],
    title: Optional[str],
    limit: int,
    offset: int,
    apikey: str = "",
) -> Response:
    """Perform the actual search using shelfmark."""
    from shelfmark.release_sources.direct_download import (
        search_books,
        SearchUnavailableError,
    )
    from shelfmark.core.models import SearchFilters

    try:
        results = search_books(query, SearchFilters())

        total = len(results)
        results = results[offset : offset + limit]

        base_url = _get_base_url(request)

        root = ET.Element("rss", version="2.0")

        channel = _build_channel(root, request, str(offset), str(total))
        _add_response_header(channel, str(offset), str(total))

        for record in results:
            _add_item(channel, record, base_url, apikey)

        return _create_xml_response(root)

    except SearchUnavailableError as e:
        return _create_error_response(900, f"Search unavailable: {e}")
    except Exception as e:
        return _create_error_response(900, f"Search error: {e}")
