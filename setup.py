import pathlib
from setuptools import setup

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()
setup(
    name="adnbidder",
    version="1.0.4",
    description="A simple client for controlling bidding in the Adnuntius platform",
    long_description="A simple client for controlling bidding in the Adnuntius platform",
    url="https://github.com/Adnuntius/adnuntius-bidder",
    author="Adnuntius",
    author_email="tech@adnuntius.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
    ],
    packages=["adnbidder"],
    install_requires=["python-dateutil", "adnuntius"],
)
