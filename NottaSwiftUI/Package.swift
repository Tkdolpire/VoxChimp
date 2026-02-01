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
    dependencies: [
        .package(url: "https://github.com/argmaxinc/WhisperKit.git", from: "0.9.0")
    ],
    targets: [
        .executableTarget(
            name: "Notta",
            dependencies: [
                .product(name: "WhisperKit", package: "WhisperKit")
            ],
            path: "Notta",
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "NottaTests",
            dependencies: ["Notta"],
            path: "NottaTests"
        )
    ]
)
