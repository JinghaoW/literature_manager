"""File hashing utilities."""

import hashlib
from pathlib import Path


def compute_file_hash(file_path: str | Path) -> str:
    """Compute the SHA-256 hash of a file.

    Reads the file in chunks to handle large files efficiently.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Hexadecimal SHA-256 digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(64 * 1024):
            sha256.update(chunk)
    return sha256.hexdigest()
