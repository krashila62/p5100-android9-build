from pathlib import Path
import difflib, hashlib, json
root = Path(__file__).resolve().parent
src = root / 'upstream'
out = root / 'generated'
out.mkdir(exist_ok=True)
original = (src / 'autosuspend_wakeup_count.cpp').read_text()
text = original
includes = '#include <android-base/file.h>\n#include <android-base/logging.h>\n#include <android-base/strings.h>'
assert text.count(includes) == 1
text = text.replace(includes, '#include "compat.h"')
text = text.replace('static bool autosuspend_is_init = false;', 'static bool autosuspend_is_init = false;\nstatic bool legacy_earlysuspend = false;')
needle = '    wakeup_count_fd = TEMP_FAILURE_RETRY(open(sys_power_wakeup_count, O_CLOEXEC | O_RDWR));'
assert text.count(needle) == 1
text = text.replace(needle, '''    // These nodes identify the earlysuspend ABI in the pinned espresso kernel.
    legacy_earlysuspend = access("/sys/power/wait_for_fb_sleep", F_OK) == 0 &&
                         access("/sys/power/wait_for_fb_wake", F_OK) == 0;

''' + needle)
old = '''    int ret = sem_wait(&suspend_lockout);

    if (ret < 0) {
        PLOG(ERROR) << "error changing semaphore";
    }
'''
new = '''    int ret = TEMP_FAILURE_RETRY(sem_wait(&suspend_lockout));
    if (ret < 0) {
        PLOG(ERROR) << "error changing semaphore";
        return ret;
    }

    // Hold the same gate as the suspend writer: a late 'mem' must not
    // overtake this 'on'. Stopping that writer alone leaves earlysuspend asleep.
    if (legacy_earlysuspend && !WriteStringToFd("on", state_fd)) {
        const int saved_errno = errno;
        PLOG(ERROR) << "WAKEFIX1: failed to request early resume";
        sem_post(&suspend_lockout);  // enable state is retained by the caller
        errno = saved_errno;
        return -1;
    }
    if (legacy_earlysuspend) LOG(INFO) << "WAKEFIX1: early resume requested";
'''
assert text.count(old) == 1
text = text.replace(old, new)
(out/'autosuspend_wakeup_count.cpp').write_text(text)
(out/'wakefix1.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/autosuspend_wakeup_count.cpp',tofile='b/autosuspend_wakeup_count.cpp')))
(out/'source-hashes.json').write_text(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and 'generated' not in p.parts},indent=2))
