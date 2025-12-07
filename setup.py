import os
from pathlib import Path

from setuptools import find_packages, setup


def read_long_description():
    readme_path = Path(__file__).parent / "README.md"
    with readme_path.open(encoding="utf-8") as fh:
        return fh.read()


setup(
    name="daplug-core",
    version=os.getenv("CIRCLE_TAG", "0.1.0"),
    url="https://github.com/dual/daplug-core",
    author="Paul Cruse III",
    author_email="paulcruse3@gmail.com",
    description="Shared schema, merge, and SNS helpers powering daplug adapters.",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["daplug_core", "daplug_core.*"]),
    python_requires=">=3.10",
    install_requires=[
        "boto3>=1.42.4,<2; python_version >= '3.9'",
        "jsonref>=1.1.0,<2; python_version >= '3.7'",
        "simplejson>=3.20.2,<4; python_version >= '2.5' and python_version not in '3.0, 3.1, 3.2'",
        "pyyaml>=6.0.3,<7; python_version >= '3.8'",
    ],
    keywords=[
        "daplug",
        "schema",
        "sns",
        "event-driven",
        "database",
        "adapter",
        "python-library",
    ],
    project_urls={
        "Homepage": "https://github.com/dual/daplug-core",
        "Documentation": "https://github.com/dual/daplug-core#readme",
        "Source Code": "https://github.com/dual/daplug-core",
        "Bug Reports": "https://github.com/dual/daplug-core/issues",
        "CI/CD": "https://circleci.com/gh/dual/daplug-core",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Database :: Front-Ends",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
    ],
    license="Apache License 2.0",
    platforms=["any"],
    zip_safe=False,
)
