#!/usr/bin/env python3
"""Validate the effects graph and Dolby UUIDs against the supplied blobs."""
import os
from pathlib import Path
import struct
import unittest
import uuid
import xml.etree.ElementTree as ET

DEVICE = Path(__file__).resolve().parents[2]
DOLBY = Path(os.environ.get('DOLBY_PATH', DEVICE.parents[2] / 'hardware/dolby'))
NS = {'a': 'http://schemas.android.com/audio/audio_effects_conf/v2_0'}


class AudioEffectsTest(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(DEVICE / 'audio/vendor/audio_effects.xml').getroot()

    def test_effect_graph_is_unambiguous(self):
        for section in ('libraries', 'effects'):
            names = [e.get('name') for e in self.root.find('a:' + section, NS)]
            self.assertEqual(len(names), len(set(names)), section)
        libraries = {e.get('name') for e in self.root.find('a:libraries', NS)}
        effects = {e.get('name') for e in self.root.find('a:effects', NS)}
        self.assertIn('dap', effects)
        for e in self.root.iter():
            if e.get('library'):
                self.assertIn(e.get('library'), libraries)
            if e.get('effect'):
                self.assertIn(e.get('effect'), effects)
        for section in ('postprocess', 'preprocess'):
            for stream in self.root.find('a:' + section, NS):
                self.assertTrue(all(e.tag == '{' + NS['a'] + '}apply' for e in stream),
                                'streams cannot contain nested streams')

    def test_dolby_effects_match_installed_blob_uuids(self):
        libraries = {e.get('name'): e.get('path')
                     for e in self.root.find('a:libraries', NS)}
        for effect in self.root.find('a:effects', NS):
            library = effect.get('library')
            if library not in {'dap', 'dvl', 'gamedap', 'vqe', 'spatializer'}:
                continue
            with self.subTest(effect=effect.get('name')):
                value = uuid.UUID(effect.get('uuid'))
                encoded = struct.pack('<IHHH', value.time_low, value.time_mid,
                                      value.time_hi_version,
                                      value.clock_seq_hi_variant << 8 | value.clock_seq_low)
                blob = DOLBY / 'proprietary/vendor/lib64/soundfx' / libraries[library]
                self.assertTrue(encoded + value.bytes[10:] in blob.read_bytes(),
                                f'{effect.get("uuid")} is not provided by {blob.name}')

    def test_stock_odm_effects_do_not_shadow_vendor(self):
        self.assertFalse((DEVICE / 'audio/odm/audio_effects.xml').exists())

    def test_all_shipped_dolby_descriptors_are_registered(self):
        libraries = {e.get('name'): e.get('path')
                     for e in self.root.find('a:libraries', NS)}
        registered = set()
        for effect in self.root.find('a:effects', NS):
            value = uuid.UUID(effect.get('uuid'))
            encoded = struct.pack('<IHHH', value.time_low, value.time_mid,
                                  value.time_hi_version,
                                  value.clock_seq_hi_variant << 8 | value.clock_seq_low)
            registered.add((libraries[effect.get('library')], encoded + value.bytes[10:]))
        found = 0
        for blob in (DOLBY / 'proprietary/vendor/lib64/soundfx').glob('*.so'):
            data = blob.read_bytes()
            offset = 0
            while True:
                offset = data.find(b'\x00\x00\x02\x00', offset)
                if offset < 0:
                    break
                start = offset - 32
                offset += 1
                if start < 0 or start + 172 > len(data):
                    continue
                descriptor = data[start:start + 172]
                name = descriptor[44:108].split(b'\x00')[0]
                maker = descriptor[108:172].split(b'\x00')[0]
                if not name or b'Dolby' not in maker:
                    continue
                if not all(32 <= c < 127 for c in name + maker):
                    continue
                found += 1
                self.assertIn((blob.name, descriptor[16:32]), registered,
                              f'{blob.name}: {name.decode()} is missing from the effects config')
        self.assertGreaterEqual(found, 9, 'Expected all nine inspected Dolby descriptors')

    def test_dolby_volume_listeners_are_attached(self):
        for stream in ('music', 'ring', 'alarm', 'system', 'notification'):
            node = self.root.find(f"a:postprocess/a:stream[@type='{stream}']", NS)
            self.assertIsNotNone(node, stream)
            self.assertIn('dlb_' + stream + '_listener',
                          [e.get('effect') for e in node], stream)

    def test_spatializer_output_is_routed(self):
        policy = ET.parse(DEVICE / 'audio/vendor/audio_policy_configuration.xml').getroot()
        primary = policy.find("modules/module[@name='primary']")
        port = primary.find("mixPorts/mixPort[@name='immersive_out']")
        self.assertIn('AUDIO_OUTPUT_FLAG_SPATIALIZER', port.get('flags').split('|'))
        sinks = {route.get('sink') for route in primary.findall('routes/route')
                 if 'immersive_out' in route.get('sources', '').split(',')}
        for device in primary.findall('devicePorts/devicePort'):
            if device.get('type') in {'AUDIO_DEVICE_OUT_SPEAKER',
                                      'AUDIO_DEVICE_OUT_WIRED_HEADSET',
                                      'AUDIO_DEVICE_OUT_WIRED_HEADPHONE',
                                      'AUDIO_DEVICE_OUT_USB_DEVICE',
                                      'AUDIO_DEVICE_OUT_USB_HEADSET'}:
                self.assertIn(device.get('tagName'), sinks)

    def test_stock_dolby_blobs_are_not_extracted(self):
        for line in (DEVICE / 'proprietary-files.txt').read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            self.assertFalse(any(s in line for s in
                                 ('dolby', 'libdap', 'libdlb', 'libswdap', 'libhwdap',
                                  'libstagefright_soft_ddpdec', 'libstagefright_soft_ac4dec')),
                             line)

    def test_inherited_hal_declarations_are_preserved(self):
        board = (DEVICE / 'BoardConfigCommon.mk').read_text()
        for variable in ('DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE', 'DEVICE_MANIFEST_FILE'):
            self.assertNotRegex(board, rf'(?m)^{variable}\s*:=')

    def test_dolby_services_are_declared(self):
        manifest = ET.parse(DEVICE / 'manifest.xml').getroot()
        dms = manifest.find("hal[name='vendor.dolby.hardware.dms']")
        self.assertIsNotNone(dms, 'DMS must be declared for service registration')
        self.assertEqual(dms.findtext('interface/instance'), 'default')
        stores = manifest.find("hal[name='android.hardware.media.c2']")
        for instance in ('default1', 'dolby'):
            self.assertIn('@1.0::IComponentStore/' + instance,
                          [e.text for e in stores.findall('fqname')])
        matrix = ET.parse(DEVICE / 'framework_compatibility_matrix.xml').getroot()
        stores = matrix.find("hal[name='android.hardware.media.c2']")
        self.assertIsNotNone(stores, 'Dolby stores must be allowed by the framework')
        self.assertEqual(stores.get('optional'), 'true')
        for instance in ('default1', 'dolby'):
            self.assertIn(instance, [e.text for e in stores.findall('interface/instance')])

    def test_dolby_codec_config_is_included(self):
        codecs = ET.parse(DEVICE / 'configs/media/vendor/media_codecs_c2.xml').getroot()
        self.assertIn('media_codecs_dolby_audio.xml',
                      [e.get('href') for e in codecs.findall('Include')])
        dolby = ET.parse(DOLBY / 'configs/media_codecs_dolby_audio.xml').getroot()
        types = {e.get('name') for e in dolby.findall('Decoders/MediaCodec/Type')}
        self.assertTrue({'audio/ac3', 'audio/eac3', 'audio/eac3-joc'} <= types)

    def test_ac4_decoder_is_exposed_and_supplied(self):
        codecs = ET.parse(DEVICE / 'configs/media/vendor/media_codecs_c2.xml').getroot()
        ac4 = codecs.find("Decoders/MediaCodec[@type='audio/ac4']")
        self.assertIsNotNone(ac4, 'The supplied AC-4 decoder must be exposed to apps')
        self.assertEqual(ac4.get('name'), 'c2.dolby.ac4.decoder')
        blob = (DOLBY / 'proprietary/vendor/lib64/libcodec2_soft_ac4dec.so').read_bytes()
        self.assertTrue(b'c2.dolby.ac4.decoder\x00' in blob)
        store = (DOLBY / 'proprietary/vendor/lib64/libcodec2_store_dolby.so').read_bytes()
        self.assertTrue(b'libcodec2_soft_ac4dec.so\x00' in store)
        self.assertEqual(ac4.find("Limit[@name='sample-rate']").get('ranges'), '48000')
        self.assertEqual(ac4.find("Limit[@name='channel-count']").get('max'), '16')
        self.assertEqual(ac4.find("Limit[@name='bitrate']").get('range'), '16000-2688000')


if __name__ == '__main__':
    unittest.main()
