#!/usr/bin/env python3
"""Exercise the production ZRAM boot block against a temporary sysfs tree."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'bin/init.qcom.post_boot.sh'


class ZramBootTest(unittest.TestCase):
    def run_boot(self, *, active=False, initialized=False, disksize_fails=False,
                 format_fails=False, secondary=True, secondary_fails=False, memory_kb=7723852):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            zram = root / 'sys/block/zram0'
            zram.mkdir(parents=True)
            (root / 'proc/sys/vm').mkdir(parents=True)
            (root / 'proc/meminfo').write_text(f'MemTotal:       {memory_kb:8d} kB\n')
            (root / 'proc/swaps').write_text('Filename Type Size Used Priority\n' +
                ('/dev/block/zram0 partition 4194300 42 32758\n' if active else ''))
            (zram / 'comp_algorithm').write_text('lzo [lz4] zstd\n')
            if secondary:
                (zram / 'recomp_algorithm').write_text('')
            (zram / 'use_dedup').write_text('0\n')
            (zram / 'initstate').write_text('1\n' if initialized else '0\n')
            disk = zram / 'disksize'
            disk.write_text('4294967296\n' if initialized else '0\n')
            lmk = root / 'sys/module/lowmemorykiller/parameters'
            lmk.mkdir(parents=True)
            calls = root / 'calls'
            source = SCRIPT.read_text().split('function configure_memory_parameters() {', 1)[1]
            source = source.split('    # Configure Low Memory Killer parameters', 1)[0]
            for prefix in ('/sys/', '/proc/', '/dev/block/'):
                source = source.replace(prefix, str(root) + prefix)
            prelude = f'''echo() {{
    if [ "$*" = "algo=zstd priority=1" ]; then
        [ "$(cat "{disk}")" = 0 ] || return 1
        [ {1 if secondary_fails else 0} = 0 ] || return 1
    fi
    if [ "$*" = 4294967296 ] && [ {1 if disksize_fails else 0} = 1 ]; then
        return 1
    fi
    builtin echo "$@"
}}
\ngetprop() {{ :; }}
mkswap() {{ echo mkswap >> "{calls}"; return {1 if format_fails else 0}; }}
swapon() {{ echo swapon >> "{calls}"; }}
configure_memory_parameters() {{
'''
            result = subprocess.run(['bash', '-c', prelude + source + '\n}\nconfigure_memory_parameters'],
                                    capture_output=True, text=True)
            values = {p.name: p.read_text().strip() for p in zram.iterdir()
                      if p.is_file() and not p.is_symlink()}
            return result.returncode, values, calls.read_text().splitlines() if calls.exists() else []

    def test_secondary_selected_before_initialization(self):
        status, values, calls = self.run_boot()
        self.assertEqual(status, 0)
        self.assertEqual(values['comp_algorithm'], 'lz4')
        self.assertEqual(values['recomp_algorithm'], 'algo=zstd priority=1')
        self.assertEqual(values['use_dedup'], '0')
        self.assertEqual(values['disksize'], '4294967296')
        self.assertEqual(calls, ['mkswap', 'swapon'])

    def test_active_swap_is_not_reconfigured_or_formatted(self):
        status, values, calls = self.run_boot(active=True, initialized=True)
        self.assertEqual(status, 0)
        self.assertEqual(values['comp_algorithm'], 'lzo [lz4] zstd')
        self.assertEqual(values['recomp_algorithm'], '')
        self.assertEqual(calls, [])

    def test_initialized_inactive_device_is_not_formatted(self):
        _, values, calls = self.run_boot(initialized=True)
        self.assertEqual(values['comp_algorithm'], 'lzo [lz4] zstd')
        self.assertEqual(calls, [])

    def test_disksize_failure_prevents_format_and_activation(self):
        status, _, calls = self.run_boot(disksize_fails=True)
        self.assertNotEqual(status, 0)
        self.assertEqual(calls, [])

    def test_format_failure_prevents_activation(self):
        status, _, calls = self.run_boot(format_fails=True)
        self.assertNotEqual(status, 0)
        self.assertEqual(calls, ['mkswap'])

    def test_secondary_interface_absent_keeps_primary_swap(self):
        status, values, calls = self.run_boot(secondary=False)
        self.assertEqual(status, 0)
        self.assertEqual(values['comp_algorithm'], 'lz4')
        self.assertEqual(calls, ['mkswap', 'swapon'])

    def test_secondary_failure_keeps_primary_swap(self):
        status, values, calls = self.run_boot(secondary_fails=True)
        self.assertEqual(status, 0)
        self.assertEqual(values['comp_algorithm'], 'lz4')
        self.assertEqual(calls, ['mkswap', 'swapon'])

    def test_existing_ram_capacity_tiers_are_preserved(self):
        for memory, size in ((3800000, 2684354560), (5800000, 3221225472),
                             (7723852, 4294967296), (11500000, 5368709120)):
            with self.subTest(memory=memory):
                _, values, _ = self.run_boot(memory_kb=memory)
                self.assertEqual(values['disksize'], str(size))


if __name__ == '__main__':
    unittest.main()
