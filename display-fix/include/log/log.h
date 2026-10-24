#pragma once
#include <stddef.h>
#include <android/log.h>
#define ALOGE(...) __android_log_print(ANDROID_LOG_ERROR, "libsuspend-wakefix1", __VA_ARGS__)
#define ALOGV(...) ((void)0)
