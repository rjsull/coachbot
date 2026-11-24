"""Legacy install shim for pip/setuptools versions without PEP 621 support.

Metadata mirrors pyproject.toml so `python setup.py develop` works offline.
"""

from setuptools import find_packages, setup

setup(
    name="coachbot",
    version="0.1.0",
    description="Deterministic training and nutrition plan tracker",
    packages=find_packages(exclude=("tests",)),
    python_requires=">=3.9",
    entry_points={"console_scripts": ["coachbot = coachbot.cli:main"]},
)
