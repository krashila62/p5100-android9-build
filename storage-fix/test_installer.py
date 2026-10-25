"""Exercise the real installer control flow against disposable regular files.
Does not emulate a block device, TWRP Edify, SELinux, or Android hardware.
"""
import pathlib,tempfile,subprocess,hashlib,re,json
source=(pathlib.Path(__file__).parent/'install-candidate.sh').read_text()
sha=lambda b:hashlib.sha1(b).hexdigest()
old=b'old boot';new=b'new boot';oldsd=b'old sdcard';newsd=b'new sdcard';display=b'preserved display'
hashes=re.findall(r"[0-9a-f]{40}",source)
# First appearances: old sdcard, new sdcard, new boot, display, old boot.
unique=list(dict.fromkeys(hashes));assert len(unique)==5
for a,b in zip(unique,[oldsd,newsd,new,display,old]):source=source.replace(a,sha(b))
lengths=list(dict.fromkeys(re.findall(r'head -c (\d+)',source)));assert len(lengths)==2
source=source.replace('head -c '+lengths[0],'head -c '+str(len(old)))
source=source.replace('head -c '+lengths[1],'head -c '+str(len(new)))
results=[]
for case in ['install','repeat','rollback','bad-payload','bad-display','corrupt-backup','write-failure']:
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp)
  paths=['/data/media/0','/system/bin','/system/lib','/tmp/p5100-integrated','/sys/class/block/mmcblk0p5','/proc','/dev/block/platform/omap_hsmmc.1/by-name']
  for p in paths:(root/p.lstrip('/')).mkdir(parents=True)
  def path(p):return root/p.lstrip('/')
  block=path('/dev/block/platform/omap_hsmmc.1/by-name/KERNEL');block.write_bytes(old+bytes(8388608-len(old)))
  path('/system/bin/sdcard').write_bytes(oldsd);path('/system/lib/libsuspend.so').write_bytes(display)
  path('/tmp/p5100-integrated/boot.img').write_bytes(new);path('/tmp/p5100-integrated/sdcard').write_bytes(newsd)
  path('/sys/class/block/mmcblk0p5/size').write_text('16384\n');path('/proc/mounts').write_text('dev /data ext4 rw 0 0\ndev /system ext4 rw 0 0\n')
  script=source.replace('test -b "$block"','test -f "$block"')
  # Rewrite only absolute path literals; mount-table patterns remain intact.
  script=re.sub(r'/(?:dev|data|system|tmp|sys|proc)/[A-Za-z0-9_./-]+',lambda m:str(root/m.group(0).lstrip('/')),script)
  script=script.replace('set -eu','set -eu\nchown() { :; }\nchcon() { :; }',1)
  p=root/'install.sh';p.write_text(script)
  run=lambda:subprocess.run(['sh',str(p)],capture_output=True,text=True)
  if case in ['repeat','rollback','corrupt-backup']:
   r=run();assert r.returncode==0,r.stderr
  backup=path('/data/media/0/GT-P5100-INTEGRATED-backup')
  if case=='rollback':(backup/'ROLLBACK').write_text('rollback')
  if case=='bad-payload':path('/tmp/p5100-integrated/sdcard').write_bytes(b'corrupt')
  if case=='bad-display':path('/system/lib/libsuspend.so').write_bytes(b'other display')
  if case=='corrupt-backup':(backup/'sdcard').write_bytes(b'corrupt')
  if case=='write-failure':p.write_text(script.replace('cat "$payload/boot.img" > "$block"','false # injected write error'))
  before=(block.read_bytes(),path('/system/bin/sdcard').read_bytes())
  r=run()
  success=case in ['install','repeat','rollback']
  assert (r.returncode==0)==success,(case,r.stdout,r.stderr)
  after=(block.read_bytes(),path('/system/bin/sdcard').read_bytes())
  if case in ['bad-payload','bad-display','corrupt-backup','write-failure']:assert before==after,case
  elif case=='rollback':assert after==(old+bytes(8388608-len(old)),oldsd)
  else:assert after==(new,newsd)
  results.append({'case':case,'pass':True})
print(json.dumps(results,indent=2))

