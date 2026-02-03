#!/bin/bash
# Notta Build Script
# Builds the macOS app with optional signing and DMG creation

set -e

# Configuration
APP_NAME="Notta"
BUNDLE_ID="com.tyrondolpire.notta"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
CREATE_DMG=false
SIGN_APP=false
CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dmg)
            CREATE_DMG=true
            shift
            ;;
        --sign)
            SIGN_APP=true
            shift
            ;;
        --identity)
            CODESIGN_IDENTITY="$2"
            SIGN_APP=true
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dmg              Create DMG installer after build"
            echo "  --sign             Sign the app (uses CODESIGN_IDENTITY env var)"
            echo "  --identity ID      Sign with specific identity"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  CODESIGN_IDENTITY  Developer ID for signing"
            exit 0
            ;;
        *)
            echo_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Clean previous builds
echo_info "Cleaning previous builds..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo_error "python3 not found"
    exit 1
fi

# Verify PyInstaller is available
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo_error "PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

# Build the app
echo_info "Building $APP_NAME.app..."
python3 -m PyInstaller "$SCRIPT_DIR/Notta.spec" --noconfirm

# Check build success
if [ ! -d "$DIST_DIR/$APP_NAME.app" ]; then
    echo_error "Build failed - app bundle not found"
    exit 1
fi

echo_info "Build complete: $DIST_DIR/$APP_NAME.app"

# Sign if requested
if [ "$SIGN_APP" = true ]; then
    if [ -z "$CODESIGN_IDENTITY" ]; then
        echo_warn "CODESIGN_IDENTITY not set, skipping signing"
    else
        echo_info "Signing app with identity: $CODESIGN_IDENTITY"

        # Sign the app bundle
        codesign --force --deep --sign "$CODESIGN_IDENTITY" \
            --entitlements "$SCRIPT_DIR/entitlements.plist" \
            --options runtime \
            "$DIST_DIR/$APP_NAME.app"

        # Verify signature
        echo_info "Verifying signature..."
        if codesign --verify --verbose "$DIST_DIR/$APP_NAME.app"; then
            echo_info "Signature verified successfully"
        else
            echo_error "Signature verification failed"
            exit 1
        fi
    fi
fi

# Create DMG if requested
if [ "$CREATE_DMG" = true ]; then
    echo_info "Creating DMG installer..."

    DMG_NAME="$APP_NAME.dmg"
    DMG_PATH="$DIST_DIR/$DMG_NAME"

    # Remove existing DMG
    rm -f "$DMG_PATH"

    # Create DMG
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$DIST_DIR/$APP_NAME.app" \
        -ov -format UDZO \
        "$DMG_PATH"

    # Sign DMG if signing enabled
    if [ "$SIGN_APP" = true ] && [ -n "$CODESIGN_IDENTITY" ]; then
        echo_info "Signing DMG..."
        codesign --force --sign "$CODESIGN_IDENTITY" "$DMG_PATH"
    fi

    echo_info "DMG created: $DMG_PATH"
fi

# Summary
echo ""
echo_info "Build Summary:"
echo "  App: $DIST_DIR/$APP_NAME.app"
if [ "$CREATE_DMG" = true ]; then
    echo "  DMG: $DIST_DIR/$DMG_NAME"
fi
if [ "$SIGN_APP" = true ] && [ -n "$CODESIGN_IDENTITY" ]; then
    echo "  Signed: Yes"
else
    echo "  Signed: No"
fi

echo ""
echo_info "To install: cp -R $DIST_DIR/$APP_NAME.app /Applications/"
