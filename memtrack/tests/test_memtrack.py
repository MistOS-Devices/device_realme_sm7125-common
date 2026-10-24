#!/usr/bin/env python3
"""Compile the real AIDL handler with interface fixtures and KGSL counter files."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp); proc=d/'proc'; proc.mkdir()
 stub=d/'aidl/android/hardware/memtrack/BnMemtrack.h';stub.parent.mkdir(parents=True)
 stub.write_text('''#pragma once
#include <cstdint>
#include <string>
#include <vector>
#define EX_ILLEGAL_ARGUMENT 3
#define EX_UNSUPPORTED_OPERATION 7
namespace ndk { struct ScopedAStatus { int code; bool isOk() const { return code==0; }
static ScopedAStatus ok() { return {0}; }
static ScopedAStatus fromExceptionCode(int code) { return {-code}; }
static ScopedAStatus fromServiceSpecificError(int code) { return {code}; }
}; }
namespace aidl::android::hardware::memtrack {
enum class MemtrackType {OTHER,GL,GRAPHICS,MULTIMEDIA,CAMERA};
struct DeviceInfo {int32_t id; std::string name;};
struct MemtrackRecord {int64_t sizeInBytes; int32_t flags;
static constexpr int FLAG_SECURE=16,FLAG_PRIVATE=1,FLAG_NONSECURE=2,FLAG_SMAPS_ACCOUNTED=4,FLAG_SMAPS_UNACCOUNTED=8;};
struct BnMemtrack {virtual ~BnMemtrack()=default;
virtual ndk::ScopedAStatus getMemory(int32_t,MemtrackType,std::vector<MemtrackRecord>*)=0;
virtual ndk::ScopedAStatus getGpuDeviceInfo(std::vector<DeviceInfo>*)=0;};
}
''')
 source=(ROOT/'Memtrack.cpp').read_text().replace('/sys/class/kgsl/kgsl/',str(d)+'/')
 (d/'Memtrack.cpp').write_text(source);(d/'Memtrack.h').write_text((ROOT/'Memtrack.h').read_text())
 (d/'test.cpp').write_text('''
#include "Memtrack.cpp"
#include <cassert>
#include <filesystem>
#include <fstream>
using namespace aidl::android::hardware::memtrack;
void write(const std::string& path,const std::string& value) { std::ofstream(path)<<value; }
int main() {
 realme::Memtrack hal; std::vector<MemtrackRecord> records;
 std::string root=realme::kProc;
 write(std::string(realme::kStats)+"page_alloc","200");
 write(std::string(realme::kStats)+"coherent","30");
 write(std::string(realme::kStats)+"secure","50");
 std::filesystem::create_directory(root+"12");std::filesystem::create_directory(root+"34");
 write(root+"12/gpumem_mapped","100\\n");write(root+"12/gpumem_unmapped","40\\n");
 write(root+"12/imported_mem","1000\\n");write(root+"34/gpumem_unmapped","20\\n");write(root+"34/gpumem_mapped","10");
 assert(hal.getMemory(12,MemtrackType::GL,&records).isOk() && records.size()==2);
 assert(records[0].sizeInBytes==100 && (records[0].flags&MemtrackRecord::FLAG_SMAPS_ACCOUNTED));
 assert(records[1].sizeInBytes==40 && (records[1].flags&MemtrackRecord::FLAG_SMAPS_UNACCOUNTED));
 assert(hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.size()==2 && records[0].sizeInBytes==120);
 assert(records[1].sizeInBytes==50 && (records[1].flags&MemtrackRecord::FLAG_SECURE));
 assert(hal.getMemory(12,MemtrackType::GRAPHICS,&records).isOk() && records[0].sizeInBytes==1000);
 assert(hal.getMemory(0,MemtrackType::GRAPHICS,&records).isOk() && records.empty());
 assert(hal.getMemory(99,MemtrackType::GL,&records).isOk() && records.empty());
 assert(!hal.getMemory(-1,MemtrackType::GL,&records).isOk() && records.empty());
 assert(!hal.getMemory(12,static_cast<MemtrackType>(99),&records).isOk());
 write(std::string(realme::kStats)+"secure","bad");
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 std::filesystem::remove(std::string(realme::kStats)+"secure");
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 write(std::string(realme::kStats)+"secure","50");
 for (auto bad:{"-1","1junk","40\\njunk","9223372036854775808",""}) {
  write(root+"12/gpumem_mapped",bad);
  assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 }
 write(root+"12/gpumem_mapped","9223372036854775807");
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty()); // sum overflow
 std::filesystem::remove(root+"34/gpumem_mapped"); // exiting process is skipped
 write(root+"12/gpumem_mapped","100");
 assert(hal.getMemory(0,MemtrackType::GL,&records).isOk() && records[0].sizeInBytes==130);
 write(std::string(realme::kStats)+"page_alloc","90");
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 write(std::string(realme::kStats)+"page_alloc","9223372036854775807");
 write(std::string(realme::kStats)+"coherent","9223372036854775807");
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 std::filesystem::remove_all(root);
 assert(!hal.getMemory(0,MemtrackType::GL,&records).isOk() && records.empty());
 std::vector<DeviceInfo> devices;assert(hal.getGpuDeviceInfo(&devices).isOk() && devices.size()==1);
}
''')
 subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(d),str(d/'test.cpp'),'-o',str(d/'test')],check=True)
 subprocess.run([str(d/'test')],check=True)
print('PASS: real memtrack handler global/per-PID counters, no double counting, malformed/overflow and disappearing nodes')

# Build/runtime wiring must replace the old service, with exactly one instance.
import xml.etree.ElementTree as ET
board=ROOT.parent
assert 'android.hardware.memtrack-service.realme_sm7125' in (board/'common.mk').read_text()
assert 'vendor.qti.hardware.memtrack-service' not in (board/'common.mk').read_text()
assert 'overrides: ["vendor.qti.hardware.memtrack-service"]' in (ROOT/'Android.bp').read_text()
manifest=ET.parse(ROOT/'android.hardware.memtrack-service.realme_sm7125.xml')
assert manifest.find('.//name').text=='android.hardware.memtrack'
assert manifest.find('.//fqname').text=='IMemtrack/default'
assert 'hal_memtrack_default_exec' in (board/'sepolicy/vendor/file_contexts').read_text().split('# Device-owned legacy KGSL memtrack backend.')[1]
assert 'r_dir_file(hal_memtrack_default, vendor_sysfs_kgsl_proc)' in (board/'sepolicy/vendor/hal_memtrack_default.te').read_text()

for counter in ('page_alloc', 'coherent', 'secure'):
 assert f'/devices/virtual/kgsl/kgsl/{counter} u:object_r:vendor_sysfs_kgsl_proc:s0' in (board/'sepolicy/vendor/genfs_contexts').read_text()
