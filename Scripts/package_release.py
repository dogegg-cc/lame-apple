#!/usr/bin/env python3
"""Prepare release assets locally. Never creates a tag, repository or remote release."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", help="Optional GitHub OWNER/REPO; generates the remote Package.swift")
    parser.add_argument("--update-manifest", action="store_true", help="Also replace the root Package.swift with the generated remote manifest")
    args = parser.parse_args()
    if args.repository and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("--repository must be OWNER/REPO")
    if args.update_manifest and not args.repository:
        parser.error("--update-manifest requires --repository")
    config = json.loads((ROOT / "upstream.json").read_text())
    build_info = ROOT / "Artifacts/build-info.json"
    record = json.loads(build_info.read_text())
    if record["upstream"] != config:
        raise RuntimeError("Artifacts do not match upstream.json; rebuild first")
    if hashlib.sha256((ROOT / config["archive"]).read_bytes()).hexdigest() != config["sha256"]:
        raise RuntimeError("Upstream source archive checksum mismatch")
    # 构建记录未变不代表磁盘上的二进制未变，打包前再次核对实际产物。
    for item in record["slices"]:
        identifier = "ios-arm64" if item["sdk"] == "iphoneos" else "ios-arm64-simulator"
        binary = ROOT / "Artifacts/LAME.xcframework" / identifier / "LAME.framework/LAME"
        if hashlib.sha256(binary.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Binary changed after build: {identifier}; rebuild and verify first")
    verification = ROOT / ".build/verification/verification.json"
    if json.loads(verification.read_text())["buildInfoSHA256"] != hashlib.sha256(build_info.read_bytes()).hexdigest():
        raise RuntimeError("Run verify.py against the current build before packaging")
    destination = ROOT / "Release" / config["packageVersion"]
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "LAME.xcframework.zip"
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--keepParent",
                    str(ROOT / "Artifacts/LAME.xcframework"), str(archive)], check=True)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / "LAME.xcframework.zip.sha256").write_text(f"{checksum}  {archive.name}\n")
    manifest = destination / "Package.swift"
    if args.repository:
        url = f'https://github.com/{args.repository}/releases/download/{config["packageVersion"]}/{archive.name}'
        manifest.write_text(
            '// swift-tools-version: 5.9\nimport PackageDescription\n\n'
            'let package = Package(\n    name: "LAMEApple",\n'
            f'    platforms: [.iOS("{config["minimumIOSVersion"]}")],\n'
            '    products: [.library(name: "LAME", targets: ["LAME"])],\n'
            '    targets: [\n        .binaryTarget(\n            name: "LAME",\n'
            f'            url: "{url}",\n            checksum: "{checksum}"\n'
            '        )\n    ]\n)\n'
        )
        if args.update_manifest:
            # 显式更新后再归档源码，使发布提交、源码包和二进制清单一致。
            shutil.copy2(manifest, ROOT / "Package.swift")
    elif manifest.exists():
        manifest.unlink()
    # 源码归档与许可证跟随二进制分发，不让下载者依赖一个可能失效的外部链接。
    shutil.copy2(ROOT / config["archive"], destination / Path(config["archive"]).name)
    shutil.copy2(build_info, destination / build_info.name)
    shutil.copy2(ROOT / "upstream.json", destination / "upstream.json")
    shutil.copytree(ROOT / "Licenses", destination / "Licenses", dirs_exist_ok=True)
    for name in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "VALIDATION.md"):
        shutil.copy2(ROOT / name, destination / name)
    with tempfile.TemporaryDirectory(prefix="source-", dir=destination) as temporary:
        snapshot = Path(temporary) / "lame-apple"
        snapshot.mkdir()
        for name in ("Scripts", "Tests", "Vendor", "Licenses"):
            shutil.copytree(ROOT / name, snapshot / name,
                            ignore=shutil.ignore_patterns(".build", ".swiftpm", "__pycache__", "*.pyc"))
        for name in ("Package.swift", "upstream.json", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "VALIDATION.md", "AGENTS.md", "LICENSE", ".swiftformat", ".gitignore"):
            shutil.copy2(ROOT / name, snapshot / name)
        subprocess.run(["/usr/bin/ditto", "-c", "-k", "--keepParent", str(snapshot),
                        str(destination / f'lame-apple-{config["packageVersion"]}-source.zip')], check=True)
    print(f"Prepared {destination}")
    print(f"SHA-256: {checksum}")
    print("No upload, tag or remote repository has been created.")


if __name__ == "__main__":
    main()
