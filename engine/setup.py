"""Builds the `vocab_engine` Python extension from the C++ sources.

    pip install ./engine          # from the repo root
"""
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext = Pybind11Extension(
    "vocab_engine",
    sources=["bindings/python.cpp", "src/fsrs.cpp", "src/comfort.cpp", "src/placement.cpp"],
    include_dirs=["include"],
    cxx_std=17,
)

setup(
    name="vocab-engine",
    version="0.1.0",
    ext_modules=[ext],
    cmdclass={"build_ext": build_ext},
)
