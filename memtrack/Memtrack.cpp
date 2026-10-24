// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 ShadowBladeX
#include "Memtrack.h"
#include <cerrno>
#include <cctype>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <memory>
#include <string>

using aidl::android::hardware::memtrack::DeviceInfo;
using aidl::android::hardware::memtrack::MemtrackRecord;
using aidl::android::hardware::memtrack::MemtrackType;

namespace realme {
namespace {
constexpr const char* kStats = "/sys/class/kgsl/kgsl/";
constexpr const char* kProc = "/sys/class/kgsl/kgsl/proc/";

int readCounter(const std::string& path, int64_t* value) {
    std::unique_ptr<FILE, decltype(&fclose)> file(fopen(path.c_str(), "r"), fclose);
    if (!file) return -errno;
    char buf[64];
    const size_t length = fread(buf, 1, sizeof(buf) - 1, file.get());
    if (ferror(file.get())) return -EIO;
    if (!length || length == sizeof(buf) - 1) return -EINVAL;
    buf[length] = '\0';
    if (!std::isdigit(static_cast<unsigned char>(buf[0]))) return -EINVAL;
    char* end;
    errno = 0;
    unsigned long long number = strtoull(buf, &end, 10);
    if (errno == ERANGE || number > INT64_MAX) return -EOVERFLOW;
    while (std::isspace(static_cast<unsigned char>(*end))) ++end;
    if (*end) return -EINVAL;
    *value = static_cast<int64_t>(number);
    return 0;
}

int readPrivateTotal(int64_t* total) {
    std::unique_ptr<DIR, decltype(&closedir)> directory(opendir(kProc), closedir);
    if (!directory) return -errno;
    int64_t sum = 0;
    for (;;) {
        errno = 0;
        dirent* entry = readdir(directory.get());
        if (!entry) {
            if (errno) return -errno;
            break;
        }
        std::string pid(entry->d_name);
        if (pid.empty() || pid.find_first_not_of("0123456789") != std::string::npos) continue;
        int64_t bytes;
        int ret = readCounter(std::string(kProc) + pid + "/gpumem_mapped", &bytes);
        if (ret == -ENOENT || ret == -ESRCH) continue; // Process exited during enumeration.
        if (ret) return ret;
        if (bytes > INT64_MAX - sum) return -EOVERFLOW;
        sum += bytes;
    }
    int64_t allocated, coherent;
    int ret = readCounter(std::string(kStats) + "page_alloc", &allocated);
    if (!ret) ret = readCounter(std::string(kStats) + "coherent", &coherent);
    if (ret) return ret;
    // On this SMMU device process mappings are page allocations. Coherent
    // globals use PFNMAP and are not counted by CPU smaps; vmalloc is an alias.
    if (sum > allocated) return -EAGAIN; // Counters changed while sampling.
    allocated -= sum;
    if (coherent > INT64_MAX - allocated) return -EOVERFLOW;
    *total = allocated + coherent;
    return 0;
}

void addRecord(std::vector<MemtrackRecord>* records, int64_t bytes, bool accounted, bool secure = false) {
    MemtrackRecord record;
    record.sizeInBytes = bytes;
    record.flags = MemtrackRecord::FLAG_PRIVATE |
            (secure ? MemtrackRecord::FLAG_SECURE : MemtrackRecord::FLAG_NONSECURE) |
            (accounted ? MemtrackRecord::FLAG_SMAPS_ACCOUNTED :
                         MemtrackRecord::FLAG_SMAPS_UNACCOUNTED);
    records->push_back(record);
}
}

ndk::ScopedAStatus Memtrack::getMemory(int32_t pid, MemtrackType type,
                                     std::vector<MemtrackRecord>* records) {
    records->clear();
    if (pid < 0) return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    if (type != MemtrackType::OTHER && type != MemtrackType::GL &&
        type != MemtrackType::GRAPHICS && type != MemtrackType::MULTIMEDIA &&
        type != MemtrackType::CAMERA) {
        return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    }
    int64_t mapped = 0, unmapped = 0, secure = 0;
    int ret = 0;
    if (pid == 0) {
        // Include driver globals; exclude imported DMA-BUFs and CPU smaps.
        if (type == MemtrackType::GL) {
            ret = readPrivateTotal(&unmapped);
            if (!ret) ret = readCounter(std::string(kStats) + "secure", &secure);
        }
    } else {
        const std::string path = std::string(kProc) + std::to_string(pid) + "/";
        if (type == MemtrackType::GL) {
            ret = readCounter(path + "gpumem_mapped", &mapped);
            if (!ret) ret = readCounter(path + "gpumem_unmapped", &unmapped);
        } else if (type == MemtrackType::GRAPHICS) {
            ret = readCounter(path + "imported_mem", &unmapped);
        }
    }
    if (pid > 0 && (ret == -ENOENT || ret == -ESRCH)) return ndk::ScopedAStatus::ok();
    if (ret) return ndk::ScopedAStatus::fromServiceSpecificError(-ret);
    if (mapped) addRecord(records, mapped, true);
    if (unmapped) addRecord(records, unmapped, false);
    if (secure) addRecord(records, secure, false, true);
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus Memtrack::getGpuDeviceInfo(std::vector<DeviceInfo>* devices) {
    devices->clear();
    DeviceInfo info;
    info.id = 0;
    info.name = "kgsl";
    devices->push_back(info);
    return ndk::ScopedAStatus::ok();
}
}
