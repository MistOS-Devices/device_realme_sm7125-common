#!/usr/bin/env python3
"""Check legacy NV access boundaries before the full Android policy build."""
from pathlib import Path
import re
import unittest

VENDOR = Path(__file__).resolve().parents[1] / 'vendor'


def explicit_permissions(domain, target, kind):
    source = (VENDOR / ('vendor_init.te' if domain == 'vendor_init' else 'rild.te')).read_text()
    matches = re.findall(r'allow\s+' + domain + r'\s+' + target + ':' + kind
                         + r'\s+([^;]+);', source)
    return set(' '.join(matches).replace('{', '').replace('}', '').split())


class RadioPolicyTest(unittest.TestCase):
    def test_init_can_restore_existing_nv_labels(self):
        nv = 'rm_vendor_radio_vendor_data_file'
        self.assertTrue({'getattr', 'relabelto'} <= explicit_permissions('vendor_init', nv, 'file'))
        self.assertIn('relabelto', explicit_permissions('vendor_init', nv, 'dir'))

    def test_radio_can_traverse_cache_without_generic_cache_write(self):
        self.assertEqual(explicit_permissions('rild', 'cache_file', 'dir'), {'search'})
        self.assertFalse(explicit_permissions('rild', 'cache_file', 'file'))

    def test_vendor_properties_have_exact_typed_contexts(self):
        source = (VENDOR / 'property_contexts').read_text()
        for prop in ('vendor.oppo.eng.no', 'vendor.oppo.rffeature'):
            self.assertRegex(source, r'(?m)^' + re.escape(prop)
                             + r'\s+u:object_r:vendor_oppo_radio_prop:s0 exact string$')
        source = (VENDOR / 'rild.te').read_text()
        self.assertNotRegex(source, r'\b(?:default_prop|system_prop)\b')


if __name__ == '__main__':
    unittest.main()
