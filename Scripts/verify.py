#!/usr/bin/env python3
"""Compile Swift 6 for both slices and run PCM -> MP3 -> PCM on an arm64 simulator."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def output(command):
    return subprocess.check_output(command, text=True).strip()


def run(command):
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Available iOS simulator UDID; booted temporarily if necessary")
    args = parser.parse_args()
    if platform.machine() != "arm64":
        parser.error("Only Apple Silicon hosts are supported")
    config = json.loads((ROOT / "upstream.json").read_text())
    build_info = (ROOT / "Artifacts/build-info.json").read_bytes()
    artifact = ROOT / "Artifacts/LAME.xcframework"
    with (artifact / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    slices = info["AvailableLibraries"]
    if len(slices) != 2 or any(item["SupportedArchitectures"] != ["arm64"] or item["SupportedPlatform"] != "ios" for item in slices):
        raise RuntimeError("Expected exactly two arm64 iOS slices")
    work = ROOT / ".build/verification"
    work.mkdir(parents=True, exist_ok=True)
    simulator_binary = None
    for item in slices:
        simulator = item.get("SupportedPlatformVariant") == "simulator"
        sdk = "iphonesimulator" if simulator else "iphoneos"
        target = f'arm64-apple-ios{config["minimumIOSVersion"]}' + ("-simulator" if simulator else "")
        frameworks = artifact / item["LibraryIdentifier"]
        binary = work / ("smoke-simulator" if simulator else "smoke-device")
        print(f"Swift 6 compile and link: {target}", flush=True)
        run(["xcrun", "--sdk", sdk, "swiftc", "-swift-version", "6", "-strict-concurrency=complete",
             "-sdk", output(["xcrun", "--sdk", sdk, "--show-sdk-path"]), "-target", target,
             "-F", str(frameworks), "-framework", "LAME", "-Xlinker", "-rpath", "-Xlinker", str(frameworks),
             str(ROOT / "Tests/Smoke/main.swift"), "-o", str(binary)])
        if simulator:
            simulator_binary = binary
        print(f"SPM consumer Release build: {sdk} arm64", flush=True)
        log = work / f"spm-{sdk}.log"
        with log.open("w") as handle:
            result = subprocess.run([
                "xcodebuild", "-scheme", "LAMEPackageProbe", "-configuration", "Release",
                "-destination", "generic/platform=" + ("iOS Simulator" if simulator else "iOS"),
                "-derivedDataPath", str(work / f"spm-{sdk}"), "ARCHS=arm64", "ONLY_ACTIVE_ARCH=YES",
                "CODE_SIGNING_ALLOWED=NO", "SWIFT_VERSION=6", "build"
            ], cwd=ROOT / "Tests/PackageConsumer", stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text(errors="replace")[-5000:], file=sys.stderr)
            raise RuntimeError(f"SPM consumer build failed; see {log}")
    if simulator_binary is None:
        raise RuntimeError("Missing simulator slice")
    devices = json.loads(output(["xcrun", "simctl", "list", "devices", "available", "-j"]))["devices"]
    selected = [(runtime, device) for runtime, group in devices.items() if ".iOS-" in runtime
                for device in group if device["udid"] == args.device]
    if len(selected) != 1:
        raise RuntimeError("Select an available iOS simulator UDID")
    runtime, device = selected[0]
    booted_here = device["state"] == "Shutdown"
    if device["state"] not in ("Shutdown", "Booted"):
        raise RuntimeError("Simulator is transitioning; retry when stable")
    try:
        if booted_here:
            run(["xcrun", "simctl", "boot", args.device])
        run(["xcrun", "simctl", "bootstatus", args.device, "-b"])
        print(f'Running on {device["name"]}: {runtime}', flush=True)
        results = work / args.device
        run(["xcrun", "simctl", "spawn", args.device, str(simulator_binary), str(results)])
        report = {"device": device["name"], "runtime": runtime, "udid": args.device,
                  "xcode": output(["xcodebuild", "-version"]),
                  "buildInfoSHA256": hashlib.sha256(build_info).hexdigest(),
                  "smoke": json.loads((results / "results.json").read_text())}
        (work / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        # 仅关闭本次脚本启动的模拟器，不干扰原先已运行的开发会话。
        if booted_here:
            run(["xcrun", "simctl", "shutdown", args.device])
    print(f"Verification report: {work / 'verification.json'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        sys.exit(1)
