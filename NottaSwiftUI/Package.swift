// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Notta",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "Notta", targets: ["Notta"])
    ],
    targets: [
        .executableTarget(
            name: "Notta",
            path: "Notta",
            resources: [
                .process("Resources")
            ]
        )
    ]
)
