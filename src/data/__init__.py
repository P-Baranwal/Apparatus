import os
from importlib import import_module

_impl = import_module("data.mock" if os.getenv("USE_MOCK") == "1" else "data.real")


def __getattr__(name):
    return getattr(_impl, name)
