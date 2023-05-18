# Adnuntius Bidder

A simple client for controlling bidding in the Adnuntius platform

## Installation

The simplest way to install the latest production release is via pip
```
pip3 install adnbidder
```

All production (not pre-release) releases from this repository are available in Pypi for installation via pip.
You can select a particular version in pip with the `==` operator, for example `pip3 install adnbidder==1.0.0`

Note that semantic versioning is used for production releases, so major versions indicate incompatible API changes, 
minor versions indication additions to the api, and patch versions indicate backwards compatible bug fixes.

For non-production releases you can download and extract the tarball and use the following commands to install
```
python3 setup.py build
python3 setup.py install
```

## Usage

A good way to get started is to look at `test/example_bidder.py`. 

## Build

`python3 setup.py sdist bdist_wheel`

## [Contact Us](https://adnuntius.com/contact/)
