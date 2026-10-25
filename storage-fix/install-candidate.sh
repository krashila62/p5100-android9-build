#!/sbin/sh
set -eu
block=/dev/block/platform/omap_hsmmc.1/by-name/KERNEL
dest=/data/media/0/GT-P5100-INTEGRATED-backup
payload=/tmp/p5100-integrated
target=/system/bin/sdcard
digest() { sha1sum "$1" | cut -d ' ' -f 1; }
grep -q ' /data ' /proc/mounts
grep -q ' /system ' /proc/mounts
test -d /data/media/0
test -b "$block"
test "$(cat /sys/class/block/mmcblk0p5/size)" -eq 16384
test "$(digest "$target")" = '33a03d2f35bc324169dd88ec13a18d4ffa36dfb0' || test "$(digest "$target")" = 'c3fd6d61a8a17e8d3ff363d95ea00f0c91197bbc'
test "$(digest "$payload/boot.img")" = '7362faffd08bf7abd886745aeb7623b50d8aaac2'
test "$(digest "$payload/sdcard")" = 'c3fd6d61a8a17e8d3ff363d95ea00f0c91197bbc'
test "$(digest /system/lib/libsuspend.so)" = 'f8647da2fa6044ec20befb040751fd8f8086cfb5'
mkdir -p "$dest"
if [ -f "$dest/COMPLETE" ]; then
 (cd "$dest" && sha1sum -c SHA1SUMS)
else
 # A previous incomplete backup is never used for restoration.
 test "$(digest "$target")" = '33a03d2f35bc324169dd88ec13a18d4ffa36dfb0'
 test "$(head -c 5208064 "$block" | sha1sum | cut -d ' ' -f 1)" = '0a65b2e0eea0b4b9d4a8ba189318984f40fe4976'
 dd if="$block" of="$dest/boot.img" bs=4096 count=2048
 test "$(wc -c < "$dest/boot.img")" -eq 8388608
 test "$(digest "$dest/boot.img")" = "$(digest "$block")"
 cp -p "$target" "$dest/sdcard"
 (cd "$dest" && sha1sum boot.img sdcard > SHA1SUMS && sha1sum -c SHA1SUMS)
 sync
 echo 'Backup complete' > "$dest/COMPLETE"
 sync
fi
# Validate backup identity in addition to its stored checksums.
test "$(digest "$dest/sdcard")" = '33a03d2f35bc324169dd88ec13a18d4ffa36dfb0'
test "$(wc -c < "$dest/boot.img")" -eq 8388608
test "$(head -c 5208064 "$dest/boot.img" | sha1sum | cut -d ' ' -f 1)" = '0a65b2e0eea0b4b9d4a8ba189318984f40fe4976'
replace_sd() {
 cp "$1" /system/bin/sdcard.integrated-new
 chown 0:0 /system/bin/sdcard.integrated-new
 chmod 0755 /system/bin/sdcard.integrated-new
 chcon u:object_r:sdcardd_exec:s0 /system/bin/sdcard.integrated-new
 mv /system/bin/sdcard.integrated-new "$target"
}
restore() {
 replace_sd "$dest/sdcard" || return 1
 cat "$dest/boot.img" > "$block" || return 1
 sync
 test "$(digest "$target")" = '33a03d2f35bc324169dd88ec13a18d4ffa36dfb0' || return 1
 test "$(digest "$block")" = "$(digest "$dest/boot.img")" || return 1
}
if [ -f "$dest/ROLLBACK" ]; then
 restore
 mv "$dest/ROLLBACK" "$dest/ROLLBACK-DONE"
 echo 'Rollback complete; display and Wi-Fi fixes retained.'
 exit 0
fi
on_exit() {
 result=$?
 trap - EXIT
 if [ "$result" -ne 0 ]; then
   echo 'Install failed. Restoring verified backup.'
   restore || echo 'AUTOMATIC RESTORE FAILED: keep TWRP open and restore Boot/System backup.'
 fi
 exit "$result"
}
trap on_exit EXIT
replace_sd "$payload/sdcard"
test "$(digest "$target")" = 'c3fd6d61a8a17e8d3ff363d95ea00f0c91197bbc'
cat "$payload/boot.img" > "$block"
sync
test "$(head -c 5208064 "$block" | sha1sum | cut -d ' ' -f 1)" = '7362faffd08bf7abd886745aeb7623b50d8aaac2'
test "$(digest /system/lib/libsuspend.so)" = 'f8647da2fa6044ec20befb040751fd8f8086cfb5'
trap - EXIT
echo 'Installation complete. Hardware validation still required. No data wipe.'

