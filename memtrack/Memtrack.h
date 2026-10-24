// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <aidl/android/hardware/memtrack/BnMemtrack.h>

namespace realme {
class Memtrack : public aidl::android::hardware::memtrack::BnMemtrack {
public:
    ndk::ScopedAStatus getMemory(int32_t pid,
            aidl::android::hardware::memtrack::MemtrackType type,
            std::vector<aidl::android::hardware::memtrack::MemtrackRecord>* records) override;
    ndk::ScopedAStatus getGpuDeviceInfo(
            std::vector<aidl::android::hardware::memtrack::DeviceInfo>* devices) override;
};
}
