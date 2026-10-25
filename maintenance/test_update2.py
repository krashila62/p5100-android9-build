import pathlib,tempfile,zipfile,io,hashlib,subprocess,json
source=(pathlib.Path(__file__).parent/'install-template.sh').read_text()
sha=lambda b:hashlib.sha1(b).hexdigest()
old=b'boot-old';new=b'boot-new';bad=b'broken-library';good=b'original-library';display=b'display';sd=b'sdcard'
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w') as z:z.writestr('lib/armeabi-v7a/libcronet.156.0.8078.25.so',good)
outer=io.BytesIO()
with zipfile.ZipFile(outer,'w') as z:z.writestr('assets/chimera-modules/CronetDynamite.uncompressed.apk',buf.getvalue())
apk=outer.getvalue();constants=dict(OLD_BOOT=sha(old),OLD_LEN=len(old),NEW_BOOT=sha(new),NEW_LEN=len(new),BAD=sha(bad),GOOD=sha(good),APK=sha(apk),DISPLAY=sha(display),SDCARD=sha(sd))
for k,v in constants.items():source=source.replace('@'+k+'@',str(v))
results=[]
for case in ['install','repeat','rollback','wrong-apk','wrong-library','bad-backup','write-failure','wrong-boot','preserve-metadata']:
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp)
  def path(s):return root/s.lstrip('/')
  def write(s,data):
   p=path(s);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
  block=write('/dev/block/platform/omap_hsmmc.1/by-name/KERNEL',old+bytes(8388608-len(old)))
  write('/system/lib/libsuspend.so',display);write('/system/bin/sdcard',sd)
  write('/tmp/p5100-update2/boot.img',new);write('/sys/class/block/mmcblk0p5/size',b'16384\n')
  write('/proc/mounts',b'dev /data ext4 rw 0 0\n')
  path('/data/media/0').mkdir(parents=True)
  app=write('/data/app/com.google.android.gms-fixture/base.apk',apk)
  lib=write('/data/user_de/0/com.google.android.gms/app_chimera/m/00000009/n/armeabi-v7a/libcronet.156.0.8078.25.so',bad)
  lib.chmod(0o755);original_stat=lib.stat()
  script=source.replace('test -b "$block"','test -f "$block"')
  # Prefix literal paths once, without recursively rewriting temporary paths.
  import re
  script=re.sub(r'/(data|system|tmp|proc|sys|dev)/',lambda m:str(root)+m.group(0),script)
  p=root/'installer.sh';p.write_text(script)
  run=lambda:subprocess.run(['sh',str(p)],capture_output=True,text=True)
  backup=path('/data/media/0/GT-P5100-UPDATE2-backup')
  if case in ['repeat','rollback','bad-backup']:
   r=run();assert r.returncode==0,(case,r.stdout,r.stderr)
  if case=='rollback':(backup/'ROLLBACK').write_text('rollback')
  if case=='wrong-apk':app.write_bytes(b'other app')
  if case=='wrong-library':lib.write_bytes(b'other lib')
  if case=='wrong-boot':block.write_bytes(b'other boot')
  if case=='bad-backup':(backup/'cronet.so').write_bytes(b'corrupt backup')
  if case=='write-failure':p.write_text(script.replace('cat "$payload/boot.img" > "$block"','false # injected error'))
  before=(lib.read_bytes(),block.read_bytes());r=run()
  success=case in ['install','repeat','rollback','preserve-metadata']
  assert (r.returncode==0)==success,(case,r.stdout,r.stderr)
  after=(lib.read_bytes(),block.read_bytes())
  if not success:assert after==before,case
  elif case=='rollback':assert after==(bad,old+bytes(8388608-len(old)))
  else:assert after==(good,new)
  if case=='preserve-metadata':
   s=lib.stat();assert (s.st_ino,s.st_mode,s.st_uid,s.st_gid)==(original_stat.st_ino,original_stat.st_mode,original_stat.st_uid,original_stat.st_gid)
  results.append(dict(case=case,passed=True))
print(json.dumps(results,indent=2))
pathlib.Path('test-results.json').write_text(json.dumps(results,indent=2))

