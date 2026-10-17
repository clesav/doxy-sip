Documentation
=============


Getting Started
---------------

This how-to assumes we have a C++ code documented with Doxygen and a SIP project with
specification files (`.sip`) to bind this C++ code in Python.
Doxygen must be configured to produce XML output.


1. Install Doxy-SIP in the Python environment alongside Sphinx:

   .. code-block:: bash

       pip install doxysip

2. Add Doxy-SIP to the list of loaded extensions in the Sphinx ``conf.py`` file:

   .. code-block:: py

          extensions = [
           ...,
           'doxysip',
          ]

3. Add the required parameters in the Sphinx ``conf.py`` file:

   .. code-block:: py

      sip_toml_project = "path/to/sip/project"
      sip_doxygen_project = "path/to/doxygen/xml/output"

4. Start using the doxysip directives in the doc source files to insert object documentation.


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

Notes:

- In the case of functions and methods, the arguments and result descriptions in C++ data (from
  \\param or \\return tags) are kept if no tag is present, and is always placed after the
  function description, regardless of the tag value.
- The docstring is processes as regular reStructuredText content so markup can be used.


Directives
----------

`..sip:specification:: [name]`
******************************

This directive sets the currently loaded SIP module specification. The name must be fully qualified.

Note: It must be used before any other Doxy-SIP directive. All other directives work with the module
loaded using this directive.


`..sip:module::`
****************

This directive inserts the content of the current module docstring.


`..sip:class:: [name]`
**********************

This directive inserts the description for the class defined in the current module.

Options:
   
   `:members`: [filters]
      Insert the documentation of the class members : sub-classes, methods, attributes, etc.
       
      [filters] defines the filtering rules for displaying members. See the dedicated section below.

   `:no-header`:
      If set, the class header (class name, qualifiers and inheritance) is not generated and the content
      for the class members (if generated) is not indented.

   `:no-doc`:
      If set, the class description is not generated.


`..sip:namespace:: [name]`
**************************

Namespaces are implemented by SIP as regular classes. To differentiate them, a ``[namespace]`` tag is added
as prefix to the class signature.

Options are the same as for ``..sip:class::``


`..sip:property:: [name]`
*************************

This directive describes a Python class property.


`..sip:enum:: [name]`
*********************

This directive describes an enumeration class.


`..sip:method:: [name]`
***********************

This directive describes a method.


`..sip:variable:: [name]`
*************************

This directive describes a variable/attribute.


`..sip:macro-constant:: [var_name] [macro_name]`
************************************************

This directive describes a C++ constant defined by a macro, and implemented in Python
as a constant global variable.

**var_name** : Python variable name

**macro_name** (optional): C++ macro name, if different from the Python variable name.


Member filtering
----------------

By defaults, the ``:member:`` option will display class/namespace members that are
*public* and documented (either in Doxygen or in SIP docstrings).
To add other members, filtering flags must be added as::

   :members: [undoc|private|special|all]

The following member filters are define:

- ``undoc`` : if specified, undocumented members will be displayed.
- ``private`` : if specified, private members (i.e. with a Python name starting by an underscore)
  will be displayed.
- ``special`` : if specified, special methods (i.e. with a Python name starting and ending
  with a double underscore) will be displayed.
- ``all`` : if specified, all members will be displayed.

Notes:

* If several flags are specified, they are separated by a comma. Example: ``:members: undoc,private``
* An undocumented private member requires both ``undoc`` and ``private`` to be displayed. Idem for
  an undocumented special method, both ``undoc`` and ``special`` are required.

A special filtering rule applies to constructors when displayed as part of a sip:class directive:

   By default, SIP generates automatically *default* constructors for each class, where possible:
   the no-argument constructor (``Class()``) and the copy constructor
   (C++: ``Class(const Class&)``, Python: ``Class(a0: Class)``).
   
   If the class has only *default* constructors, then they are only displayed if they are documented
   (or the ``undoc`` flag is specified).
   
   If the class has any *non-default* constructors, then all constructors are displayed, whether they're
   documented or not.
