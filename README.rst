Doxy-SIP
========


Doxy-SIP is a Sphinx plugin providing integration between
Doxygen, the SIP bindings tools and Sphinx.

The itch to scratch
-------------------

When writing Python compiled extensions created in C++ and SIP bindings, options to
write clean and easy documentation that can be integrated in Sphinx-produced web pages
are limited:

* Using Doxygen comments in the C++ code:

    Ddocumenting an API within the C++ source files is very easy and tools such as Breathe. However,
    using tools such as Breathe will produce an API with C++ signature whereas Python
    signatures are different, omit certain C++ objects or add new ones.

* Using Python Docstrings:

    It limits the functionalities and defeats the philosophy of writing documentation
    and code in the same place.

* Manually documenting in RST files:

    Just too tedious.

Doxy-SIP attempts to resolve that by combining Doxygen output and docstring in SIP
specification files to provide clear documentation about the C++ implementation, but with
a Pythonic presentation.

It takes as input:

* A Doxygen output in XML format documenting C++ code.
* A SIP project file (pyproject.toml) defining the bindings for the same C++ code.

It defines a new Sphinx domain (sip) and directives to semi-automatically (à la sphinx.ext.autodoc)
add documentation on objects defined in the bindings specification files.

Installation
------------

Breathe is available from github and PyPI <https://pypi.org/project/doxy-sip/>. It can be installed with::

    pip install doxy-sip

Documentation
-------------

Short documentation - </DOCUMENTATION.rst>.

Requirements
------------

Doxy-SIP requires Python 3.9+, Sphinx 7.2+, Doxygen 1.9.2+ and SIP 6.13+

Acknowledgements
----------------

- Dimitri van Heesch for Doxygen - <https://www.doxygen.nl>.
- Georg Brandl for Sphinx - <https://www.sphinx-doc.org>.
- Phil Thompson for SIP - <https://github.com/Python-SIP/sip>.

