#!/sbin/sh
set -eu
block=/dev/block/platform/omap_hsmmc.1/by-name/KERNEL
dest=/data/media/0/GT-P5100-UPDATE2-backup
payload=/tmp/p5100-update2
target=/data/user_de/0/com.google.android.gms/app_chimera/m/00000009/n/armeabi-v7a/libcronet.156.0.8078.25.so
digest() { sha1sum "$1" | cut -d ' ' -f 1; }
boot_digest() { head -c "$1" "$block" | sha1sum | cut -d ' ' -f 1; }
grep -q ' /data ' /proc/mounts
test -d /data/media/0
test -b "$block"
test "$(cat /sys/class/block/mmcblk0p5/size)" -eq 16384
test "$(digest /system/lib/libsuspend.so)" = '@DISPLAY@'
test "$(digest /system/bin/sdcard)" = '@SDCARD@'
test "$(digest "$payload/boot.img")" = '@NEW_BOOT@'
test "$(boot_digest @OLD_LEN@)" = '@OLD_BOOT@' || test "$(boot_digest @NEW_LEN@)" = '@NEW_BOOT@'
current=$(digest "$target")
test "$current" = '@BAD@' || test "$current" = '@GOOD@'
mkdir -p "$dest"
if [ -f "$dest/COMPLETE" ]; then
 (cd "$dest" && sha1sum -c SHA1SUMS)
else
 test "$(boot_digest @OLD_LEN@)" = '@OLD_BOOT@'
 dd if="$block" of="$dest/boot.img" bs=4096 count=2048
 test "$(wc -c < "$dest/boot.img")" -eq 8388608
 test "$(digest "$block")" = "$(digest "$dest/boot.img")"
 cp -p "$target" "$dest/cronet.so"
 test "$(digest "$dest/cronet.so")" = "$current"
 (cd "$dest" && sha1sum boot.img cronet.so > SHA1SUMS && sha1sum -c SHA1SUMS)
 sync
 echo complete > "$dest/COMPLETE"
 sync
fi
test "$(wc -c < "$dest/boot.img")" -eq 8388608
test "$(head -c @OLD_LEN@ "$dest/boot.img" | sha1sum | cut -d ' ' -f 1)" = '@OLD_BOOT@'
backup_hash=$(digest "$dest/cronet.so")
test "$backup_hash" = '@BAD@' || test "$backup_hash" = '@GOOD@'
restore() {
 cat "$dest/cronet.so" > "$target" || return 1
 cat "$dest/boot.img" > "$block" || return 1
 sync
 test "$(digest "$target")" = "$backup_hash" || return 1
 test "$(digest "$block")" = "$(digest "$dest/boot.img")" || return 1
}
if [ -f "$dest/ROLLBACK" ]; then
 restore
 mv "$dest/ROLLBACK" "$dest/ROLLBACK-DONE"
 echo 'Rollback completed.'
 exit 0
fi
# Recover only from the same installed APK. No Google binaries are shipped.
apk=
for candidate in /data/app/com.google.android.gms-*/base.apk; do
 if [ -f "$candidate" ] && [ "$(digest "$candidate")" = '@APK@' ]; then apk=$candidate; break; fi
done
test -n "$apk" || { echo 'Installed Google APK differs; aborting without changes.'; exit 1; }
unzip -p "$apk" assets/chimera-modules/CronetDynamite.uncompressed.apk > "$payload/cronet.apk"
unzip -p "$payload/cronet.apk" lib/armeabi-v7a/libcronet.156.0.8078.25.so > "$payload/cronet.so"
test "$(digest "$payload/cronet.so")" = '@GOOD@'
on_exit() {
 result=$?
 trap - EXIT
 if [ "$result" -ne 0 ]; then
  echo 'Write failed; restoring backup.'
  restore || echo 'RESTORE FAILED: remain in TWRP and restore separate Boot/Data backups.'
 fi
 exit "$result"
}
trap on_exit EXIT
# Keep the existing inode, owner, permissions and SELinux label.
cat "$payload/cronet.so" > "$target"
test "$(digest "$target")" = '@GOOD@'
cat "$payload/boot.img" > "$block"
sync
test "$(boot_digest @NEW_LEN@)" = '@NEW_BOOT@'
test "$(digest /system/lib/libsuspend.so)" = '@DISPLAY@'
trap - EXIT
echo 'GPS daemon disabled; Cronet restored from installed APK. No data wipe.'

