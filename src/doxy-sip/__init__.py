# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>


from sphinx.domains import Domain

from .directives import (
    SIPCurrentModuleDirective,
    SIPModuleDirective,
    SIPClassDirective,
    SIPNamespaceDirective,
    SIPEnumDirective,
    SIPMethodDirective,
    SIPPropertyDirective,
)


__version__ = "0.0.1"


class SIPDomain(Domain):
    name = 'sip'
    label = 'Bindings specification language'
    directives = {
        'currentmodule': SIPCurrentModuleDirective,
        'module' : SIPModuleDirective,
        'class': SIPClassDirective,
        'namespace': SIPNamespaceDirective,
        'enum': SIPEnumDirective,
        'method': SIPMethodDirective,
        'property': SIPPropertyDirective,
    }
    initial_data = {
        'sip_specs': {},
        'sip_dox_index': None,
        'sip_project_loaded': False,
        'sip_current_spec': '',
    }


def setup(app):
    app.add_domain(SIPDomain)
    app.add_config_value('sip_toml_project', '.', 'env', str)
    app.add_config_value('sip_doxygen_project', '.', 'env', str)

    return {
        "version": __version__
    }
