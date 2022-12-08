# Apache Pony Mail Unit Tests Repository

The aim of this repository is to create a comprehensive suite of tests for ensuring 
that changes to the Pony Mail codebase does not impact stability and reproducibility.

The repository is split into three main directories:

- `tests/`: The python test scripts
- `yaml/`: The test specifications
- `corpus/`: The test corpus (data input to be used during tests)

The root directory has a `runall.py`, which will run all tests it can find in the 
yaml directory, and summarize the results at the end. You may also run individual 
tests from the tests directory (more on that as we build out the test dir).

CLI args for `runall.py`:
- `--rootdir`: The root filepath of your Apache Pony Mail installation to test against
- `--fof`: Fail if one test fails, exiting the suite
- `--load [filename]`: Only load a specific yaml test specification, don't run all tests

Environment variables:
- `PYTHONHASHSEED=0`: this ensures that Sets etc return their entries in a deterministic order
- `MOCK_GMTIME=0`: override time.gmtime() to use the value '0' if none is provided
- `MOCK_AAT=0`: override archived-at datetimes to unix epoch. Used for certain medium generator tests
  
The above variables are useful for some tests to ensure reproducability.
However using them may mask bugs in the code, so they should only be used where necessary.

Alternate values for some tests
===============================
Version 0.10 of Ponymail never detects format=flowed mails.
This is because the content-type entry was not set up in msg_metadata
As a consequence, some mails will be parsed differently.
The test scripts allow for an alternate value for some tests, shown as v0.10.

PLEASE NOTE
===========
In order to test the use of optional dependencies, the code in this repository requires
the use of 3rd party codes which do not have licences compatible with the Apache Licence 2.0
