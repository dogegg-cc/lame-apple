// swift-tools-version: 5.9
import PackageDescription

// 本地开发先运行 Scripts/build.py；远端发布清单由 package_release.py 单独生成。
let package = Package(
    name: "LAMEApple",
    platforms: [.iOS(.v17)],
    products: [.library(name: "LAME", targets: ["LAME"])],
    targets: [
        .binaryTarget(name: "LAME", path: "Artifacts/LAME.xcframework"),
    ]
)
