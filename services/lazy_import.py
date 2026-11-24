"""Pembungkus import lambat agar pustaka berat hanya dimuat saat dipakai."""

import importlib


class LazyModule:
    """Modul yang baru diimpor ketika atributnya pertama kali diakses."""

    __slots__ = ("_name", "_module")

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_module", None)

    def _load(self):
        module = object.__getattribute__(self, "_module")
        if module is None:
            name = object.__getattribute__(self, "_name")
            if name == "fitz":
                # PyMuPDF 2.x memakai nama "pymupdf"; "fitz" hanya alias lama.
                try:
                    module = importlib.import_module("pymupdf")
                except ImportError:
                    module = importlib.import_module("fitz")
            else:
                module = importlib.import_module(name)
            object.__setattr__(self, "_module", module)
        return module

    def __getattr__(self, item):
        return getattr(self._load(), item)
