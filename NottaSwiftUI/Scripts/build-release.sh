#!/bin/bash
#
# Notta Release Build Script
# Builds, signs, notarizes, and packages Notta for distribution
#
# Prerequisites:
# 1. Apple Developer ID Application certificate in Keychain
# 2. Notarization credentials stored: xcrun notarytool store-credentials "NOTTA_NOTARIZE"
# 3. Sparkle signing keys generated: ./Sparkle.framework/bin/generate_keys
#

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="Notta"
SCHEME="Notta"
BUILD_DIR="${PROJECT_DIR}/build"
DIST_DIR="${PROJECT_DIR}/dist"
ARCHIVE_PATH="${BUILD_DIR}/${PROJECT_NAME}.xcarchive"
EXPORT_PATH="${BUILD_DIR}/Export"
APP_PATH="${EXPORT_PATH}/${PROJECT_NAME}.app"

# Get version from Info.plist
VERSION=$(defaults read "${PROJECT_DIR}/${PROJECT_NAME}/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "1.0.0")
BUILD_NUMBER=$(defaults read "${PROJECT_DIR}/${PROJECT_NAME}/Info.plist" CFBundleVersion 2>/dev/null || echo "1")

# Notarization profile name (stored with: xcrun notarytool store-credentials)
NOTARIZE_PROFILE="NOTTA_NOTARIZE"

# Output filenames
DMG_NAME="${PROJECT_NAME}-${VERSION}.dmg"
ZIP_NAME="${PROJECT_NAME}-${VERSION}.zip"

echo "============================================"
echo "Building ${PROJECT_NAME} v${VERSION} (${BUILD_NUMBER})"
echo "============================================"

# Clean previous build
echo ""
echo "Step 1: Cleaning previous build..."
rm -rf "${BUILD_DIR}"
rm -rf "${DIST_DIR}"
mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

# Archive the project
echo ""
echo "Step 2: Creating archive..."
xcodebuild archive \
    -project "${PROJECT_DIR}/${PROJECT_NAME}.xcodeproj" \
    -scheme "${SCHEME}" \
    -archivePath "${ARCHIVE_PATH}" \
    -configuration Release \
    CODE_SIGN_STYLE=Manual \
    | xcpretty || xcodebuild archive \
    -project "${PROJECT_DIR}/${PROJECT_NAME}.xcodeproj" \
    -scheme "${SCHEME}" \
    -archivePath "${ARCHIVE_PATH}" \
    -configuration Release \
    CODE_SIGN_STYLE=Manual

# Export the archive
echo ""
echo "Step 3: Exporting archive..."
xcodebuild -exportArchive \
    -archivePath "${ARCHIVE_PATH}" \
    -exportPath "${EXPORT_PATH}" \
    -exportOptionsPlist "${PROJECT_DIR}/ExportOptions.plist"

# Verify the app exists
if [ ! -d "${APP_PATH}" ]; then
    echo "Error: App not found at ${APP_PATH}"
    exit 1
fi

# Submit for notarization
echo ""
echo "Step 4: Submitting for notarization..."
echo "This may take several minutes..."

xcrun notarytool submit "${APP_PATH}" \
    --keychain-profile "${NOTARIZE_PROFILE}" \
    --wait

# Staple the notarization ticket
echo ""
echo "Step 5: Stapling notarization ticket to app..."
xcrun stapler staple "${APP_PATH}"

# Verify notarization
echo ""
echo "Step 6: Verifying notarization..."
spctl -a -v "${APP_PATH}"

# Create DMG
echo ""
echo "Step 7: Creating DMG..."
"${PROJECT_DIR}/Scripts/create-dmg.sh" "${APP_PATH}" "${DIST_DIR}/${DMG_NAME}"

# Notarize the DMG
echo ""
echo "Step 8: Notarizing DMG..."
xcrun notarytool submit "${DIST_DIR}/${DMG_NAME}" \
    --keychain-profile "${NOTARIZE_PROFILE}" \
    --wait

xcrun stapler staple "${DIST_DIR}/${DMG_NAME}"

# Create ZIP for Sparkle
echo ""
echo "Step 9: Creating ZIP for Sparkle updates..."
ditto -c -k --keepParent "${APP_PATH}" "${DIST_DIR}/${ZIP_NAME}"

# Generate appcast signature (if Sparkle keys exist)
if command -v sign_update &> /dev/null; then
    echo ""
    echo "Step 10: Generating Sparkle signature..."
    SIGNATURE=$(sign_update "${DIST_DIR}/${ZIP_NAME}" 2>/dev/null || echo "")
    if [ -n "${SIGNATURE}" ]; then
        echo "Sparkle signature: ${SIGNATURE}"
        echo "${SIGNATURE}" > "${DIST_DIR}/${ZIP_NAME}.signature"
    fi
else
    echo ""
    echo "Note: sign_update not found. Skipping Sparkle signature."
    echo "To sign for Sparkle, add the Sparkle bin directory to your PATH."
fi

# Summary
echo ""
echo "============================================"
echo "Build Complete!"
echo "============================================"
echo ""
echo "Outputs:"
echo "  DMG: ${DIST_DIR}/${DMG_NAME}"
echo "  ZIP: ${DIST_DIR}/${ZIP_NAME}"
echo ""
echo "Verification:"
spctl -a -v "${DIST_DIR}/${DMG_NAME}" 2>&1 | head -1
echo ""
echo "Next steps:"
echo "  1. Upload ${DMG_NAME} to your website"
echo "  2. Upload ${ZIP_NAME} to your update server"
echo "  3. Update appcast.xml with the new version"
echo "  4. Test the update mechanism"
