"""Secure multipart/form-data parsing and image upload handling.

Validates extension + size, strips path components, stores under media/ with
a random filename. No reliance on client-provided content type for security.
"""
from __future__ import annotations

import os
import re
import secrets
from email.parser import BytesParser
from email.policy import default as default_policy

import settings


class UploadedFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self.content = content
        self.content_type = content_type
        self.size = len(content)


def parse_multipart(content_type: str, body: bytes):
    """Return (fields: dict[str,str], files: dict[str, UploadedFile|list])."""
    fields: dict[str, str] = {}
    files: dict[str, object] = {}

    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    msg = BytesParser(policy=default_policy).parsebytes(header + body)
    if not msg.is_multipart():
        return fields, files

    for part in msg.iter_parts():
        disp = part.get("Content-Disposition", "")
        name_m = re.search(r'name="([^"]*)"', disp)
        if not name_m:
            continue
        name = name_m.group(1)
        file_m = re.search(r'filename="([^"]*)"', disp)
        if file_m and file_m.group(1):
            payload = part.get_payload(decode=True) or b""
            uf = UploadedFile(file_m.group(1), payload, part.get_content_type())
            if name in files:
                if isinstance(files[name], list):
                    files[name].append(uf)
                else:
                    files[name] = [files[name], uf]
            else:
                files[name] = uf
        else:
            payload = part.get_payload(decode=True)
            fields[name] = payload.decode("utf-8", "replace") if payload else ""
    return fields, files


class UploadError(Exception):
    pass


def save_image(uploaded: UploadedFile, subdir: str) -> str:
    """Validate and save an uploaded image. Returns the media-relative path."""
    if uploaded is None or not uploaded.filename:
        raise UploadError("No file provided")
    ext = os.path.splitext(uploaded.filename)[1].lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise UploadError(
            f"Unsupported file type '{ext}'. Allowed: "
            + ", ".join(sorted(settings.ALLOWED_IMAGE_EXTENSIONS))
        )
    if uploaded.size == 0:
        raise UploadError("Empty file")
    if uploaded.size > settings.MAX_UPLOAD_BYTES:
        raise UploadError(
            f"File too large ({uploaded.size // 1024} KB). "
            f"Max {settings.MAX_UPLOAD_BYTES // 1024} KB."
        )
    # basic magic-byte sanity check
    if not _looks_like_image(uploaded.content):
        raise UploadError("File does not appear to be a valid image")

    target_dir = settings.MEDIA_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secrets.token_hex(16) + ext
    path = target_dir / safe_name
    path.write_bytes(uploaded.content)
    return f"{subdir}/{safe_name}"


def _looks_like_image(data: bytes) -> bool:
    if len(data) < 12:
        return False
    sigs = [
        b"\xff\xd8\xff",            # jpg
        b"\x89PNG\r\n\x1a\n",       # png
        b"GIF87a", b"GIF89a",       # gif
        b"RIFF",                     # webp (RIFF....WEBP)
    ]
    return any(data.startswith(s) for s in sigs) or (
        data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    )
