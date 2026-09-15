Documentation
=============


Getting Started
---------------

This how-to assumes we have a C++ code documented with Doxygen and a SIP project with
specification files (`.sip`) to bind this C++ code in Python.
Doxygen must be configured to produce XML output.


1. Install Doxy-SIP in the Python environment alongside Sphinx:

   .. code-block:: bash

       pip install doxy-sip

2. Add Doxy-SIP to the list of loaded extensions in the Sphinx ``conf.py`` file:

   .. code-block:: py

          extensions = [
           ...,
           'doxy-sip',
          ]

3. Add the required parameters in the Sphinx ``conf.py`` file:

   .. code-block:: py

      sip_toml_project = "path/to/sip/project"
      sip_doxygen_project = "path/to/doxygen/xml/output"

4. Start using the doxy-sip directives in the doc source files to insert object documentation.


Extension configuration options
-------------------------------

**sip_toml_project** :
   This option must contain a path to the directory containing the SIP project ``pyproject.toml``
   that defines the binding modules.

**sip_doxygen_project** :
   This option must contain a path to the directory containing the XML output produced by Doxygen.


Docstring tags
--------------

If description data exists in both C++ and docstrings for the same object,
Doxy-SIP will combine the two according to an optional tag, present in
the first line of the docstring.
This tag does not appear in the final documentation text.

The SIP specification file should look like this::

   %Docstring
       \dox:[prepend|append|discard]
       First line of description
   %End

Tag values:

* `prepend` : the C++ description is added before the docstring content.
* `append` : the C++ description is added after the docstring content.
* `discard` (default) : the C++ data is discarded.

Note 1: In the case of functions and methods, the arguments and result descriptions in C++ data (from
\\param or \\return tags) are kept if no tag is present, and is always placed after the function description,
regardless of the tag value.

Note 2: The docstring is processes as regular reStructuredText content so markup can be used.


Directives
----------

**..sip:currentmodule:: [name]**

   This directive sets the currently loaded SIP module specification. The name must be fully qualified.

   Note: It must be used before any other Doxy-SIP directive. All other directives work with the module
   loaded using this directive.


**..sip:module::**

   This directive inserts the content of the current module docstring.


**..sip:class:: [name]**

   This directive inserts the description for the class defined in the current module.
   
   Options:
   
      `:members`:
         Insert the documentation of the class members : sub-classes, methods, attributes, etc.
        
      `:undoc-members`:
         If set, undocumented members are included. By default they are not excluded.
         Note that this option requires ``:members:`` to be set as well.
      
      `:undoc-slots`:
         By default, Python special functions or "slots" (e.g. `__str__()`) are excluded if undocumented,
         even if ``undoc-members`` is set. If ``undoc-slots`` is set, they are included.
         Note that this option requires ``:members:`` and ``:undoc-members:`` to be set as well.


**..sip:namespace:: [name]**

   Namespaces are implemented by SIP as regular classes. To differentiate them, a ``[namespace]`` tag is added
   as prefix to the class signature.

   Options are the same as for ``..sip:class::``


**..sip:enum:: [name]**

   This directive describes an enumeration class.

   Options are the same as for ``..sip:class::``


**..sip:method:: [name]**

   This directive describes a method.






