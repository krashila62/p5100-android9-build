import os, pathlib, subprocess, urllib.request, hashlib, json, base64
root=pathlib.Path(__file__).resolve().parent
def run(*args): subprocess.run(list(map(str,args)),check=True)
for item in json.loads((root/'sources.json').read_text()):
    data=urllib.request.urlopen(item['url'],timeout=60).read()
    if 'format=TEXT' in item['url']: data=base64.b64decode(data)
    assert hashlib.sha256(data).hexdigest()==item['sha256']
    path=root/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
core=root/'core'
run('git','init',core)
run('git','-C',core,'fetch','--depth=1','https://github.com/aosp-mirror/platform_system_core.git','3655b3122e299c619cc42b874077e4952fb5fb21')
run('git','-C',core,'checkout','--detach','FETCH_HEAD')
run('git','-C',core,'apply','--check',root/'bring-back-fuse.patch')
run('git','-C',core,'apply',root/'bring-back-fuse.patch')
ndk=pathlib.Path(os.environ['ANDROID_NDK_LATEST_HOME'])/'toolchains/llvm/prebuilt/linux-x86_64/bin'
cc=ndk/'armv7a-linux-androideabi28-clang';cxx=ndk/'armv7a-linux-androideabi28-clang++'
stubs=root/'link-only';stubs.mkdir(exist_ok=True)
for lib in ['libcutils','libminijail','libpackagelistparser']:
    run(cc,'-shared','-fPIC','-Wl,-soname,'+lib+'.so',root/(lib+'-link-stub.c'),'-o',stubs/(lib+'.so'))
out=pathlib.Path('artifacts');out.mkdir(exist_ok=True)
includes=[root/'include']+[core/p for p in ['base/include','libcutils/include','libutils/include','liblog/include','libpackagelistparser/include','include']]
sources=[core/'sdcard/sdcard.cpp',core/'sdcard/fuse.cpp']+[core/'base'/p for p in ['chrono_utils.cpp','file.cpp','logging.cpp','stringprintf.cpp','strings.cpp','errors_unix.cpp']]
run(cxx,'-std=c++17','-O2','-fPIE','-pie','-static-libstdc++','-Wl,--no-undefined,-z,relro,-z,now','-Wl,--exclude-libs,ALL',*[ '-I'+str(p) for p in includes],*sources,'-L'+str(stubs),'-lcutils','-lminijail','-lpackagelistparser','-llog','-o',out/'sdcard')
with (out/'elf-report.txt').open('w') as f: subprocess.run([str(ndk/'llvm-readelf'),'-h','-d','--dyn-syms',str(out/'sdcard')],stdout=f,check=True)
(out/'sources.json').write_bytes((root/'sources.json').read_bytes())
(out/'NOT-FLASHABLE.txt').write_text('Isolated Android 9 FUSE daemon candidate. Device validation required. Link stubs are not distributed.\n')
(out/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(out.iterdir()) if p.is_file())+'\n')

