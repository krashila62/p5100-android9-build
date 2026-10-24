"""Build experimental gateway lookup fix; recovery packaging is separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "sources.lock.json"
EXPECTED = {
    "kernel": ("https://github.com/MightyM17/android_kernel_ti_omap4.git",
               "4f4a4b2427c5b09ec0442c0578957322ff4c7ca6"),
    "toolchain": ("https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9",
                  "cb7b3ac1b7fdb49474ff68761909934d1142f594"),
}


def validate():
    config = json.loads(LOCK.read_text(encoding="utf-8"))
    for name, (url, commit) in EXPECTED.items():
        if config[name] != {"url": url, "commit": commit}:
            raise ValueError(f"Unexpected source pin: {name}")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Commit must be a full SHA")
    if config["defconfig"] != "espresso_defconfig":
        raise ValueError("Wrong device configuration")
    if not re.fullmatch(r"[0-9a-f]{64}", config["rom_sha256"]):
        raise ValueError("Invalid reference ROM hash")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate pins without downloads or builds")
    args = parser.parse_args()
    cfg = validate()
    if args.check:
        print("Source pins and device configuration validated; no build performed.")
        return 0
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("Build requires an x86_64 Linux runner")
    build_root = ROOT / "build-work"
    artifact = ROOT / "artifacts"
    if build_root.exists() or artifact.exists():
        raise RuntimeError("Use a fresh checkout; existing directories will not be removed")
    artifact.mkdir()
    status = {"status": "started", "flashable": False, "device_tested": False, "sources": cfg}
    log = (artifact / "build.log").open("w", encoding="utf-8", buffering=1)

    def run(argv, cwd=ROOT, env=None):
        line = "+ " + " ".join(map(str, argv))
        print(line, flush=True)
        log.write(line + "\n")
        process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        result = []
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            result.append(line)
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, argv)
        return "".join(result).strip()

    try:
        (artifact / "NOT-FLASHABLE.txt").write_text(
            "IPv4 gateway lookup fix. No boot.img; device test required.\n"
            "Do not flash zImage to BOOT/KERNEL: it is not an Android boot image.\n"
            "PowerVR external modules and hardware compatibility have NOT been validated.\n"
            "Check result.json: a log artifact can exist even when compilation failed.\n",
            encoding="utf-8")
        if shutil.disk_usage(ROOT).free < 8 * 1024**3:
            raise RuntimeError("Less than 8 GiB available on the runner; refusing to start downloads")
        build_root.mkdir()
        for name in EXPECTED:
            directory = build_root / name
            run(["git", "init", directory])
            run(["git", "-c", "protocol.version=2", "fetch", "--depth=1", cfg[name]["url"],
                 cfg[name]["commit"]], cwd=directory)
            run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=directory)
            actual = run(["git", "rev-parse", "HEAD"], cwd=directory)
            if actual != cfg[name]["commit"]:
                raise RuntimeError(f"Source mismatch: {name}")
        kernel = build_root / "kernel"
        source = kernel / "net/ipv4/fib_semantics.c"
        before = source.read_text()
        old = "\t\t\t\t.flowi4_oif = nh->nh_oif,\n"
        if before.count(old) != 1:
            raise RuntimeError("Unexpected gateway lookup source")
        after = before.replace(old, old + "\t\t\t\t.flowi4_iif = net->loopback_dev->ifindex,\n")
        source.write_text(after)
        import difflib
        (artifact / "routefix1.patch").write_text("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="a/net/ipv4/fib_semantics.c", tofile="b/net/ipv4/fib_semantics.c")))
        # Keep the release string required by original PowerVR binary modules.
        # Build user and patch manifest explicitly identify this modified build.
        (kernel / ".scmversion").write_text("-g4f4a4b24\n")
        status["patch"] = "Set net->loopback_dev->ifindex for local IPv4 gateway validation"
        output = build_root / "kernel-out"
        # Linux 3.4 requires the O= directory to exist before invoking make.
        output.mkdir()
        compiler = build_root / "toolchain/bin/arm-linux-androideabi-"
        status["compiler"] = run([str(compiler) + "gcc", "--version"])
        status["host"] = run(["uname", "-a"])
        status["host_gcc"] = run(["gcc", "--version"])
        env = os.environ.copy()
        env.update({"LC_ALL": "C", "TZ": "UTC", "KBUILD_BUILD_USER": "wifi-routefix1",
                    "KBUILD_BUILD_HOST": "github-actions", "KBUILD_BUILD_VERSION": "1",
                    "KBUILD_BUILD_TIMESTAMP": "Sat Jun 1 13:56:34 UTC 2024"})
        command = ["make", "-C", kernel, f"O={output}", "ARCH=arm", f"CROSS_COMPILE={compiler}"]
        run(command + [cfg["defconfig"]], env=env)
        shutil.copyfile(output / ".config", artifact / "kernel.config")
        run(command + [f"-j{min(os.cpu_count() or 2, 4)}", "zImage", "modules"], env=env)
        for src, target in [(output / "arch/arm/boot/zImage", artifact / "zImage.NOT-FLASHABLE"),
                            (output / "Module.symvers", artifact / "Module.symvers"),
                            (output / "include/config/kernel.release", artifact / "kernel.release")]:
            if not src.is_file() or src.stat().st_size == 0:
                raise RuntimeError(f"Missing or empty build output: {src}")
            shutil.copyfile(src, target)
        # These are kernel-tree modules only, not the external PowerVR driver build.
        for src in output.rglob("*.ko"):
            target = artifact / "kernel-tree-modules" / src.relative_to(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        if source.read_text() != after:
            raise RuntimeError("Patched file changed unexpectedly")
        if run(["git", "diff", "--name-only"], cwd=kernel) != "net/ipv4/fib_semantics.c":
            raise RuntimeError("Unexpected tracked source changes")
        untracked = run(["git", "ls-files", "--others", "--exclude-standard"], cwd=kernel).splitlines()
        if any(p != ".scmversion" for p in untracked):
            raise RuntimeError("Unexpected untracked source files")
        if (artifact / "kernel.release").read_text().strip() != "3.4.112-g4f4a4b24":
            raise RuntimeError("Unexpected module release")
        status["status"] = "compiled_not_device_tested"
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        traceback.print_exc(file=log)
        raise
    finally:
        (artifact / "result.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        shutil.copyfile(LOCK, artifact / LOCK.name)
        log.close()
        sums = []
        for file in sorted(artifact.rglob("*")):
            if file.is_file() and file.name != "SHA256SUMS":
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                sums.append(f"{digest}  {file.relative_to(artifact).as_posix()}")
        (artifact / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())


