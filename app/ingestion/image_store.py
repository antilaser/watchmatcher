"""Local file storage for listing images kept out of the database."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from pathlib import Path
from time import time
from uuid import UUID

from app.core.config import get_settings

_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _storage_root() -> Path:
    root = Path(get_settings().media_storage_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def _extension(mime_type: str) -> str:
    return _MIME_EXTENSIONS.get(mime_type.lower(), ".jpg")


def resolve_media_path(relative_path: str) -> Path:
    root = _storage_root().resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("media path escapes storage root")
    return path


def store_listing_image(
    raw_message_id: UUID,
    *,
    image_base64: str,
    image_mime_type: str,
    message_at: datetime,
) -> dict[str, str]:
    settings = get_settings()
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except binascii.Error as e:
        raise ValueError("invalid image_base64") from e

    if len(image_bytes) > settings.listing_image_max_bytes:
        raise ValueError("listing image too large")

    mime = image_mime_type.lower() if image_mime_type else "image/jpeg"
    ext = _extension(mime)
    rel_dir = Path("listing-images") / f"{message_at:%Y}" / f"{message_at:%m}"
    rel_path = rel_dir / f"{raw_message_id}{ext}"
    final_path = resolve_media_path(str(rel_path))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    tmp_path.write_bytes(image_bytes)
    tmp_path.replace(final_path)

    return {
        "listing_image_path": str(rel_path),
        "listing_image_mime_type": mime,
        "listing_image_stored_at": datetime.now(timezone.utc).isoformat(),
    }


def delete_listing_image(metadata: dict) -> bool:
    rel_path = metadata.get("listing_image_path")
    if not isinstance(rel_path, str) or not rel_path:
        return False
    try:
        path = resolve_media_path(rel_path)
    except ValueError:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def delete_listing_images_older_than(days: int) -> int:
    root = (_storage_root() / "listing-images").resolve()
    if not root.exists():
        return 0
    cutoff = time() - days * 86_400
    deleted = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            deleted += 1
        except FileNotFoundError:
            continue
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass
    return deleted
