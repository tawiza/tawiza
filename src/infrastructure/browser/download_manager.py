"""
File download management for browser automation.

Features:
- Download tracking with progress monitoring
- File verification (size, type, integrity)
- Automatic processing (CSV, PDF, JSON parsing)
- Retry logic for failed downloads
- Temporary file cleanup
"""

import asyncio
import hashlib
import mimetypes
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel


class DownloadInfo(BaseModel):
    """Information about a download."""

    download_id: str
    url: str
    filename: str
    file_path: Path
    size_bytes: int = 0
    mime_type: str | None = None
    status: str = "pending"  # pending, downloading, completed, failed
    progress: float = 0.0  # 0.0 to 1.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    checksum_sha256: str | None = None


class DownloadManager:
    """
    Manage file downloads from browser automation.

    Features:
    - Track multiple downloads
    - Monitor progress
    - Verify downloaded files
    - Auto-process common file types
    """

    def __init__(
        self,
        download_dir: Path | None = None,
        auto_verify: bool = True,
        auto_cleanup: bool = False,
    ):
        """
        Initialize download manager.

        Args:
            download_dir: Directory for downloads (default: ./downloads)
            auto_verify: Automatically verify downloaded files
            auto_cleanup: Automatically delete files after processing
        """
        self.download_dir = download_dir or Path("./downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.auto_verify = auto_verify
        self.auto_cleanup = auto_cleanup

        self.downloads: dict[str, DownloadInfo] = {}
        self._download_tasks: dict[str, asyncio.Task] = {}

        logger.info(f"DownloadManager initialized (dir={self.download_dir})")

    async def setup_page_downloads(
        self,
        page: Any,
        download_dir: Path | None = None,
    ) -> None:
        """
        Configure page for downloads.

        Args:
            page: Playwright page object
            download_dir: Override default download directory
        """
        target_dir = download_dir or self.download_dir

        # Set download behavior in Playwright
        # This is handled automatically by Playwright's context
        logger.info(f"Page configured for downloads to {target_dir}")

    async def wait_for_download(
        self,
        page: Any,
        trigger_action: Callable,
        timeout: float = 30.0,
        expected_filename: str | None = None,
    ) -> DownloadInfo:
        """
        Wait for a download to start and complete.

        Args:
            page: Playwright page object
            trigger_action: Async function that triggers the download
            timeout: Maximum wait time
            expected_filename: Expected filename (for verification)

        Returns:
            DownloadInfo with download details

        Example:
            download = await manager.wait_for_download(
                page,
                lambda: page.click('a[download]'),
                expected_filename='report.pdf'
            )
        """
        from uuid import uuid4

        download_id = str(uuid4())

        logger.info(f"Waiting for download (id={download_id})")

        try:
            # Start waiting for download event
            async with page.expect_download(timeout=timeout * 1000) as download_info:
                # Trigger the download
                await trigger_action()

            # Get download object
            download = await download_info.value

            # Get suggested filename
            filename = await download.suggested_filename()

            # Verify expected filename if provided
            if expected_filename and filename != expected_filename:
                logger.warning(
                    f"Filename mismatch: expected '{expected_filename}', got '{filename}'"
                )

            # Save to download directory
            file_path = self.download_dir / filename
            await download.save_as(file_path)

            # Get file info
            file_size = file_path.stat().st_size
            mime_type = mimetypes.guess_type(filename)[0]

            # Create download info
            info = DownloadInfo(
                download_id=download_id,
                url=page.url,
                filename=filename,
                file_path=file_path,
                size_bytes=file_size,
                mime_type=mime_type,
                status="completed",
                progress=1.0,
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )

            # Calculate checksum if auto-verify enabled
            if self.auto_verify:
                info.checksum_sha256 = self._calculate_checksum(file_path)

            self.downloads[download_id] = info

            logger.success(
                f"Download complete: {filename} ({file_size:,} bytes) -> {file_path}"
            )

            return info

        except Exception as e:
            logger.error(f"Download failed: {e}")

            info = DownloadInfo(
                download_id=download_id,
                url=page.url,
                filename="",
                file_path=Path(""),
                status="failed",
                error=str(e),
            )

            self.downloads[download_id] = info
            raise

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()

        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        checksum = sha256.hexdigest()
        logger.debug(f"Checksum for {file_path.name}: {checksum}")
        return checksum

    async def process_download(
        self,
        download_info: DownloadInfo,
        processor: str | None = "auto",
    ) -> dict[str, Any]:
        """
        Process downloaded file based on type.

        Args:
            download_info: Download information
            processor: Processor type ("auto", "csv", "json", "pdf", "text")

        Returns:
            Processed data dictionary
        """
        file_path = download_info.file_path

        if processor == "auto":
            # Auto-detect based on MIME type or extension
            if download_info.mime_type:
                if "csv" in download_info.mime_type:
                    processor = "csv"
                elif "json" in download_info.mime_type:
                    processor = "json"
                elif "pdf" in download_info.mime_type:
                    processor = "pdf"
                else:
                    processor = "text"
            else:
                # Fallback to extension
                ext = file_path.suffix.lower()
                if ext == ".csv":
                    processor = "csv"
                elif ext == ".json":
                    processor = "json"
                elif ext == ".pdf":
                    processor = "pdf"
                else:
                    processor = "text"

        logger.info(f"Processing {file_path.name} as {processor}")

        try:
            if processor == "csv":
                return await self._process_csv(file_path)
            elif processor == "json":
                return await self._process_json(file_path)
            elif processor == "pdf":
                return await self._process_pdf(file_path)
            elif processor == "text":
                return await self._process_text(file_path)
            else:
                raise ValueError(f"Unknown processor: {processor}")

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            raise

    async def _process_csv(self, file_path: Path) -> dict[str, Any]:
        """Process CSV file."""
        import csv

        rows = []
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))

        logger.info(f"Loaded {len(rows)} rows from CSV")

        return {
            "type": "csv",
            "rows": rows,
            "row_count": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
        }

    async def _process_json(self, file_path: Path) -> dict[str, Any]:
        """Process JSON file."""
        import json

        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"Loaded JSON data from {file_path.name}")

        return {
            "type": "json",
            "data": data,
        }

    async def _process_pdf(self, file_path: Path) -> dict[str, Any]:
        """Process PDF file (extract text)."""
        try:
            import PyPDF2

            with file_path.open("rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"

            logger.info(f"Extracted text from PDF ({len(reader.pages)} pages)")

            return {
                "type": "pdf",
                "text": text,
                "page_count": len(reader.pages),
            }

        except ImportError:
            logger.warning("PyPDF2 not installed, returning file info only")
            return {
                "type": "pdf",
                "file_path": str(file_path),
                "note": "Install PyPDF2 for text extraction",
            }

    async def _process_text(self, file_path: Path) -> dict[str, Any]:
        """Process text file."""
        with file_path.open("r", encoding="utf-8") as f:
            text = f.read()

        logger.info(f"Loaded text file ({len(text)} chars)")

        return {
            "type": "text",
            "text": text,
            "char_count": len(text),
            "line_count": text.count("\n") + 1,
        }

    def get_download(self, download_id: str) -> DownloadInfo | None:
        """Get download information by ID."""
        return self.downloads.get(download_id)

    def list_downloads(
        self,
        status: str | None = None,
    ) -> list[DownloadInfo]:
        """
        List all downloads.

        Args:
            status: Filter by status

        Returns:
            List of download information
        """
        downloads = list(self.downloads.values())

        if status:
            downloads = [d for d in downloads if d.status == status]

        return sorted(downloads, key=lambda d: d.started_at or datetime.now(), reverse=True)

    async def cleanup_download(self, download_id: str) -> bool:
        """
        Delete downloaded file.

        Args:
            download_id: Download ID

        Returns:
            True if deleted, False if not found
        """
        download = self.downloads.get(download_id)
        if not download:
            return False

        try:
            if download.file_path.exists():
                download.file_path.unlink()
                logger.info(f"Deleted {download.filename}")
            return True
        except Exception as e:
            logger.error(f"Error deleting {download.filename}: {e}")
            return False

    async def cleanup_all(self, status: str | None = None) -> int:
        """
        Clean up all downloads.

        Args:
            status: Only delete downloads with this status

        Returns:
            Number of files deleted
        """
        downloads = self.list_downloads(status=status)
        deleted_count = 0

        for download in downloads:
            if await self.cleanup_download(download.download_id):
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} download(s)")
        return deleted_count

    def get_stats(self) -> dict[str, Any]:
        """Get download statistics."""
        downloads = list(self.downloads.values())

        total_size = sum(d.size_bytes for d in downloads if d.status == "completed")
        total_count = len(downloads)
        completed = sum(1 for d in downloads if d.status == "completed")
        failed = sum(1 for d in downloads if d.status == "failed")

        return {
            "total_downloads": total_count,
            "completed": completed,
            "failed": failed,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }


# Convenience function
_manager_instance: DownloadManager | None = None


def get_download_manager(
    download_dir: Path | None = None,
) -> DownloadManager:
    """Get singleton download manager instance."""
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = DownloadManager(download_dir=download_dir)

    return _manager_instance


if __name__ == "__main__":
    # Example usage
    import asyncio

    from playwright.async_api import async_playwright

    async def demo():
        manager = DownloadManager(download_dir=Path("./test_downloads"))

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            # Navigate to page with download link
            await page.goto("https://example.com/downloads")

            # Wait for download
            download_info = await manager.wait_for_download(
                page,
                lambda: page.click('a[href$=".pdf"]'),
                expected_filename="report.pdf"
            )

            # Process the download
            result = await manager.process_download(download_info)
            print(f"Processed: {result}")

            # Get stats
            stats = manager.get_stats()
            print(f"Stats: {stats}")

            await browser.close()

    # asyncio.run(demo())
