from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="renutil",
    version="0.2.0",
    description="A toolkit for managing Ren'Py instances via the command line.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kobaltcore/renutil",
    author="cobaltcore",
    author_email="cobaltcore@yandex.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="build renpy visual-novel packaging deployment toolkit",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    install_requires=["requests", "lxml", "semantic_version", "jsonpickle", "tqdm"],
    python_requires=">=3",
    entry_points={
        "console_scripts": [
            "renutil=renutil.renutil:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/kobaltcore/renutil/issues",
        "Source": "https://github.com/kobaltcore/renutil",
    },
)
