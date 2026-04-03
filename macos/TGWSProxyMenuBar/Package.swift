// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TGWSProxyMenuBar",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "TGWSProxyMenuBar", targets: ["TGWSProxyMenuBar"])
    ],
    targets: [
        .executableTarget(
            name: "TGWSProxyMenuBar",
            path: "Sources"
        )
    ]
)
