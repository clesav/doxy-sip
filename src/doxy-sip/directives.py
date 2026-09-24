# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>


from sphinx.directives import SphinxDirective
from sphinx.util.docutils import switch_source_input
from sphinx.util.parsing import nested_parse_to_nodes
from docutils.statemachine import StringList
from docutils.parsers.rst import directives
from sphinx.util import logging
from sphinx import addnodes
from sphinx.domains.python import PyObject
from . import sip_struct
from . import dox_struct
from . import combiner


LOGGER = logging.getLogger('doxy-sip')


def _yield_indented_lines(lines, indent):
    for line in lines:
        if line.strip():
            yield indent + line
        else:
            yield ""


def _add_lines_to_result(lines, result, indent):
    for line in lines:
        if line.strip():
            result.append(indent + line)
        else:
            result.append('')


def _render_docstring(docstring):
    if docstring is None:
        return []
    s = docstring if isinstance(docstring, str) else docstring.text
    s = s.strip(' \n')
    return [s]


def _parse_generated_content(state, lines):
    if not lines:
        return []

    content = StringList(lines)
    with switch_source_input(state, content):
        return nested_parse_to_nodes(state, content)


class SIPSpecificationDirective(SphinxDirective):

    has_content = True
    required_arguments = 1

    def run(self):
        mod_name = self.arguments[0]
        sip_data = self.env.domaindata['sip']
        sip_project_dir = self.env.app.config.sip_toml_project
        try:
            sip_spec = sip_struct.get_sip_spec(sip_data, sip_project_dir, mod_name)
            self.env.domaindata['sip']['sip_current_spec'] = sip_spec

            mod_lines = [
                '.. py:currentmodule:: ' + sip_spec.module.fq_py_name.name,
                ''
            ]

            return _parse_generated_content(self.state, mod_lines)

        except sip_struct.UserException as e:
            text = '\n  '.join(e.text.split('\n'))
            msg = f'SIP errors while parsing spec file for module "{mod_name}":\n  {text}'
            raise self.error(msg) from None

        except Exception as e:
            msg = f'Error while reading spec file for module "{mod_name}"'
            raise self.error(msg) from e


class _SIPDirective(SphinxDirective):

    has_content = True

    def _generate_error(self, message):
        lines = [
            ".. error::",
            "",
            f"   `{self.name}`: {message}",
            "",
        ]

        nodes = _parse_generated_content(self.state, lines)
        return nodes


    def _get_loaded_spec(self):
        self.sip_spec = self.env.domaindata['sip']['sip_current_spec']
        if not self.sip_spec:
            return self._generate_error("A SIP directive should be preceded by a `sip:currentmodule` directive.")
        else:
            return None


    def _find_matching_dox_class(self, sip_klass, kind):
        kinds = []
        if kind in ('any', 'class_like'):
            kinds.extend(('class', 'struct', 'union'))
        if kind in ('any', 'namespace'):
            kinds.append('namespace')

        #Use the class C++ name, with the global scope stripped
        klass_fq_cpp_name = sip_klass.iface_file.fq_cpp_name.cpp_stripped(-1)
        dox_klass = dox_struct.get_dox_class(self.env.domains['sip'], klass_fq_cpp_name, kinds)
        return dox_klass


class SIPModuleDirective(_SIPDirective):

    required_arguments = 0

    def run(self):
        #Get the currently loaded SIP specification
        if err_nodes := self._get_loaded_spec():
            return err_nodes

        sip_mod = self.sip_spec.module

        mod_lines = [
            '.. py:module:: ' + sip_mod.fq_py_name.name,
            ''
        ]

        LOGGER.debug('SIP - Loaded module ' + sip_mod.fq_py_name.name)

        if len(self.content):
            _add_lines_to_result(self.content.data, mod_lines, '   ')
        elif sip_mod.docstring is not None:
            docstring_lines = sip_struct.render_docstring(sip_mod.docstring)
            _add_lines_to_result(docstring_lines, mod_lines, '   ')

        nodes = _parse_generated_content(self.state, mod_lines)

        return nodes


class _AutoDirectiveOptions:

    OPTION_SPEC = {
        'members': directives.flag,
        'undoc-members': directives.flag,
        'undoc-slots': directives.flag,
    }

    def __init__(self, options):
        self.do_members = 'members' in options
        self.do_undoc_members = self.do_members and 'undoc-members' in options
        self.do_undoc_slots = self.do_undoc_members and 'undoc-slots' in options



class _AutoDirective(_SIPDirective):

    has_content = True

    option_spec = _AutoDirectiveOptions.OPTION_SPEC

    def run(self):
        source, lineno = self.get_source_info()
        LOGGER.debug('[doxy-sip] %s:%s: input:\n%s', source, lineno, self.block_text)

        #Get the currently loaded SIP specification
        if err_nodes := self._get_loaded_spec():
            return err_nodes

        self.sip_options = _AutoDirectiveOptions(self.options)

        return self.run_sip_directive()


    def _run_sip_directive(self):
        raise NotImplementedError


    def _generate_class(self, sip_klass, dox_klass):
        klass_lines = []
        klass_lines.extend(self._generate_class_header(sip_klass))

        #Add the class description by combining the doxygen description and the SIP docstring
        _, klass_description = combiner.merge_description(sip_klass.docstring, dox_klass)
        if klass_description:
            _add_lines_to_result(klass_description, klass_lines, "   ")
            klass_lines.append("")

        if not self.sip_options.do_members:
            return klass_lines

        #Add the sub-classes
        sub_classes = [ c for c in self.sip_spec.classes if c.scope == sip_klass ]
        sub_enums = [ e for e in self.sip_spec.enums if e.scope == sip_klass ]
        if sub_classes or sub_enums:
            klass_lines.append("   **Sub-types**:")
            klass_lines.append("")

            for sc in sub_classes:
                subklass_fq_cpp_name = sc.iface_file.fq_cpp_name.cpp_stripped(-1)
                dox_subklass = dox_struct.get_dox_class(self.env.domains['sip'],
                                                        subklass_fq_cpp_name,
                                                        ('class', 'struct', 'union'))
                subklass_lines = self._generate_class(sc, dox_subklass)
                subklass_lines.append("")
                _add_lines_to_result(subklass_lines, klass_lines, "      ")

            #Add the enumerations
            for se in sub_enums:
                decl = combiner.combine_class_enum(se, dox_klass)
                enum_lines = list(self._generate_enum(decl))
                enum_lines.append("")
                _add_lines_to_result(enum_lines, klass_lines, "      ")

        #Add the constructors
        ctor_lines = list(self._generate_constructors(sip_klass, dox_klass))
        _add_lines_to_result(ctor_lines, klass_lines, "   ")

        #Add the methods
        method_lines = list(self._generate_methods(sip_klass, dox_klass))
        _add_lines_to_result(method_lines, klass_lines, "   ")

        #Add the properties
        property_lines = list(self._generate_properties(sip_klass))
        _add_lines_to_result(property_lines, klass_lines, "   ")

        #Add the variables
        var_lines = list(self._generate_class_attributes(sip_klass, dox_klass))
        _add_lines_to_result(var_lines, klass_lines, "   ")

        return klass_lines


    def _generate_class_header(self, sip_klass):
        klass_scoped_py_name = sip_struct.get_scoped_py_name(sip_klass)
        yield f".. py:class:: {klass_scoped_py_name}"

        if sip_klass.is_abstract:
            yield "   :abstract:"
        yield ""

        supers = sip_struct.render_superclasses(self.sip_spec, sip_klass)
        if supers:
            yield "   **inherits** " + " , ".join(f":py:class:`{sc}`" for sc in supers)
            yield ""


    def _generate_enum(self, decl):
        yield ".. py:class:: " + decl.signature
        yield ""
        if decl.description:
            yield from _yield_indented_lines(decl.description, "   ")
            yield ""
        yield "   **Enumeration values:**"
        yield ""
        for name, desc in decl.members:
            yield "   .. py:attribute:: " + name
            yield ""
            if desc is not None:
                yield from _yield_indented_lines(desc, "      ")
                yield ""


    def _generate_constructors(self, sip_klass, dox_klass):
        ctor_decl_list = combiner.combine_constructors(self.sip_spec, sip_klass, dox_klass)

        if ctor_decl_list:
            yield "**Constructors**:"
            yield ""

        for ctor_desc in ctor_decl_list:

            if not ctor_desc.ctor_default and not self.sip_options.do_undoc_members:
                continue

            yield "   .. py:method:: " + ctor_desc.signature
            yield ""

            if ctor_desc.description:
                yield from _yield_indented_lines(ctor_desc.description, "      ")
                yield ""

            if ctor_desc.arguments is not None:
                for arg_name, arg_desc in ctor_desc.arguments:
                    param_line = f"      :param {arg_name}:"
                    if arg_desc:
                        param_line += f" {arg_desc}"
                    yield param_line
                yield ""


    def _generate_methods(self, sip_klass, dox_klass):
        first = True
        for sip_member in reversed(sip_klass.members):
            member = sip_struct.SIP_Callable(self.sip_spec, sip_klass, sip_member)

            overload_declarations = []
            for overload in member.overloads:
                fct_decl = combiner.combine_overload_declaration(self.sip_spec, overload, dox_klass)

                if not fct_decl.description and not self.sip_options.do_undoc_members:
                    continue

                if overload.py_slot and not fct_decl.description and not self.sip_options.do_undoc_slots:
                    continue

                if first:
                    first = False
                    yield "**Methods**:"
                    yield ""

                yield "   .. sip:method:: " + fct_decl.signature

                if overload.is_static:
                    yield "      :staticmethod:"

                qualifiers = []
                if overload.is_virtual:
                    qualifiers.append('virtual')
                if overload.is_abstract:
                    qualifiers.append('abstract')
                if qualifiers:
                    yield "      :qualifiers: " + ','.join(qualifiers)

                yield ""

                if fct_decl.description:
                    yield from _yield_indented_lines(fct_decl.description, "      ")
                    yield ""

                if fct_decl.arguments is not None:
                    for arg_name, arg_desc in fct_decl.arguments:
                        param_line = f"      :param {arg_name}:"
                        if arg_desc is not None:
                            param_line += " " + arg_desc
                        if arg_desc or not overload.py_slot:
                            yield param_line

                if fct_decl.result:
                    yield "      :return: " + fct_decl.result

                yield ""


    def _generate_properties(self, sip_klass):
        if len(sip_klass.properties):
            yield "**Properties**:"
            yield ""
            for p in sip_klass.properties:
                yield from self._generate_property(sip_klass, p)


    def _generate_property(self, sip_klass, sip_prop):
        decl = combiner.combine_property_declaration(self.sip_spec, sip_klass, sip_prop)
        yield f".. py:property:: {decl.name}"
        if decl.type_:
            yield f"   :type: {decl.type_}"
        yield ""
        if decl.description:
            yield from _yield_indented_lines(decl.description, "   ")
            yield ""


    def _generate_class_attributes(self, sip_klass, dox_klass):
        klass_vars_decl = combiner.combine_class_variable_declaration(self.sip_spec, sip_klass, dox_klass)

        if klass_vars_decl:
            yield "**Attributes**:"
            yield ""

        indent = " " * 3
        for v_name, v_type, v_desc in klass_vars_decl:
            yield indent + ".. py:attribute:: " + v_name
            yield indent * 2 + ":type: " + v_type
            yield ""
            if v_desc:
                yield from _yield_indented_lines(v_desc, indent * 2)
                yield ""


class SIPClassDirective(_AutoDirective):
    '''Directive to document a class.
    '''

    required_arguments = 1

    def run_sip_directive(self):

        klass_name = self.arguments[0]

        #Get the wrapped class object from the specification
        sip_klass = sip_struct.find_sip_klass(self.sip_spec, klass_name)
        if sip_klass is None or sip_klass.class_key is None:
            return self._generate_error(f'No class {klass_name} in SIP spec')

        dox_klass = self._find_matching_dox_class(sip_klass, 'class_like')

        klass_lines = self._generate_class(sip_klass, dox_klass)

        _add_lines_to_result(self.content.data, klass_lines, "   ")

        nodes = _parse_generated_content(self.state, klass_lines)

        return nodes


class SIPNamespaceDirective(_AutoDirective):
    '''Directive to document a namespace.
    Namespace in SIP bindings are just classes so we generate the nodes just like a class.
    Simply to denote the difference, we tweak in the resulting nodes to insert a
    qualifier "[namespace]" before the first content node (which is the "class" keyword)
    '''

    required_arguments = 1

    def run_sip_directive(self):

        ns_name = self.arguments[0]

        sip_NS = sip_struct.find_sip_klass(self.sip_spec, ns_name)
        if sip_NS is None or sip_NS.class_key is not None:
            return self._generate_error(f'No namespace {ns_name} in SIP spec')

        dox_NS = self._find_matching_dox_class(sip_NS, 'namespace')

        lines = self._generate_class(sip_NS, dox_NS)

        nodes = _parse_generated_content(self.state, lines)

        node_desc_sig = nodes[1][0]
        assert isinstance(node_desc_sig, addnodes.desc_signature)

        node_desc_sig.insert(0, addnodes.desc_annotation(text='[namespace]'))

        return nodes


class SIPEnumDirective(_AutoDirective):
    '''Directive to document a global enumeration.
    '''

    required_arguments = 1

    def run_sip_directive(self):

        enum_name = self.arguments[0]

        #Get the wrapped class object from the specification
        sip_enum = sip_struct.find_sip_enum(self.sip_spec, enum_name)
        if sip_enum is None:
            return self._generate_error(f'No enumeration {enum_name} in SIP spec')

        enum_fq_cpp_name = sip_enum.fq_cpp_name.cpp_stripped(-1)
        dox_enum = dox_struct.get_dox_enum(self.env.domains['sip'], enum_fq_cpp_name)
        decl = combiner.combine_enum(sip_enum, dox_enum)
        enum_lines = list(self._generate_enum(decl))

        _add_lines_to_result(self.content.data, enum_lines, "   ")

        nodes = _parse_generated_content(self.state, enum_lines)

        return nodes


class SIPPropertyDirective(_AutoDirective):
    '''Directive to document a property.
    '''

    required_arguments = 1

    def run_sip_directive(self):

        prop_name = self.arguments[0]

        #Get the wrapped class object from the specification
        sip_klass, sip_prop = sip_struct.find_sip_property(self.sip_spec, prop_name)
        if sip_prop is None:
            return self._generate_error(f'No class property {prop_name} in SIP spec')

        lines = list(self._generate_property(sip_klass, sip_prop))

        _add_lines_to_result(self.content.data, lines, "   ")

        nodes = _parse_generated_content(self.state, lines)

        return nodes


_QUALIFIERS = ['abstract', 'virtual']

def _qualifier_converter(opt_value):
    qual_list = [ v.strip() for v in opt_value.split(',')]
    if any(v not in _QUALIFIERS for v in qual_list):
        return None
    return qual_list


class SIPMethodDirective(SphinxDirective):

    required_arguments = 1
    final_argument_whitespace = True
    has_content = True

    #Inherit all the options from PyObject, and add :qualifiers:
    option_spec = PyObject.option_spec
    option_spec.update({
        'qualifiers': _qualifier_converter,
    })

    def run(self):

        lines = [".. py:method:: " + self.arguments[0], ""]
        _add_lines_to_result(self.content.data, lines, "   ")

        nodes = _parse_generated_content(self.state, lines)

        qualifiers = self.options.get('qualifiers', None)
        if not qualifiers:
            return nodes

        node_desc_sig = nodes[1][0]
        assert isinstance(node_desc_sig, addnodes.desc_signature)

        node_desc_sig.insert(0, addnodes.desc_sig_space())

        qual_text = '[' + ' , '.join(qualifiers) + ']'
        node_desc_sig.insert(0, addnodes.desc_annotation(text=qual_text))

        return nodes
