// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 ShadowBladeX
#include "Memtrack.h"
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <cstdlib>

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    auto service = ndk::SharedRefBase::make<realme::Memtrack>();
    const std::string instance = std::string(realme::Memtrack::descriptor) + "/default";
    if (AServiceManager_addService(service->asBinder().get(), instance.c_str()) != STATUS_OK) {
        return EXIT_FAILURE;
    }
    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;
}
