from importlib import import_module

_impl = import_module("data.real")


def __getattr__(name):
    return getattr(_impl, name)
