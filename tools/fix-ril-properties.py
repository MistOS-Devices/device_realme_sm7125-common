#!/usr/bin/env python3
"""Namespace the two legacy properties in the verified RMX2061 RIL blobs."""
import hashlib
from pathlib import Path
import sys

# Stock blob and the same blob with the existing null-instance guard applied.
SUPPORTED_SHA256 = {
    '1736ff26a7e487dc8f22cf7653e9d82d737cc7dbb93b7c3f77593e377ad5be64',
    '0d14d71f3ca95069d893fd748c14536310e9542cd7cc2e204e02f37f40fde376',
    'ffcefff1c2450da3456a9378f6e1d7f12d0ee8931c5c1b08e14bd2604bba525b',
}
PROPERTIES = (
    (b'oppo.eng.factory.no\0', b'vendor.oppo.eng.no\0'),
    (b'sys.oppo.network.rffeature\0', b'vendor.oppo.rffeature\0'),
)


def patch(data):
    original = data
    for old, new in PROPERTIES:
        original = original.replace(new.ljust(len(old), b'\0'), old)
    if hashlib.sha256(original).hexdigest() not in SUPPORTED_SHA256:
        raise ValueError('unsupported RIL blob; refusing an unverified binary patch')
    result = original
    for old, new in PROPERTIES:
        if len(new) > len(old) or original.count(old) != 1:
            raise ValueError('expected radio property string is not unique or does not fit')
        result = result.replace(old, new.ljust(len(old), b'\0'))
    return result


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: fix-ril-properties.py LIBRIL_QC_HAL_QMI_SO')
    path = Path(sys.argv[1])
    try:
        data = path.read_bytes()
        updated = patch(data)
        if updated != data:
            path.write_bytes(updated)
    except (OSError, ValueError) as error:
        sys.exit(str(error))
