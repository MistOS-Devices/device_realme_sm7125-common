#!/usr/bin/env python3
"""Validate the vendor group-clamp contract with Android's CPU profiles."""
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    'HighEnergySaving': ('background', '0'),
    'NormalPerformance': ('system', '0'),
    'ServicePerformance': ('system-background', '0'),
    'HighPerformance': ('foreground', '0'),
    'HighPerformanceWI': ('foreground_window', '6.25'),
    'MaxPerformance': ('top-app', '12.50'),
    'RealtimePerformance': ('rt', '0'),
    'CameraServicePerformance': ('camera-daemon', '0'),
    'NNApiHALPerformance': ('nnapi-hal', '0'),
    'Dex2oatPerformance': ('dex2oat', '0'),
}
class TaskProfilesTest(unittest.TestCase):
    def test_profiles_and_attributes(self):
        config = json.loads((ROOT/'configs/task_profiles.json').read_text())
        attributes = {x['Name']: x for x in config['Attributes']}
        for bound in ('Min', 'Max'):
            self.assertEqual(attributes['UClamp'+bound], {
                'Name': 'UClamp'+bound, 'Controller': 'cpu',
                'File': 'cpu.uclamp.'+bound.lower()})
        profiles = {p['Name']: p['Actions'] for p in config['Profiles']}
        self.assertEqual(len(profiles),len(config['Profiles']))
        for name,(group,floor) in GROUPS.items():
            self.assertEqual(profiles[name], [
                {'Name':'JoinCgroup','Params':{'Controller':'cpu','Path':group}},
                {'Name':'SetAttribute','Params':{'Name':'UClampMax','Value':'100'}},
                {'Name':'SetAttribute','Params':{'Name':'UClampMin','Value':floor}},
            ])
        for name in ('SCHED_QOS_NONE','SCHED_QOS_SENSITIVE_STANDARD','SCHED_QOS_SENSITIVE_EXTREME'):
            self.assertEqual(profiles[name], [])
        self.assertNotIn('AggregateProfiles',config) # Keep platform IO/timer actions.
        self.assertNotIn('UClampLatencySensitive',attributes)

    def test_group_node_ownership_and_initialization(self):
        text=(ROOT/'rootdir/etc/vendor/init.sm7125.rc').read_text()
        init=text.split('on init\n',1)[1].split('\non ',1)[0]
        for group,floor in GROUPS.values():
            for bound,value in [('max','100'),('min',floor)]:
                node=f'/dev/cpuctl/{group}/cpu.uclamp.{bound}'
                commands=[f'chown system system {node}',f'chmod 0664 {node}',f'write {node} {value}']
                positions=[init.index(cmd) for cmd in commands]
                self.assertEqual(positions,sorted(positions))
        self.assertNotIn('/dev/cpuctl/cpu.uclamp.',text) # Keep SF root placement unchanged.
if __name__=='__main__': unittest.main()
