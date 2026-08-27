// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LAMEPackageProbe",
    platforms: [.iOS(.v17)],
    products: [.library(name: "LAMEPackageProbe", targets: ["LAMEPackageProbe"])],
    // 固定消费本次生成的本地包，不通过根清单下载已发布版本。
    dependencies: [.package(path: "../../Artifacts")],
    targets: [
        .target(name: "LAMEPackageProbe", dependencies: [.product(name: "LAME", package: "artifacts")]),
    ]
)
