from __future__ import annotations

from pathlib import Path
from io import BytesIO
from typing import Optional, Union, BinaryIO, cast


class LocalFile:
    """
    File value object backed by either:
      - a local filesystem path, or
      - in-memory bytes

    Exactly one of (path, data) must be provided.
    """

    def __init__(
        self,
        *,
        path: Optional[Union[str, Path]] = None,
        data: Optional[bytes] = None,
        file_name: Optional[str] = None,
    ):
        if path is None and data is None:
            raise ValueError("LocalFile requires either 'path' or 'data'")

        if path is not None and data is not None:
            raise ValueError("LocalFile cannot have both 'path' and 'data'")

        self._path: Optional[Path] = Path(path) if path is not None else None
        self._data: Optional[bytes] = data

        if file_name:
            self._file_name = file_name
        elif self._path is not None:
            self._file_name = self._path.name
        else:
            self._file_name = None  # allowed but some properties will error

    # ---------- factories (preferred) ----------

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> LocalFile:
        return cls(path=path)

    @classmethod
    def from_bytes(cls, data: bytes, file_name: Optional[str] = None) -> LocalFile:
        return cls(data=data, file_name=file_name)

    # ---------- identity ----------

    @property
    def path(self) -> Optional[Path]:
        return self._path

    @property
    def is_in_memory(self) -> bool:
        return self._data is not None

    @property
    def is_on_disk(self) -> bool:
        return self._path is not None

    # ---------- name helpers ----------

    @property
    def name(self) -> str:
        if not self._file_name:
            raise ValueError("LocalFile has no file_name")
        return self._file_name

    @property
    def stem(self) -> str:
        return Path(self.name).stem

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix

    # ---------- existence & metadata ----------

    def exists(self) -> bool:
        if self.is_in_memory:
            return True
        return bool(self._path and self._path.exists())

    def is_file(self) -> bool:
        if self.is_in_memory:
            return True
        return bool(self._path and self._path.is_file())

    def size(self) -> int:
        if self._data is not None:
            return len(self._data)
        if not self._path:
            raise ValueError("LocalFile has no data or path")
        return self._path.stat().st_size

    # ---------- reading ----------

    def read_bytes(self) -> bytes:
        if self._data is not None:
            return self._data
        if not self._path:
            raise ValueError("LocalFile has no data or path")
        return self._path.read_bytes()

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.read_bytes().decode(encoding)

    def open(self, mode: str = "rb") -> BinaryIO:
        if "b" not in mode:
            raise ValueError("LocalFile.open() only supports binary modes")

        if self._path is not None:
            # Path.open is typed as IO[Any] in stubs; cast to BinaryIO for type checkers.
            return cast(BinaryIO, self._path.open(mode))

        if self._data is not None:
            return BytesIO(self._data)

        raise ValueError("LocalFile has neither path nor data")

    # ---------- writing / materializing ----------

    def write_bytes(self, data: bytes, overwrite: bool = True) -> None:
        if self._path is None:
            # purely in-memory
            self._data = data
            return

        if not overwrite and self._path.exists():
            raise FileExistsError(f"{self._path} already exists")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(data)

    def save_to(self, destination: Union[str, Path], overwrite: bool = True) -> LocalFile:
        """
        Persist this file to disk and return a new path-backed LocalFile.
        """
        dest = Path(destination)

        if not overwrite and dest.exists():
            raise FileExistsError(f"{dest} already exists")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.read_bytes())
        return LocalFile(path=dest)

    # ---------- convenience ----------

    def __str__(self) -> str:
        if self._path is not None:
            return str(self._path)
        return f"<in-memory:{self._file_name or 'unnamed'}>"

    def __repr__(self) -> str:
        if self._path is not None:
            return f"LocalFile(path='{self._path}', file_name='{self._file_name}')"
        return f"LocalFile(in_memory_bytes={len(self._data or b'')} file_name='{self._file_name}')"
