#!/usr/bin/env python3
"""Build unmodified upstream LAME as two arm64 dynamic framework slices."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".build" / "lame"


def output(args):
    return subprocess.check_output(args, text=True).strip()


def run(args, *, cwd=None, env=None, log=None):
    if log is None:
        subprocess.run(args, cwd=cwd, env=env, check=True)
        return
    with log.open("w") as handle:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(errors="replace")[-6000:], file=sys.stderr)
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}")


def fresh_directory(path):
    # 清理边界只允许本工程的生成目录，不能被参数引导到源码或其他工程。
    resolved = path.resolve()
    allowed = [WORK.resolve(), (ROOT / "Artifacts").resolve()]
    if not any(base in resolved.parents for base in allowed):
        raise ValueError(f"Not a generated child directory: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def build_slice(source, config, sdk, jobs):
    platform = "ios" if sdk == "iphoneos" else "ios-simulator"
    folder = WORK / platform
    fresh_directory(folder)
    sdk_path = output(["xcrun", "--sdk", sdk, "--show-sdk-path"])
    compiler = output(["xcrun", "--sdk", sdk, "--find", "clang"])
    minimum = config["minimumIOSVersion"]
    target = f"arm64-apple-ios{minimum}" + ("-simulator" if sdk != "iphoneos" else "")
    # Libtool 会过滤 -target；同时传递它保留的 -arch/-m 参数，确保最终链接仍是 iOS 17。
    minimum_flag = f"-miphoneos-version-min={minimum}" if sdk == "iphoneos" else f"-mios-simulator-version-min={minimum}"
    flags = shlex.join(["-target", target, "-arch", "arm64", minimum_flag,
                        "-isysroot", sdk_path, "-O2", "-fPIC", "-std=gnu11"])
    pkg_config = shutil.which("pkg-config")
    if pkg_config is None:
        raise RuntimeError("pkg-config is required by upstream configure")
    empty_packages = folder / "empty-pkgconfig"
    empty_packages.mkdir()
    env = os.environ.copy()
    # 禁止从开发机的 Homebrew/pkg-config 偷带 macOS 库进入 iOS 产物。
    for key in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "SDKROOT", "MACOSX_DEPLOYMENT_TARGET", "IPHONEOS_DEPLOYMENT_TARGET"):
        env.pop(key, None)
    env.update({
        "CC": shlex.quote(compiler), "CFLAGS": flags,
        "CPPFLAGS": "", "LDFLAGS": flags, "LIBS": "",
        "PKG_CONFIG": pkg_config, "PKG_CONFIG_PATH": "", "PKG_CONFIG_LIBDIR": str(empty_packages),
        "PKG_CONFIG_SYSROOT_DIR": sdk_path,
        "AR": output(["xcrun", "--sdk", sdk, "--find", "ar"]),
        "RANLIB": output(["xcrun", "--sdk", sdk, "--find", "ranlib"]),
    })
    configure = [
        str(source / "configure"), "--host=aarch64-apple-darwin",
        "--enable-shared", "--disable-static", "--disable-decoder",
        "--disable-frontend", "--disable-analyzer-hooks", "--disable-nasm",
        "--disable-cpml", "--disable-gtktest", "--with-fileio=lame",
        f"--prefix={folder / 'install'}",
    ]
    print(f"[{platform}] configure", flush=True)
    run(configure, cwd=folder, env=env, log=folder / "configure.log")
    print(f"[{platform}] compile arm64 encoder", flush=True)
    run(["make", "-C", "libmp3lame", f"-j{jobs}"], cwd=folder, env=env, log=folder / "make.log")
    framework = folder / "LAME.framework"
    (framework / "Headers").mkdir(parents=True)
    (framework / "Modules").mkdir()
    binary = framework / "LAME"
    shutil.copy2((folder / "libmp3lame/.libs/libmp3lame.dylib").resolve(), binary)
    run(["xcrun", "install_name_tool", "-id", "@rpath/LAME.framework/LAME", str(binary)])
    shutil.copy2(source / "include/lame.h", framework / "Headers/lame.h")
    # 直接使用官方头文件，避免默认不区分大小写的磁盘上 LAME.h 覆盖 lame.h。
    (framework / "Modules/module.modulemap").write_text(
        'framework module LAME {\n  umbrella header "lame.h"\n  export *\n  module * { export * }\n}\n'
    )
    info = {
        "CFBundleDevelopmentRegion": "en", "CFBundleExecutable": "LAME",
        "CFBundleIdentifier": "org.lame-apple.LAME", "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "LAME", "CFBundlePackageType": "FMWK",
        "CFBundleShortVersionString": config["packageVersion"], "CFBundleVersion": "1",
        "CFBundleSupportedPlatforms": ["iPhoneOS" if sdk == "iphoneos" else "iPhoneSimulator"],
        "MinimumOSVersion": minimum,
    }
    with (framework / "Info.plist").open("wb") as handle:
        plistlib.dump(info, handle)
    # LAME 本身只做传入 PCM 的计算，不声明跟踪、数据收集或必需理由 API。
    with (framework / "PrivacyInfo.xcprivacy").open("wb") as handle:
        plistlib.dump({"NSPrivacyTracking": False, "NSPrivacyTrackingDomains": [],
                      "NSPrivacyCollectedDataTypes": [], "NSPrivacyAccessedAPITypes": []}, handle)
    licenses = framework / "Licenses"
    licenses.mkdir()
    for name in ("COPYING", "LICENSE"):
        shutil.copy2(source / name, licenses / name)
    architecture = output(["xcrun", "lipo", "-archs", str(binary)])
    dependencies = output(["xcrun", "otool", "-L", str(binary)])
    if architecture != "arm64":
        raise RuntimeError(f"Unexpected architecture: {architecture}")
    build_version = output(["xcrun", "vtool", "-show-build", str(binary)])
    platform_name = "IOS" if sdk == "iphoneos" else "IOSSIMULATOR"
    if f"platform {platform_name}\n" not in build_version or f"minos {minimum}\n" not in build_version:
        raise RuntimeError(f"Unexpected Mach-O platform or minimum OS:\n{build_version}")
    for line in dependencies.splitlines()[1:]:
        library = line.strip().split(" (", 1)[0]
        if library != "@rpath/LAME.framework/LAME" and not library.startswith(("/usr/lib/", "/System/Library/")):
            raise RuntimeError(f"Unexpected dependency: {library}")
    if "MH_DYLIB" not in output(["xcrun", "otool", "-hv", str(binary)]) and "DYLIB" not in output(["xcrun", "otool", "-hv", str(binary)]):
        raise RuntimeError("Expected a dynamic library")
    run(["/usr/bin/codesign", "--force", "--sign", "-", str(framework)])
    return framework, {"sdk": sdk, "sdkVersion": output(["xcrun", "--sdk", sdk, "--show-sdk-version"]),
                       "target": target, "configureArguments": [arg.replace(str(folder), "$BUILD_DIR") for arg in configure[1:]],
                       "dependencies": dependencies.splitlines()[1:],
                       "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 8))
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    config = json.loads((ROOT / "upstream.json").read_text())
    archive = ROOT / config["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != config["sha256"]:
        raise RuntimeError("Upstream SHA-256 mismatch; refusing to build")
    extraction = WORK / "source"
    fresh_directory(extraction)
    with tarfile.open(archive) as tar:
        # 明确启用安全解包过滤，不允许归档中的路径逃出生成目录。
        tar.extractall(extraction, filter="data")
    source = extraction / config["sourceDirectory"]
    records = []
    frameworks = []
    for sdk in ("iphoneos", "iphonesimulator"):
        framework, record = build_slice(source, config, sdk, args.jobs)
        frameworks.append(framework)
        records.append(record)
    artifacts = ROOT / "Artifacts"
    artifacts.mkdir(exist_ok=True)
    target = artifacts / "LAME.xcframework"
    if target.exists():
        shutil.rmtree(target)
    command = ["xcodebuild", "-create-xcframework"]
    for framework in frameworks:
        command += ["-framework", str(framework)]
    run(command + ["-output", str(target)])
    record = {"upstream": config, "xcode": output(["xcodebuild", "-version"]),
              "compiler": output(["xcrun", "clang", "--version"]), "slices": records}
    (artifacts / "build-info.json").write_text(json.dumps(record, indent=2) + "\n")
    # 本地测试只消费本次构建；根清单留给远端分发，不随开发构建改写。
    (artifacts / "Package.swift").write_text(
        '// swift-tools-version: 5.9\nimport PackageDescription\n\n'
        'let package = Package(\n    name: "LAMEApple",\n'
        f'    platforms: [.iOS("{config["minimumIOSVersion"]}")],\n'
        '    products: [.library(name: "LAME", targets: ["LAME"])],\n'
        '    targets: [.binaryTarget(name: "LAME", path: "LAME.xcframework")]\n)\n'
    )
    print(f"Built {target}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
