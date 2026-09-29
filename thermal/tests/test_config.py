#!/usr/bin/env python3
"""Compile the production sensor configuration with host-only hardware/IPC stubs."""
import pathlib
import re
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
source = (root / 'thermalConfig.cpp').read_text()
data = (root / 'thermalData.h').read_text()
config = (root / 'thermalConfig.h').read_text()
struct = data[data.index('    struct target_therm_cfg {'):data.index('    struct therm_sensor {')]
klass = config[config.index('class ThermalConfig {'):config.index('}  // namespace thermal')]
prelude = '''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>
#define LOG(level) std::cerr
#define RETRY_CT 3
static int test_soc = 443;
namespace aidl::android::hardware::thermal {
struct ThermalCommon {
 int readFromFile(std::string_view path, std::string& out) {
  out = path.find("soc_id") != path.npos ? std::to_string(test_soc) : "MTP";
  return out.size();
 }
 int findLimitProfile() { return 0; }
};
'''
for enum in ('TemperatureType', 'ThrottlingSeverity'):
    names = sorted(set(re.findall(enum + r'::(\w+)', source + struct)))
    prelude += 'enum class ' + enum + ' {' + ','.join(names) + '};\n'
production = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
main = '''
using namespace aidl::android::hardware::thermal;
int main() {
 for (int soc : {443, 400}) {
  test_soc = soc;
  auto cfg = ThermalConfig().fetchConfig();
  int cpus = 0, gpu = 0, skin = 0, battery = 0, bcl = 0;
  for (const auto& sensor : cfg) {
   switch (sensor.type) {
    case TemperatureType::CPU: cpus += sensor.sensor_list.size(); break;
    case TemperatureType::GPU: ++gpu; break;
    case TemperatureType::SKIN: ++skin; break;
    case TemperatureType::BATTERY: ++battery; break;
    case TemperatureType::BCL_CURRENT:
    case TemperatureType::BCL_VOLTAGE:
    case TemperatureType::BCL_PERCENTAGE: ++bcl; break;
    default: break;
   }
  }
  assert(cpus == 8 && gpu > 0 && skin > 0 && battery == 1);
  assert(soc == 443 ? bcl == 0 : bcl > 0);
 }
 std::cout << "PASS: Realme 443 retains temperature sensors, excludes disabled BCL; 400 unchanged\\n";
}
'''
with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp)
    (path / 'test.cpp').write_text(prelude + struct + klass + '}\n' + production + main)
    subprocess.run(['clang++', '-std=c++17', '-fsanitize=address,undefined',
                    str(path / 'test.cpp'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
