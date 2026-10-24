// Host regression tests exercise semaphore ordering and failure recovery.
#include "generated/autosuspend_wakeup_count.cpp"
#include <cassert>
#include <thread>
#include <chrono>
static std::string state_text() {
    char b[4] = {}; assert(pread(state_fd,b,3,0) >= 0); return b;
}
int main() {
    char path[] = "/tmp/wakefix1-XXXXXX";
    state_fd = mkstemp(path); assert(state_fd >= 0); unlink(path);
    autosuspend_is_init = true; legacy_earlysuspend = true;
    assert(sem_init(&suspend_lockout,0,1) == 0);
    assert(autosuspend_wakeup_count_disable() == 0);
    assert(state_text() == "on");
    assert(sem_trywait(&suspend_lockout) == -1 && errno == EAGAIN);
    assert(autosuspend_wakeup_count_enable() == 0);
    // Simulate a worker already holding the gate with a pending sleep write.
    assert(sem_wait(&suspend_lockout) == 0);
    std::thread worker([] {
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
        assert(lseek(state_fd,0,SEEK_SET) == 0);
        assert(android::base::WriteStringToFd("mem",state_fd));
        assert(lseek(state_fd,0,SEEK_SET) == 0);
        assert(sem_post(&suspend_lockout) == 0);
    });
    assert(autosuspend_wakeup_count_disable() == 0); worker.join();
    assert(state_text().substr(0,2) == "on");
    assert(sem_trywait(&suspend_lockout) == -1 && errno == EAGAIN);
    assert(autosuspend_wakeup_count_enable() == 0);
    int good_fd=state_fd; state_fd=-1;
    assert(autosuspend_wakeup_count_disable() == -1);
    assert(sem_trywait(&suspend_lockout) == 0); // no deadlock after error
    assert(sem_post(&suspend_lockout) == 0);
    legacy_earlysuspend=false;
    assert(autosuspend_wakeup_count_disable() == 0); // modern path does not write
    close(good_fd);
    puts("PASS: legacy on write, writer ordering, held gate, error recovery, modern path");
}
