// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LAMEPackageProbe",
    platforms: [.iOS(.v17)],
    products: [.library(name: "LAMEPackageProbe", targets: ["LAMEPackageProbe"])],
    dependencies: [.package(path: "../..")],
    targets: [
        .target(name: "LAMEPackageProbe", dependencies: [.product(name: "LAME", package: "lame-apple")]),
    ]
)
