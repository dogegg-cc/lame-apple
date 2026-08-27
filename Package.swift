// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LAMEApple",
    platforms: [.iOS("17.0")],
    products: [.library(name: "LAME", targets: ["LAME"])],
    targets: [
        .binaryTarget(
            name: "LAME",
            url: "https://github.com/dogegg-cc/lame-apple/releases/download/0.1.1/LAME.xcframework.zip",
            checksum: "49e5796c12ed03d2a4bcdb0c77949047e110675f4d2f826132efa58179e856d3"
        ),
    ]
)
