#!/usr/bin/env python3
"""Check observed physical wakeup-stat directories receive the existing RO type."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
# Paths enumerated on RMX2061; virtual sources already have platform labels.
PATHS=[
 '/devices/platform/soc/a600000.ssusb/wakeup',
 '/devices/platform/soc/soc:gpio_keys/wakeup',
 '/devices/platform/soc/soc:qcom,msm-audio-apr/soc:qcom,msm-audio-apr:qcom,q6core-audio/soc:qcom,msm-audio-apr:qcom,q6core-audio:bolero-cdc/rx-macro/rx_swr_ctrl/wakeup',
 '/devices/platform/soc/soc:qcom,msm-audio-apr/soc:qcom,msm-audio-apr:qcom,q6core-audio/soc:qcom,msm-audio-apr:qcom,q6core-audio:bolero-cdc/tx-macro/tx_swr_ctrl/wakeup',
 '/devices/platform/soc/c440000.qcom,spmi/spmi-0/spmi0-00/c440000.qcom,spmi:qcom,pm6150@0:qcom,qpnp-smb5/wakeup',
 '/devices/platform/soc/c440000.qcom,spmi/spmi-0/spmi0-00/c440000.qcom,spmi:qcom,pm6150@0:qcom,pm6150_rtc/wakeup',
 '/devices/platform/soc/c440000.qcom,spmi/spmi-0/spmi0-00/c440000.qcom,spmi:qcom,pm6150@0:qcom,power-on@800/wakeup',
 '/devices/platform/soc/c440000.qcom,spmi/spmi-0/spmi0-04/c440000.qcom,spmi:qcom,pm6150l@4:qcom,power-on@800/wakeup',
]
class WakeupStatsTest(unittest.TestCase):
 def test_physical_source_labels(self):
  labels=[]
  for line in (ROOT/'sepolicy/vendor/genfs_contexts').read_text().splitlines():
   fields=line.split()
   if len(fields)==4 and fields[:2]==['genfscon','sysfs']:
    labels.append((fields[2],fields[3]))
  for directory in PATHS:
   for leaf in ('name','active_count','total_time_ms','max_time_ms','last_change_ms'):
    path=f'{directory}/wakeup123/{leaf}'
    matches=[(prefix,label) for prefix,label in labels if path.startswith(prefix)]
    self.assertTrue(matches,path)
    self.assertEqual(max(matches,key=lambda x:len(x[0]))[1], 'u:object_r:sysfs_wakeup:s0')
  for prefix,label in labels:
   if label=='u:object_r:sysfs_wakeup:s0':
    self.assertTrue(prefix.endswith('/wakeup') or prefix.endswith('/diag'))
if __name__=='__main__':unittest.main()
