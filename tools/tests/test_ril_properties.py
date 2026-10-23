#!/usr/bin/env python3
"""Verify that only the two legacy radio property strings change."""
import importlib.util
from pathlib import Path
import sys

script = Path(__file__).resolve().parents[1] / 'fix-ril-properties.py'
spec = importlib.util.spec_from_file_location('fix_ril_properties', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = Path(sys.argv[1]).read_bytes()
updated = module.patch(original)
assert updated != original and len(updated) == len(original)
expected = original
for old, new in module.PROPERTIES:
    assert len(new) <= len(old) and original.count(old) == 1
    expected = expected.replace(old, new.ljust(len(old), b'\0'))
assert updated == expected
assert module.patch(updated) == updated
for invalid in (original + b'x', updated + b'x', b'not an ELF'):
    try:
        module.patch(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('unrecognized blob was accepted')
print('PASS: RIL property replacement preserves offsets, is idempotent and rejects unknown blobs')
