from __future__ import annotations

import hashlib
import re
import urllib.request
import zipfile
import zlib
from http.client import HTTPException
from pathlib import Path


_IMAGE_NAME = "tf-16mib.img"
_IMAGE_SIZE = 16 * 1024**2
_MAX_DOWNLOAD_SIZE = 32 * 1024**2
_CHUNK_SIZE = 64 * 1024
_DOWNLOAD_URL = (
    "https://github.com/Zeal8bit/Zeal-Software-Collection/releases/latest/download/"
    f"{_IMAGE_NAME}.zip"
)


def download_community_image(directory: Path) -> Path:
    archive = directory / f"{_IMAGE_NAME}.zip"
    try:
        with urllib.request.urlopen(_DOWNLOAD_URL, timeout=30) as response, archive.open("wb") as output:
            size = 0
            while chunk := response.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > _MAX_DOWNLOAD_SIZE:
                    raise ValueError("Community image ZIP exceeds the download size limit")
                output.write(chunk)
    except HTTPException as exc:
        raise ValueError(f"Community image download failed: {exc}") from exc

    image = directory / _IMAGE_NAME
    checksum_name = f"{_IMAGE_NAME}.sha256"
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            for name in (_IMAGE_NAME, checksum_name):
                if names.count(name) != 1:
                    raise ValueError(f"Expected exactly one {name} in the community image ZIP")
                member = bundle.getinfo(name)
                if member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError(f"Unsupported ZIP compression for {name}")
            if bundle.getinfo(_IMAGE_NAME).file_size != _IMAGE_SIZE:
                raise ValueError("Expected a 16 MiB community image")
            if bundle.getinfo(checksum_name).file_size > 256:
                raise ValueError("Invalid community image checksum file")
            with bundle.open(checksum_name) as checksum_file:
                checksum = re.fullmatch(rb"([0-9a-fA-F]{64})[ \t]+\*?tf-16mib\.img\r?\n?", checksum_file.read(257))
            if checksum is None:
                raise ValueError("Invalid community image checksum file")

            digest = hashlib.sha256()
            with bundle.open(_IMAGE_NAME) as source, image.open("wb") as output:
                while chunk := source.read(_CHUNK_SIZE):
                    digest.update(chunk)
                    output.write(chunk)
                if output.tell() != _IMAGE_SIZE or digest.hexdigest() != checksum[1].decode("ascii").lower():
                    raise ValueError("Community image size or SHA-256 verification failed")
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError) as exc:
        raise ValueError(f"Invalid community image ZIP: {exc}") from exc
    return image
