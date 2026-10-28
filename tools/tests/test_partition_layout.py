"""Evaluate the real BoardConfig with both camera choices and device layouts."""
from pathlib import Path
import subprocess
import tempfile
import unittest

COMMON = Path(__file__).resolve().parents[2]
MIB = 1024 * 1024


class PartitionLayoutTest(unittest.TestCase):
    def layout(self, device, camera=None, rom_reserve=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('device/qcom/sepolicy_vndr/SEPolicy.mk',
                         'device/lineage/sepolicy/libperfmgr/sepolicy.mk',
                         'device/lineage/sepolicy/libion/sepolicy.mk'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            if rom_reserve is not None:
                path = root / 'vendor/lineage/config/BoardConfigReservedSize.mk'
                path.parent.mkdir(parents=True)
                path.write_text(f'BOARD_ODMIMAGE_PARTITION_RESERVED_SIZE := {rom_reserve}\n'
                                f'BOARD_VENDORIMAGE_PARTITION_RESERVED_SIZE := {rom_reserve}\n')
            feature = '' if camera is None else f'TARGET_INCLUDE_OPLUS_CAMERA := {camera}\n'
            (root / 'Makefile').write_text(
                '.DEFAULT_GOAL := snapshot\n'
                f'TARGET_DEVICE := {device}\n' + feature +
                f'include {COMMON / "BoardConfigCommon.mk"}\n'
                'snapshot:\n\t@echo $(BOARD_SUPER_PARTITION_SIZE) '
                '$(BOARD_QTI_DYNAMIC_PARTITIONS_SIZE) '
                '$(BOARD_ODMIMAGE_PARTITION_RESERVED_SIZE) '
                '$(BOARD_VENDORIMAGE_PARTITION_RESERVED_SIZE)\n')
            output = subprocess.check_output(['make', '--no-print-directory', '-s'], cwd=root, text=True)
            return tuple(map(int, output.split()))

    def test_rmx2061_geometry_is_correct_with_either_camera(self):
        for feature, reserve in (('true', 128 * MIB), ('false', 500 * MIB)):
            with self.subTest(camera=feature):
                self.assertEqual(self.layout('RMX2061', feature),
                                 (7804 * MIB, 7800 * MIB, reserve, reserve))

    def test_camera_padding_applies_after_rom_reserve_defaults(self):
        self.assertEqual(self.layout('RMX2061', 'true', 500 * MIB)[2:], (128 * MIB, 128 * MIB))
        self.assertEqual(self.layout('RMX2061', 'false', 256 * MIB)[2:], (256 * MIB, 256 * MIB))

    def test_other_device_keeps_its_existing_geometry(self):
        self.assertEqual(self.layout('RMX2170'),
                         (8084 * MIB, 8080 * MIB, 500 * MIB, 500 * MIB))


if __name__ == '__main__':
    unittest.main()
