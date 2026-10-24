// Small NDK build adapter for AOSP libsuspend (no platform libbase dependency).
#pragma once
#include <cerrno>
#include <cstring>
#include <string>
#include <sstream>
#include <cstdio>
#include <unistd.h>
#ifdef __ANDROID__
#include <android/log.h>
#endif
namespace android { namespace base {
static bool WriteStringToFd(const std::string& s, int fd) {
    size_t done = 0;
    while (done < s.size()) {
        ssize_t n = TEMP_FAILURE_RETRY(write(fd, s.data() + done, s.size() - done));
        if (n <= 0) return false;
        done += n;
    }
    return true;
}
static bool ReadFdToString(int fd, std::string* s) {
    s->clear(); char buf[4096];
    for (;;) {
        ssize_t n = TEMP_FAILURE_RETRY(read(fd, buf, sizeof(buf)));
        if (n < 0) return false;
        if (n == 0) return true;
        s->append(buf, n);
    }
}
static std::string Trim(const std::string& s) {
    const char* ws = " \t\n\r\f\v";
    size_t begin = s.find_first_not_of(ws);
    return begin == std::string::npos ? "" : s.substr(begin, s.find_last_not_of(ws) - begin + 1);
}
}}
class SuspendLog {
    bool active; int saved_errno; bool with_errno; std::ostringstream text;
public:
    SuspendLog(const char* level, bool pe): active(strcmp(level, "VERBOSE") != 0), saved_errno(errno), with_errno(pe) {}
    template<class T> SuspendLog& operator<<(const T& x) { if (active) text << x; return *this; }
    ~SuspendLog() {
        if (!active) return;
        if (with_errno) text << ": " << strerror(saved_errno);
#ifdef __ANDROID__
        __android_log_write(ANDROID_LOG_INFO, "libsuspend-wakefix1", text.str().c_str());
#else
        fprintf(stderr, "%s\n", text.str().c_str());
#endif
    }
};
#define LOG(level) SuspendLog(#level, false)
#define PLOG(level) SuspendLog(#level, true)
#ifndef MIN
#define MIN(a,b) ((a)<(b)?(a):(b))
#endif
