import sys

from setuptools import setup, find_packages

with open("requirements.txt") as fp:
    requirements = fp.read()


def setup_package():
    needs_sphinx = {"build_sphinx", "upload_docs"}.intersection(sys.argv)
    sphinx = ["sphinx"] if needs_sphinx else []
    setup(
        setup_requires=["six"] + sphinx,
        packages=find_packages(),
        include_package_data=True,
        install_requires=requirements,
    )


if __name__ == "__main__":
    setup_package()
