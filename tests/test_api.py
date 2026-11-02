"""Tests for the Newznab and SABnzbd API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    """Create a test client with environment configured."""
    import os

    # Set test environment variables before importing
    os.environ["DOWNLOAD_OUTPUT_DIR"] = "/tmp/shelfmark-test/downloads"
    os.environ["DOWNLOAD_TMP_DIR"] = "/tmp/shelfmark-test/tmp"
    os.environ["DOWNLOAD_LOG_DIR"] = "/tmp/shelfmark-test/logs"
    os.environ["LOG_ROOT"] = "/tmp/shelfmark-test/logs"
    from pathlib import Path

    Path("/tmp/shelfmark-test/logs").mkdir(parents=True, exist_ok=True)
    Path("/tmp/shelfmark-test/downloads").mkdir(parents=True, exist_ok=True)
    Path("/tmp/shelfmark-test/tmp").mkdir(parents=True, exist_ok=True)
    os.environ["SERVER_API_KEY"] = "test-api-key"

    from shelfmark_news.main import app

    return TestClient(app)


class TestNewznabAPI:
    """Tests for the Newznab API."""

    def test_caps_endpoint(self, client):
        """Test that caps endpoint returns valid XML."""
        response = client.get("/api?t=caps")
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert b"<caps>" in response.content
        assert b"book-search" in response.content
        assert b"7020" in response.content  # Ebook category

    def test_caps_no_auth_required(self, client):
        """Test that caps endpoint doesn't require API key."""
        response = client.get("/api?t=caps")
        assert response.status_code == 200

    def test_search_without_query_returns_test_results(self, client):
        """Test that search without query returns test results (for Readarr)."""
        response = client.get("/api?t=search&apikey=test-api-key")
        assert response.status_code == 200
        assert b"<rss" in response.content
        assert b"Test Book" in response.content

    def test_book_search_without_params_returns_test_results(self, client):
        """Test that book search without params returns test results."""
        response = client.get("/api?t=book&apikey=test-api-key")
        assert response.status_code == 200
        assert b"<rss" in response.content
        assert b"Test Book" in response.content

    def test_search_requires_auth(self, client):
        """Test that search requires valid API key."""
        response = client.get("/api?t=search&q=test&apikey=wrong-key")
        assert response.status_code == 200  # Newznab returns 200 with error XML
        assert b"error" in response.content.lower()
        assert b"100" in response.content  # Error code for invalid credentials

    def test_invalid_function(self, client):
        """Test that invalid function returns error."""
        response = client.get("/api?t=invalid&apikey=test-api-key")
        assert response.status_code == 200
        assert b"error" in response.content.lower()
        assert b"202" in response.content  # No such function

    def test_search_with_query_returns_rss(self, client):
        """t=search with query returns RSS with record fields."""
        from collections import namedtuple

        FakeRecord = namedtuple(
            "FakeRecord", "title author format language size id"
        )
        fake = FakeRecord(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            format="epub",
            language="English",
            size="2.5 MB",
            id="abc123",
        )

        with patch(
            "shelfmark.release_sources.direct_download.search_books", return_value=([fake], 1)
        ):
            response = client.get(
                "/api?t=search&q=gatsby&apikey=test-api-key"
            )

        assert response.status_code == 200
        content = response.text
        assert "<rss" in content
        assert "The Great Gatsby" in content
        assert "F. Scott Fitzgerald" in content
        assert "[epub]" in content
        assert "abc123" in content
        assert "enclosure" in content
        assert "application/x-nzb" in content

    def test_book_search_with_author_title(self, client):
        """t=book joins author+title into query for search_books."""
        from collections import namedtuple

        FakeRecord = namedtuple(
            "FakeRecord", "title author format language size id"
        )
        fake = FakeRecord(
            title="Dune", author="Frank Herbert",
            format="epub", language="English", size="1 MB", id="dune123",
        )

        with patch(
            "shelfmark.release_sources.direct_download.search_books", return_value=([fake], 1)
        ) as mock_search:
            client.get(
                "/api?t=book&author=Frank+Herbert&title=Dune&apikey=test-api-key"
            )

        mock_search.assert_called_once()
        call_query = mock_search.call_args[0][0]
        assert "Dune" in call_query
        assert "Frank Herbert" in call_query

    def test_search_returns_error_on_failure(self, client):
        """t=search returns error XML when search_books raises."""
        from shelfmark.release_sources.direct_download import SearchUnavailableError

        with patch(
            "shelfmark.release_sources.direct_download.search_books",
            side_effect=SearchUnavailableError("down"),
        ):
            response = client.get(
                "/api?t=search&q=test&apikey=test-api-key"
            )

        assert response.status_code == 200
        assert b"900" in response.content  # Error code
        assert b"down" in response.content

    @pytest.mark.parametrize("upstream_total", [None, 120, "500+"])
    def test_search_paginates_available_records(self, client, upstream_total):
        from xml.etree import ElementTree as ET

        from shelfmark.release_sources import BrowseRecord

        records = [
            BrowseRecord(id=f"book{i}", title=f"Book {i}", source="direct_download")
            for i in range(3)
        ]
        with patch(
            "shelfmark.release_sources.direct_download.search_books",
            return_value=(records, upstream_total),
        ):
            response = client.get(
                "/api?t=search&q=books&limit=1&offset=1&apikey=test-api-key"
            )

        root = ET.fromstring(response.content)
        header = root.find(".//{http://www.newznab.com/DTD/2010/feeds/attributes/}response")
        assert header is not None
        assert header.attrib == {"offset": "1", "total": "3"}
        assert [item.findtext("title") for item in root.findall(".//item")] == ["Book 1"]

    def test_search_with_no_matches(self, client):
        with patch(
            "shelfmark.release_sources.direct_download.search_books",
            return_value=([], None),
        ):
            response = client.get("/api?t=search&q=missing&apikey=test-api-key")

        assert b'<newznab:response offset="0" total="0"' in response.content
        assert b"<item>" not in response.content

    def test_search_uses_upstream_parser(self, client):
        from bs4 import BeautifulSoup

        html = """<table><tbody><tr>
            <td><a href="/md5/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"><img src="cover.jpg"></a></td>
            <td><span>Parsed Book</span></td><td><span>Parsed Author</span></td>
            <td><span>Publisher</span></td><td><span>2026</span></td>
            <td></td><td></td><td><span>English</span></td>
            <td><span>fiction</span></td><td><span>epub</span></td>
            <td><span>2 MB</span></td>
        </tr></tbody></table>"""
        table = BeautifulSoup(html, "html.parser").find("tbody")
        with (
            patch(
                "shelfmark.release_sources.direct_download.annas_archive.network.AAMirrorSelector"
            ),
            patch(
                "shelfmark.release_sources.direct_download.annas_archive.network.get_aa_base_url",
                return_value="https://example.invalid",
            ),
            patch(
                "shelfmark.release_sources.direct_download.annas_archive._fetch_search_table",
                return_value=(html, table),
            ),
            patch(
                "shelfmark.release_sources.direct_download.annas_archive._enrich_search_results_with_downloads"
            ),
        ):
            response = client.get("/api?t=search&q=parsed&apikey=test-api-key")

        assert b"Parsed Book - Parsed Author [epub]" in response.content
        assert b'<newznab:response offset="0" total="1"' in response.content


class TestSABnzbdAPI:
    """Tests for the SABnzbd API."""

    @pytest.fixture(autouse=True)
    def _clear_queue(self):
        """Clear the in-memory download queue before each test."""
        from shelfmark_news.sabnzbd import _download_queue

        _download_queue.clear()
        with patch("shelfmark_news.sabnzbd._execute_download"):
            yield
        _download_queue.clear()

    def test_version_endpoint(self, client):
        """Test version endpoint."""
        response = client.get("/sabnzbd/api?mode=version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_auth_endpoint(self, client):
        """Test auth endpoint with valid key."""
        response = client.get("/sabnzbd/api?mode=auth&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data.get("auth") == "ok"

    def test_queue_endpoint(self, client):
        """Test queue endpoint returns queue structure."""
        response = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert "queue" in data
        assert "slots" in data["queue"]

    def test_history_endpoint(self, client):
        """Test history endpoint returns history structure."""
        response = client.get("/sabnzbd/api?mode=history&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "slots" in data["history"]

    # --- Lifecycle tests: verify queue/history reflect download state ---

    def test_queued_item_appears_in_queue(self, client):
        """A QUEUED item appears in the queue endpoint with correct fields."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        item = DownloadItem(
            nzo_id="SABnzbd_nzo_test001",
            source_id="abc123",
            source="direct_download",
            title="Test Book - Test Author [epub]",
            status=DownloadStatus.QUEUED,
            progress=0.0,
        )
        _download_queue[item.nzo_id] = item

        response = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        slots = data["queue"]["slots"]
        assert len(slots) == 1
        assert slots[0]["nzo_id"] == "SABnzbd_nzo_test001"
        assert slots[0]["status"] == "Queued"
        assert slots[0]["percentage"] == "0"

    def test_downloading_item_appears_in_queue_with_speed_eta(self, client):
        """A DOWNLOADING item in queue reports speed, ETA and progress."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        item = DownloadItem(
            nzo_id="SABnzbd_nzo_test002",
            source_id="def456",
            source="direct_download",
            title="Downloading Book",
            status=DownloadStatus.DOWNLOADING,
            progress=42.5,
            size=10 * 1024 * 1024,  # 10 MB
            downloaded=4250000,
            speed=512 * 1024,  # 512 KB/s
            eta="0:12",
        )
        _download_queue[item.nzo_id] = item

        response = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        slots = data["queue"]["slots"]
        assert len(slots) == 1
        s = slots[0]
        assert s["status"] == "Downloading"
        assert s["percentage"] == "42"
        assert s["timeleft"] == "0:12"

        # Queue-level speed should reflect the downloading slot
        assert data["queue"]["speed"] != "0"
        assert "K" in data["queue"]["speed"] or "M" in data["queue"]["speed"]

    def test_queue_reports_idle_when_no_downloading_items(self, client):
        """Queue status is 'Idle' when all items are QUEUED (none DOWNLOADING)."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        item = DownloadItem(
            nzo_id="SABnzbd_nzo_test003",
            source_id="ghi789",
            source="direct_download",
            title="Waiting Book",
            status=DownloadStatus.QUEUED,
        )
        _download_queue[item.nzo_id] = item

        response = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["queue"]["status"] == "Idle"
        assert data["queue"]["speed"] == "0"

    def test_queue_reports_downloading_when_any_item_is_downloading(self, client):
        """Queue status is 'Downloading' when at least one item is DOWNLOADING."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a",
            source_id="a",
            source="direct_download",
            title="Queued Book",
            status=DownloadStatus.QUEUED,
        )
        _download_queue["nzo_b"] = DownloadItem(
            nzo_id="nzo_b",
            source_id="b",
            source="direct_download",
            title="Downloading Book",
            status=DownloadStatus.DOWNLOADING,
            speed=100 * 1024,
        )

        response = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["queue"]["status"] == "Downloading"

    def test_completed_item_appears_in_history_not_queue(self, client):
        """A COMPLETED item appears in history, not in the queue."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        item = DownloadItem(
            nzo_id="SABnzbd_nzo_test004",
            source_id="jkl012",
            source="direct_download",
            title="Finished Book",
            status=DownloadStatus.COMPLETED,
            progress=100.0,
            size=5 * 1024 * 1024,
            download_path="/downloads/finished_book.epub",
        )
        _download_queue[item.nzo_id] = item

        # Queue should be empty
        queue_resp = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert queue_resp.status_code == 200
        assert len(queue_resp.json()["queue"]["slots"]) == 0

        # History should contain the item
        history_resp = client.get("/sabnzbd/api?mode=history&apikey=test-api-key")
        assert history_resp.status_code == 200
        history_slots = history_resp.json()["history"]["slots"]
        assert len(history_slots) == 1
        assert history_slots[0]["nzo_id"] == "SABnzbd_nzo_test004"
        assert history_slots[0]["status"] == "Completed"
        assert history_slots[0]["storage"] == "/downloads/finished_book.epub"

    def test_failed_item_appears_in_history_not_queue(self, client):
        """A FAILED item appears in history with its error message."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        item = DownloadItem(
            nzo_id="SABnzbd_nzo_test005",
            source_id="mno345",
            source="direct_download",
            title="Failed Book",
            status=DownloadStatus.FAILED,
            error_message="Network timeout",
        )
        _download_queue[item.nzo_id] = item

        # Queue should be empty
        queue_resp = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        assert len(queue_resp.json()["queue"]["slots"]) == 0

        # History should contain the failure
        history_resp = client.get("/sabnzbd/api?mode=history&apikey=test-api-key")
        history_slots = history_resp.json()["history"]["slots"]
        assert len(history_slots) == 1
        assert history_slots[0]["status"] == "Failed"
        assert history_slots[0]["fail_message"] == "Network timeout"

    def test_multiple_items_mixed_states(self, client):
        """Queue and history correctly partition items by status."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        _download_queue["q1"] = DownloadItem(
            nzo_id="q1",
            source_id="a",
            source="direct_download",
            title="Q",
            status=DownloadStatus.QUEUED,
        )
        _download_queue["q2"] = DownloadItem(
            nzo_id="q2",
            source_id="b",
            source="direct_download",
            title="DL",
            status=DownloadStatus.DOWNLOADING,
            speed=200 * 1024,
            size=8 * 1024 * 1024,
        )
        _download_queue["q3"] = DownloadItem(
            nzo_id="q3",
            source_id="c",
            source="direct_download",
            title="Done",
            status=DownloadStatus.COMPLETED,
            download_path="/out/done.epub",
        )
        _download_queue["q4"] = DownloadItem(
            nzo_id="q4",
            source_id="d",
            source="direct_download",
            title="Fail",
            status=DownloadStatus.FAILED,
            error_message="Boom",
        )

        queue_resp = client.get("/sabnzbd/api?mode=queue&apikey=test-api-key")
        queue_slots = queue_resp.json()["queue"]["slots"]
        queue_nzo_ids = {s["nzo_id"] for s in queue_slots}
        assert queue_nzo_ids == {"q1", "q2"}
        assert queue_resp.json()["queue"]["status"] == "Downloading"

        history_resp = client.get("/sabnzbd/api?mode=history&apikey=test-api-key")
        history_slots = history_resp.json()["history"]["slots"]
        history_nzo_ids = {s["nzo_id"] for s in history_slots}
        assert history_nzo_ids == {"q3", "q4"}

    # --- Untested SABnzbd modes ---

    def test_auth_with_invalid_key(self, client):
        """mode=auth with wrong key returns failed."""
        response = client.get("/sabnzbd/api?mode=auth&apikey=wrong-key")
        assert response.status_code == 200
        data = response.json()
        assert data["auth"] == "failed"
        assert data["status"] is False

    def test_get_config(self, client):
        """mode=get_config returns complete_dir and download_dir."""
        response = client.get("/sabnzbd/api?mode=get_config&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        assert "complete_dir" in data["config"]["misc"]
        assert "download_dir" in data["config"]["misc"]

    def test_addurl_creates_queue_item(self, client):
        """mode=addurl creates a DownloadItem visible in the queue."""
        from shelfmark_news.sabnzbd import _download_queue

        response = client.get(
            "/sabnzbd/api?mode=addurl&apikey=test-api-key&name=some_source_id"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        assert len(data["nzo_ids"]) == 1
        nzo_id = data["nzo_ids"][0]
        assert nzo_id in _download_queue
        assert _download_queue[nzo_id].source_id == "some_source_id"

    def test_addurl_extracts_source_id_from_url(self, client):
        """mode=addurl extracts source_id from /download/ path in URL."""
        from shelfmark_news.sabnzbd import _download_queue

        response = client.get(
            "/sabnzbd/api?mode=addurl&apikey=test-api-key"
            "&name=http://localhost/api/v1/download/abc123?apikey=foo"
        )
        assert response.status_code == 200
        nzo_id = response.json()["nzo_ids"][0]
        assert _download_queue[nzo_id].source_id == "abc123"

    def test_addurl_no_name(self, client):
        """mode=addurl without name returns error."""
        response = client.get("/sabnzbd/api?mode=addurl&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "No URL/ID provided" in data["error"]

    def test_addfile_creates_queue_item(self, client):
        """mode=addfile with valid NZB creates a queue item."""
        from shelfmark_news.sabnzbd import _download_queue

        nzb_content = (
            '<?xml version="1.0"?>'
            '<nzb><head><meta type="id">test_source_42</meta></head></nzb>'
        )
        response = client.post(
            "/sabnzbd/api?mode=addfile&apikey=test-api-key",
            files={"name": ("test.nzb", nzb_content, "application/x-nzb")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        assert len(data["nzo_ids"]) == 1
        nzo_id = data["nzo_ids"][0]
        assert nzo_id in _download_queue
        assert _download_queue[nzo_id].source_id == "test_source_42"

    def test_addfile_no_file(self, client):
        """mode=addfile without a file returns error."""
        response = client.post("/sabnzbd/api?mode=addfile&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "No NZB file provided" in data["error"]

    def test_addfile_invalid_nzb(self, client):
        """mode=addfile with NZB missing <meta type='id'> returns error."""
        nzb_content = '<?xml version="1.0"?><nzb><head></head></nzb>'
        response = client.post(
            "/sabnzbd/api?mode=addfile&apikey=test-api-key",
            files={"name": ("test.nzb", nzb_content, "application/x-nzb")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "Could not extract source ID" in data["error"]

    def test_delete_removes_items(self, client):
        """mode=delete removes items from the queue."""
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadItem,
            DownloadStatus,
        )

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.QUEUED,
        )
        _download_queue["nzo_b"] = DownloadItem(
            nzo_id="nzo_b", source_id="b", source="direct_download",
            title="B", status=DownloadStatus.QUEUED,
        )

        response = client.get(
            "/sabnzbd/api?mode=delete&apikey=test-api-key&nzo_ids=nzo_a,nzo_b"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        assert set(data["nzo_ids"]) == {"nzo_a", "nzo_b"}
        assert len(_download_queue) == 0

    def test_delete_unknown_id_noop(self, client):
        """mode=delete with unknown nzo_id returns empty list."""
        response = client.get(
            "/sabnzbd/api?mode=delete&apikey=test-api-key&nzo_ids=ghost"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True
        assert data["nzo_ids"] == []

    def test_delete_value_fallback(self, client):
        """mode=delete uses value param when nzo_ids is absent."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_x"] = DownloadItem(
            nzo_id="nzo_x", source_id="x", source="direct_download",
            title="X", status=DownloadStatus.QUEUED,
        )
        response = client.get(
            "/sabnzbd/api?mode=delete&apikey=test-api-key&value=nzo_x"
        )
        assert response.status_code == 200
        assert response.json()["nzo_ids"] == ["nzo_x"]
        assert len(_download_queue) == 0

    def test_pause_pauses_downloading(self, client):
        """mode=pause changes DOWNLOADING to PAUSED."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.DOWNLOADING,
        )
        response = client.get(
            "/sabnzbd/api?mode=pause&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.status_code == 200
        assert response.json()["nzo_ids"] == ["nzo_a"]
        assert _download_queue["nzo_a"].status == DownloadStatus.PAUSED

    def test_pause_ignores_wrong_status(self, client):
        """mode=pause does not pause QUEUED items."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.QUEUED,
        )
        response = client.get(
            "/sabnzbd/api?mode=pause&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.json()["nzo_ids"] == []
        assert _download_queue["nzo_a"].status == DownloadStatus.QUEUED

    def test_pause_no_ids_error(self, client):
        """mode=pause without nzo_ids returns error."""
        response = client.get("/sabnzbd/api?mode=pause&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "No NZO IDs provided" in data["error"]

    def test_resume_resumes_paused(self, client):
        """mode=resume changes PAUSED to DOWNLOADING."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.PAUSED,
        )
        response = client.get(
            "/sabnzbd/api?mode=resume&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.status_code == 200
        assert response.json()["nzo_ids"] == ["nzo_a"]
        assert _download_queue["nzo_a"].status == DownloadStatus.DOWNLOADING

    def test_resume_ignores_wrong_status(self, client):
        """mode=resume does not resume DOWNLOADING items."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.DOWNLOADING,
        )
        response = client.get(
            "/sabnzbd/api?mode=resume&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.json()["nzo_ids"] == []
        assert _download_queue["nzo_a"].status == DownloadStatus.DOWNLOADING

    def test_resume_no_ids_error(self, client):
        """mode=resume without nzo_ids returns error."""
        response = client.get("/sabnzbd/api?mode=resume&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "No NZO IDs provided" in data["error"]

    def test_retry_resets_failed_to_queued(self, client):
        """mode=retry resets FAILED to QUEUED, clears progress and error."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.FAILED,
            progress=99.0, error_message="Boom",
        )
        response = client.get(
            "/sabnzbd/api?mode=retry&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.status_code == 200
        assert response.json()["nzo_ids"] == ["nzo_a"]
        item = _download_queue["nzo_a"]
        assert item.status == DownloadStatus.QUEUED
        assert item.progress == 0.0
        assert item.error_message == ""

    def test_retry_ignores_completed(self, client):
        """mode=retry does not reset COMPLETED items."""
        from shelfmark_news.sabnzbd import _download_queue, DownloadItem, DownloadStatus

        _download_queue["nzo_a"] = DownloadItem(
            nzo_id="nzo_a", source_id="a", source="direct_download",
            title="A", status=DownloadStatus.COMPLETED,
        )
        response = client.get(
            "/sabnzbd/api?mode=retry&apikey=test-api-key&nzo_ids=nzo_a"
        )
        assert response.json()["nzo_ids"] == []
        assert _download_queue["nzo_a"].status == DownloadStatus.COMPLETED

    def test_retry_no_ids_error(self, client):
        """mode=retry without nzo_ids returns error."""
        response = client.get("/sabnzbd/api?mode=retry&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "No NZO IDs provided" in data["error"]

    def test_unknown_mode(self, client):
        """Unknown mode returns error."""
        response = client.get("/sabnzbd/api?mode=bogus&apikey=test-api-key")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "Unknown mode" in data["error"]

    def test_protected_mode_requires_auth(self, client):
        """Protected modes require API key."""
        response = client.get("/sabnzbd/api?mode=queue")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is False
        assert "API Key Incorrect" in data["error"]

    def test_post_support(self, client):
        """POST to /sabnzbd/api works identically to GET."""
        response = client.post("/sabnzbd/api?mode=version")
        assert response.status_code == 200
        assert response.json()["version"] == "4.0.0"


class TestDownloadEndpoint:
    """Tests for /api/v1/download/{source_id}."""

    def test_download_endpoint_returns_nzb(self, client):
        """GET returns application/x-nzb XML with source_id in meta."""
        response = client.get(
            "/api/v1/download/test_source_123?apikey=test-api-key"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-nzb"
        content = response.text
        assert "<nzb" in content
        assert "<meta type=\"id\">test_source_123</meta>" in content
        assert "alt.binaries.ebooks" in content

    def test_download_endpoint_requires_auth(self, client):
        """GET without valid key returns 401."""
        response = client.get("/api/v1/download/test_source_123")
        assert response.status_code == 401

    def test_download_endpoint_wrong_key_returns_401(self, client):
        """GET with wrong key returns 401."""
        response = client.get(
            "/api/v1/download/test_source_123?apikey=wrong-key"
        )
        assert response.status_code == 401


class TestHealthEndpoint:
    """Tests for health check."""

    def test_health_endpoint(self, client):
        """Test health endpoint returns healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data


class TestReadarrWorkflow:
    """End-to-end Readarr workflow: search -> grab NZB -> addfile -> track."""

    @pytest.fixture(autouse=True)
    def _clear_queue(self):
        """Clear the in-memory download queue before each test."""
        from shelfmark_news.sabnzbd import _download_queue

        _download_queue.clear()
        with patch("shelfmark_news.sabnzbd._execute_download"):
            yield
        _download_queue.clear()

    def test_search_grab_download_history(self, client):
        """Full Readarr lifecycle with mocked shelfmark search."""
        from collections import namedtuple
        from shelfmark_news.sabnzbd import (
            _download_queue,
            DownloadStatus,
        )

        FakeRecord = namedtuple(
            "FakeRecord", "title author format language size id"
        )
        fake = FakeRecord(
            title="Neuromancer",
            author="William Gibson",
            format="epub",
            language="English",
            size="1.8 MB",
            id="neuro123",
        )

        # Step 1: Search
        with patch(
            "shelfmark.release_sources.direct_download.search_books", return_value=([fake], 1)
        ):
            search_resp = client.get(
                "/api?t=search&q=neuromancer&apikey=test-api-key"
            )

        assert search_resp.status_code == 200
        assert b"Neuromancer" in search_resp.content
        assert b"neuro123" in search_resp.content

        # Step 2: Grab NZB from download endpoint
        nzb_resp = client.get(
            "/api/v1/download/neuro123?apikey=test-api-key"
        )
        assert nzb_resp.status_code == 200
        nzb_content = nzb_resp.text
        assert "<meta type=\"id\">neuro123</meta>" in nzb_content

        # Step 3: Send NZB to SABnzbd via addfile
        add_resp = client.post(
            "/sabnzbd/api?mode=addfile&apikey=test-api-key",
            files={"name": ("neuro.nzb", nzb_content, "application/x-nzb")},
        )
        assert add_resp.status_code == 200
        assert add_resp.json()["status"] is True
        nzo_id = add_resp.json()["nzo_ids"][0]
        assert nzo_id in _download_queue

        # Step 4: Verify item in queue as QUEUED
        queue_resp = client.get(
            "/sabnzbd/api?mode=queue&apikey=test-api-key"
        )
        queue_slots = queue_resp.json()["queue"]["slots"]
        assert len(queue_slots) == 1
        assert queue_slots[0]["nzo_id"] == nzo_id
        assert queue_slots[0]["status"] == "Queued"
        assert queue_slots[0]["cat"] == "*"

        # Step 5: Simulate download completion
        _download_queue[nzo_id].status = DownloadStatus.COMPLETED
        _download_queue[nzo_id].progress = 100.0
        _download_queue[nzo_id].download_path = "/tmp/ingest/neuromancer.epub"

        # Step 6: Verify item moved to history
        hist_resp = client.get(
            "/sabnzbd/api?mode=history&apikey=test-api-key"
        )
        history_slots = hist_resp.json()["history"]["slots"]
        assert len(history_slots) == 1
        assert history_slots[0]["nzo_id"] == nzo_id
        assert history_slots[0]["status"] == "Completed"
        assert history_slots[0]["storage"] == "/tmp/ingest/neuromancer.epub"

        # Queue should now be empty
        queue_resp2 = client.get(
            "/sabnzbd/api?mode=queue&apikey=test-api-key"
        )
        assert len(queue_resp2.json()["queue"]["slots"]) == 0


class TestShelfmarkDownload:
    """Exercise the real handler and post-processing, mocking only network access."""

    @pytest.fixture
    def download_item(self, client):
        from shelfmark_news.sabnzbd import DownloadItem, _download_queue

        item = DownloadItem(
            nzo_id="integration-download",
            source_id="a" * 32,
            source="direct_download",
            title="Pending",
        )
        _download_queue[item.nzo_id] = item
        yield item
        _download_queue.pop(item.nzo_id, None)

    async def test_download_moves_file_to_ingest(self, download_item, tmp_path, monkeypatch):
        from pathlib import Path

        from shelfmark.release_sources import BrowseRecord

        from shelfmark_news.sabnzbd import DownloadStatus, _execute_download

        book = BrowseRecord(
            id=download_item.source_id,
            title="Integration Book",
            source="direct_download",
            author="Test Author",
            format="epub",
            size="1 MB",
        )
        ingest_dir = tmp_path / "ingest"
        monkeypatch.setattr(
            "shelfmark.release_sources.direct_download.handler.TMP_DIR", tmp_path
        )
        monkeypatch.setattr(
            "shelfmark.download.postprocess.pipeline.get_final_destination",
            lambda task: ingest_dir,
        )

        def fake_download(book_info, book_path, progress, cancel_flag, status):
            book_path.write_bytes(b"test book content")
            status("downloading", None)
            progress(100.0)
            return "https://example.invalid/book.epub"

        with (
            patch(
                "shelfmark.release_sources.direct_download.annas_archive.get_book_info",
                return_value=book,
            ) as metadata,
            patch(
                "shelfmark.release_sources.direct_download.handler._download_book",
                side_effect=fake_download,
            ),
        ):
            await _execute_download(download_item.nzo_id, download_item.source_id)

        metadata.assert_called_once_with(download_item.source_id, fetch_download_count=False)
        assert download_item.status == DownloadStatus.COMPLETED
        assert download_item.download_path is not None
        final_path = Path(download_item.download_path)
        assert final_path.is_relative_to(ingest_dir)
        assert final_path.read_bytes() == b"test book content"
        assert not list(tmp_path.glob("*.epub"))
        assert download_item.title == book.title
        assert download_item.size == 1024 * 1024
        assert download_item.progress == 100.0

    @pytest.mark.parametrize("failure", ["metadata", "download", "postprocess"])
    async def test_download_failures_reach_history(self, download_item, client, failure):
        from shelfmark.release_sources import BrowseRecord

        from shelfmark_news.sabnzbd import DownloadStatus, _execute_download

        with (
            patch(
                "shelfmark.release_sources.direct_download.annas_archive.get_book_info",
                return_value=BrowseRecord(
                    id=download_item.source_id, title="Book", source="direct_download"
                ),
                side_effect=RuntimeError("Metadata unavailable") if failure == "metadata" else None,
            ),
            patch(
                "shelfmark.release_sources.direct_download.DirectDownloadHandler.download",
                return_value=None if failure == "download" else "/unused/book.epub",
            ),
            patch(
                "shelfmark.download.postprocess.router.post_process_download", return_value=None
            ) as postprocess,
        ):
            await _execute_download(download_item.nzo_id, download_item.source_id)

        assert download_item.status == DownloadStatus.FAILED
        assert download_item.error_message == {
            "metadata": "Metadata unavailable",
            "download": "Download returned no path",
            "postprocess": "Post-processing failed",
        }[failure]
        assert download_item.download_path is None
        assert postprocess.call_count == (1 if failure == "postprocess" else 0)
        history = client.get("/sabnzbd/api?mode=history&apikey=test-api-key").json()
        assert any(
            slot["nzo_id"] == download_item.nzo_id and slot["status"] == "Failed"
            for slot in history["history"]["slots"]
        )


def test_xlib_supports_browser_bypass():
    import Xlib.X

    assert hasattr(Xlib.X, "FamilyServerInterpreted")
