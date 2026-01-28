#!/bin/bash
#
# Generate Sparkle appcast.xml for Notta updates
# Usage: ./generate-appcast.sh
#
# Prerequisites:
# - Sparkle framework bin directory in PATH
# - Private key available for signing
#

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist"
APPCAST_FILE="${DIST_DIR}/appcast.xml"

# Configuration - UPDATE THESE FOR YOUR DEPLOYMENT
BASE_URL="https://notta.app/releases"
APP_NAME="Notta"

# Get version info from most recent build
VERSION=$(defaults read "${PROJECT_DIR}/${APP_NAME}/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "1.0.0")
BUILD_NUMBER=$(defaults read "${PROJECT_DIR}/${APP_NAME}/Info.plist" CFBundleVersion 2>/dev/null || echo "1")

ZIP_FILE="${DIST_DIR}/${APP_NAME}-${VERSION}.zip"
DMG_FILE="${DIST_DIR}/${APP_NAME}-${VERSION}.dmg"

echo "Generating appcast.xml for ${APP_NAME} v${VERSION}"

# Check if ZIP exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: ZIP file not found at ${ZIP_FILE}"
    echo "Run build-release.sh first."
    exit 1
fi

# Get file size
FILE_SIZE=$(stat -f%z "$ZIP_FILE" 2>/dev/null || stat -c%s "$ZIP_FILE")

# Get current date in RFC 2822 format
PUB_DATE=$(date -R)

# Try to get Sparkle signature
SIGNATURE=""
if [ -f "${ZIP_FILE}.signature" ]; then
    SIGNATURE=$(cat "${ZIP_FILE}.signature")
elif command -v sign_update &> /dev/null; then
    SIGNATURE=$(sign_update "$ZIP_FILE" 2>/dev/null || echo "")
fi

if [ -z "$SIGNATURE" ]; then
    echo "Warning: No Sparkle signature available."
    echo "The appcast will be created without a signature."
    echo "Users will see a security warning unless you add a signature."
fi

# Generate appcast.xml
cat > "$APPCAST_FILE" << EOF
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${APP_NAME} Updates</title>
    <link>${BASE_URL}/appcast.xml</link>
    <description>Most recent changes with links to updates.</description>
    <language>en</language>

    <item>
      <title>Version ${VERSION}</title>
      <pubDate>${PUB_DATE}</pubDate>
      <sparkle:version>${BUILD_NUMBER}</sparkle:version>
      <sparkle:shortVersionString>${VERSION}</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>14.0</sparkle:minimumSystemVersion>
      <description><![CDATA[
        <h2>What's New in ${APP_NAME} ${VERSION}</h2>
        <ul>
          <li>Bug fixes and performance improvements</li>
        </ul>
        <p>See the full changelog at <a href="https://notta.app/changelog">notta.app/changelog</a></p>
      ]]></description>
      <enclosure
        url="${BASE_URL}/${APP_NAME}-${VERSION}.zip"
        length="${FILE_SIZE}"
        type="application/octet-stream"
EOF

# Add signature if available
if [ -n "$SIGNATURE" ]; then
    echo "        sparkle:edSignature=\"${SIGNATURE}\"" >> "$APPCAST_FILE"
fi

# Close the XML
cat >> "$APPCAST_FILE" << EOF
      />
    </item>
  </channel>
</rss>
EOF

echo ""
echo "Appcast generated: ${APPCAST_FILE}"
echo ""
echo "Contents:"
echo "----------------------------------------"
cat "$APPCAST_FILE"
echo "----------------------------------------"
echo ""
echo "Next steps:"
echo "  1. Update the <description> section with actual release notes"
echo "  2. Upload ${APP_NAME}-${VERSION}.zip to ${BASE_URL}/"
echo "  3. Upload appcast.xml to ${BASE_URL}/"
echo "  4. Update SUFeedURL in Info.plist if needed"

# If we have multiple versions, we should preserve old items
# This basic script only generates for the current version
# For production, consider using Sparkle's generate_appcast tool
