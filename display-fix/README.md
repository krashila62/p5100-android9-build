# Experimental GT-P5100 WAKEFIX1

Target: Android 9 with the espresso 3.4 kernel and legacy earlysuspend sysfs ABI.
Not a claim to fix all artifacts or the separate DISPC IRQ-unregister panic.

The kernel's kernel/power/main.c at 4f4a4b2427c5b09ec0442c0578957322ff4c7ca6
routes writes to /sys/power/state through request_suspend_state with CONFIG_EARLYSUSPEND.
The Android 9 wakeup-count backend stops its writer in disable(), but never sends
the corresponding `on`. Request legacy resume while holding that writer's semaphore.
On write failure return an error and restore the semaphore so a retry cannot deadlock.
Only enable this behavior when both legacy framebuffer wait nodes exist.

Upstream source snapshots: https://github.com/LineageOS/android_system_core/tree/lineage-16.0/libsuspend
Retained Apache 2.0 notices. Sources are committed here and hashed by prepare.py.
The broken extra earlysuspend backend in the ROM is not used. Public autosuspend
entry points and the wakeup-count suspend algorithm remain based on upstream.
The NDK adapter implements libbase string/file/log helpers locally; static NDK C++
runtime symbols are hidden. API level 28, ARMv7, original kernel is not changed.

Host tests cover the new legacy-resume write, ordering against a pending mem writer,
semaphore ownership, write-failure recovery, and unchanged nonlegacy behavior.
They cannot prove that a physical panel wakes or that the kernel cannot panic.
Build artifacts are not directly flashable. Validate ELF dependencies and exports,
then create a hash-gated recovery update with rollback and backup before device testing.

Only public-repository standard GitHub runners are used. No paid runner or external
compute service is configured. Artifacts expire after three days.
