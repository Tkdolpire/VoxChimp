#!/bin/bash
#
# Create DMG installer for Notta
# Usage: ./create-dmg.sh /path/to/Notta.app /path/to/output.dmg
#

set -e

# Arguments
APP_PATH="$1"
DMG_PATH="$2"

if [ -z "$APP_PATH" ] || [ -z "$DMG_PATH" ]; then
    echo "Usage: $0 /path/to/Notta.app /path/to/output.dmg"
    exit 1
fi

if [ ! -d "$APP_PATH" ]; then
    echo "Error: App not found at $APP_PATH"
    exit 1
fi

# Configuration
APP_NAME=$(basename "$APP_PATH" .app)
VOLUME_NAME="${APP_NAME}"
DMG_TEMP="${DMG_PATH}.temp.dmg"
DMG_DIR="$(dirname "$DMG_PATH")"
STAGING_DIR="${DMG_DIR}/.dmg-staging"

# Get script directory for background image
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKGROUND_IMG="${SCRIPT_DIR}/Distribution/dmg-background.png"

echo "Creating DMG: ${DMG_PATH}"
echo "  App: ${APP_PATH}"
echo "  Volume: ${VOLUME_NAME}"

# Clean up any previous staging
rm -rf "$STAGING_DIR"
rm -f "$DMG_TEMP"
rm -f "$DMG_PATH"

# Create staging directory
mkdir -p "$STAGING_DIR"

# Copy app to staging
echo "Copying app..."
cp -R "$APP_PATH" "$STAGING_DIR/"

# Create Applications symlink
ln -s /Applications "$STAGING_DIR/Applications"

# Calculate DMG size (app size + 50MB buffer)
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$((APP_SIZE + 50))

echo "Creating DMG image (${DMG_SIZE}MB)..."

# Create temporary DMG
hdiutil create \
    -srcfolder "$STAGING_DIR" \
    -volname "$VOLUME_NAME" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDRW \
    -size "${DMG_SIZE}m" \
    "$DMG_TEMP"

# Mount the temporary DMG
echo "Mounting DMG for customization..."
MOUNT_DIR="/Volumes/${VOLUME_NAME}"

# Unmount if already mounted
if [ -d "$MOUNT_DIR" ]; then
    hdiutil detach "$MOUNT_DIR" -quiet || true
fi

hdiutil attach "$DMG_TEMP" -readwrite -noverify -noautoopen

# Wait for mount
sleep 2

# Check if we have a custom background
if [ -f "$BACKGROUND_IMG" ]; then
    echo "Adding background image..."
    mkdir -p "${MOUNT_DIR}/.background"
    cp "$BACKGROUND_IMG" "${MOUNT_DIR}/.background/background.png"
    BACKGROUND_SET="true"
else
    BACKGROUND_SET="false"
fi

# Use AppleScript to customize the DMG appearance
echo "Customizing DMG appearance..."

if [ "$BACKGROUND_SET" = "true" ]; then
    osascript <<EOF
tell application "Finder"
    tell disk "${VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {400, 100, 900, 450}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set background picture of viewOptions to file ".background:background.png"
        set position of item "${APP_NAME}.app" of container window to {125, 170}
        set position of item "Applications" of container window to {375, 170}
        close
        open
        update without registering applications
        delay 2
        close
    end tell
end tell
EOF
else
    osascript <<EOF
tell application "Finder"
    tell disk "${VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {400, 100, 900, 400}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set position of item "${APP_NAME}.app" of container window to {125, 150}
        set position of item "Applications" of container window to {375, 150}
        close
        open
        update without registering applications
        delay 2
        close
    end tell
end tell
EOF
fi

# Sync and unmount
sync
sleep 2
hdiutil detach "$MOUNT_DIR"

# Convert to compressed DMG
echo "Compressing DMG..."
hdiutil convert "$DMG_TEMP" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_PATH"

# Clean up
rm -f "$DMG_TEMP"
rm -rf "$STAGING_DIR"

# Get final size
FINAL_SIZE=$(ls -lh "$DMG_PATH" | awk '{print $5}')

echo ""
echo "DMG created successfully!"
echo "  Path: ${DMG_PATH}"
echo "  Size: ${FINAL_SIZE}"
