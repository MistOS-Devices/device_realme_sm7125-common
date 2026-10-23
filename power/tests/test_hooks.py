#!/usr/bin/env python3
"""Compile the real hooks against a fake QTI backend; exercise fallback lifecycle."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    d = Path(directory)
    headers = {
        'log/log.h': '#pragma once\n#define ALOGE(...) ((void)0)\n',
        'aidl/android/hardware/power/BnPower.h': '''#pragma once
namespace aidl::android::hardware::power {
enum class Mode { LAUNCH, OTHER }; enum class Boost { INTERACTION, OTHER };
}
''',
        'power-common.h': '''#pragma once
#define HINT_HANDLED 1
#define HINT_NONE 0
#define CHECK_HANDLE(h) ((h) > 0)
#define VENDOR_HINT_FIRST_LAUNCH_BOOST 1
#define LAUNCH_BOOST_V1 1
#define VENDOR_HINT_SCROLL_BOOST 2
#define SCROLL_VERTICAL 1
''',
        'hint-data.h': '', 'metadata-defs.h': '',
        'performance.h': '''#pragma once
extern int next_handle, requests, releases, last_duration;
extern long long now_us;
inline int perf_hint_enable_with_type(int, int duration, int) { ++requests; last_duration=duration; return next_handle; }
inline void release_request(int) { ++releases; }
''',
        'utils.h': '''#pragma once
#include <time.h>
extern long long now_us;
inline int test_clock_gettime(clockid_t, timespec *ts) {
    ts->tv_sec=now_us/1000000; ts->tv_nsec=(now_us%1000000)*1000; return 0;
}
#define clock_gettime test_clock_gettime
inline long long calc_timespan_us(timespec before, timespec after) {
    return (after.tv_sec-before.tv_sec)*1000000LL+(after.tv_nsec-before.tv_nsec)/1000;
}
''',
    }
    for name, text in headers.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    source = '#include <cassert>\n#include <thread>\n#include <vector>\nextern "C" { int next_handle=-1, requests=0, releases=0, last_duration=0; long long now_us=1000000; }\n'
    source += f'#include "{root / "mode-ext.cpp"}"\n#include "{root / "boost-ext.cpp"}"\n'
    source += '''
int main() {
    using namespace aidl::google::hardware::power::impl::pixel;
    using aidl::android::hardware::power::Mode;
    using aidl::android::hardware::power::Boost;
    assert(!setDeviceSpecificMode(Mode::LAUNCH, true));
    assert(!setDeviceSpecificMode(Mode::LAUNCH, false));
    assert(!setDeviceSpecificBoost(Boost::INTERACTION, 100));
    next_handle=7;
    assert(setDeviceSpecificMode(Mode::LAUNCH, true));
    assert(setDeviceSpecificMode(Mode::LAUNCH, false));
    assert(releases==1);
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 100));
    assert(last_duration==100);
    int before=requests;
    now_us+=10000; // Coalesce within the live boost.
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 100));
    assert(requests==before);
    now_us+=70000; // Exactly 20 ms remain: refresh before expiry.
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 100));
    assert(requests==before+1);
    now_us+=10000;
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 500));
    assert(requests==before+2 && last_duration==500);
    now_us+=500001; // Expired ordinary hints must never be suppressed.
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 100));
    assert(requests==before+3);
    now_us+=100001; next_handle=-1;
    assert(!setDeviceSpecificBoost(Boost::INTERACTION, 100));
    next_handle=8; // A failed request must permit an immediate retry.
    assert(setDeviceSpecificBoost(Boost::INTERACTION, -1));
    assert(last_duration==100);
    assert(setDeviceSpecificBoost(Boost::INTERACTION, 5000));
    assert(last_duration==1000);
    now_us+=1000001; before=requests;
    std::vector<std::thread> threads;
    for (int i=0;i<32;i++) threads.emplace_back([] {
        assert(setDeviceSpecificBoost(Boost::INTERACTION, 100));
    });
    for (auto &thread:threads) thread.join();
    assert(requests==before+1);
    assert(!setDeviceSpecificMode(Mode::OTHER, true));
    assert(!setDeviceSpecificBoost(Boost::OTHER, 100));
}
'''
    (d / 'test.cpp').write_text(source)
    subprocess.run(['clang++', '-std=c++17', '-pthread', '-I', str(d), '-fsanitize=address,undefined',
                    str(d / 'test.cpp'), '-o', str(d / 'test')], check=True)
    subprocess.run([str(d / 'test')], check=True)

print("PASS: interaction coverage, extension, bounds, fallback, retry and concurrent coalescing")
