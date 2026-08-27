#!/usr/bin/env python3
"""Resolve and build a published version with an isolated SwiftPM consumer."""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/dogegg-cc/lame-apple.git"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Exact released version; defaults to upstream.json packageVersion")
    args = parser.parse_args()
    config = json.loads((ROOT / "upstream.json").read_text())
    version = args.version or config["packageVersion"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        parser.error("--version must be MAJOR.MINOR.PATCH")
    parent = ROOT / ".build/remote-verification"
    parent.mkdir(parents=True, exist_ok=True)
    # 每次使用独立源码检出、二进制缓存和 DerivedData，不能被本地产物掩盖缺失的发布资产。
    work = Path(tempfile.mkdtemp(prefix=f"{version}-", dir=parent))
    consumer = work / "Consumer"
    source = consumer / "Sources/LAMEPackageProbe"
    source.mkdir(parents=True)
    shutil.copy2(ROOT / "Tests/PackageConsumer/Sources/LAMEPackageProbe/Probe.swift", source / "Probe.swift")
    (consumer / "Package.swift").write_text(
        '// swift-tools-version: 5.9\nimport PackageDescription\n\n'
        'let package = Package(\n    name: "LAMEPackageProbe",\n'
        f'    platforms: [.iOS("{config["minimumIOSVersion"]}")],\n'
        '    products: [.library(name: "LAMEPackageProbe", targets: ["LAMEPackageProbe"])],\n'
        f'    dependencies: [.package(url: "{REPOSITORY}", exact: "{version}")],\n'
        '    targets: [.target(name: "LAMEPackageProbe", dependencies: [\n'
        '        .product(name: "LAME", package: "lame-apple")\n    ])]\n)\n'
    )
    packages = work / "SourcePackages"
    for sdk, platform in (("iphoneos", "iOS"), ("iphonesimulator", "iOS Simulator")):
        log = work / f"{sdk}.log"
        print(f"Remote SPM {version}: {sdk} arm64; log: {log}", flush=True)
        with log.open("w") as handle:
            result = subprocess.run([
                "xcodebuild", "-scheme", "LAMEPackageProbe", "-configuration", "Release",
                "-destination", f"generic/platform={platform}",
                "-derivedDataPath", str(work / f"derived-{sdk}"),
                "-clonedSourcePackagesDirPath", str(packages),
                "-packageCachePath", str(work / "PackageCache"), "-disablePackageRepositoryCache",
                "ARCHS=arm64", "ONLY_ACTIVE_ARCH=YES", "CODE_SIGNING_ALLOWED=NO", "SWIFT_VERSION=6", "build"
            ], cwd=consumer, stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"Remote SPM build failed; see {log}\n{log.read_text(errors='replace')[-5000:]}")
    checkout = packages / "checkouts/lame-apple"
    if (checkout / "Artifacts").exists():
        raise RuntimeError("Remote verification must not depend on a checked-in Artifacts directory")
    manifest = (checkout / "Package.swift").read_text()
    expected_url = f"https://github.com/dogegg-cc/lame-apple/releases/download/{version}/LAME.xcframework.zip"
    if expected_url not in manifest or not re.search(r'checksum:\s*"[a-f0-9]{64}"', manifest):
        raise RuntimeError("Release manifest does not pin the expected binary URL and checksum")
    artifacts = list((packages / "artifacts").rglob("LAME.xcframework"))
    if len(artifacts) != 1:
        raise RuntimeError("Expected one downloaded LAME XCFramework")
    artifact = artifacts[0]
    info = plistlib.loads((artifact / "Info.plist").read_bytes())
    slices = info["AvailableLibraries"]
    if {item["LibraryIdentifier"] for item in slices} != {"ios-arm64", "ios-arm64-simulator"}:
        raise RuntimeError("Unexpected downloaded slices")
    records = {}
    for item in slices:
        binary = artifact / item["LibraryIdentifier"] / item["LibraryPath"] / "LAME"
        records[item["LibraryIdentifier"]] = hashlib.sha256(binary.read_bytes()).hexdigest()
    report = {"version": version, "repository": REPOSITORY, "binaryURL": expected_url,
              "commit": subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip(),
              "built": ["iphoneos-arm64", "iphonesimulator-arm64"], "binarySHA256": records}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: remote SwiftPM download and both Release builds; report: {work / 'report.json'}")


if __name__ == "__main__":
    main()
