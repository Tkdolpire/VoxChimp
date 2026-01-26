#!/usr/bin/env python3
"""
Create a macOS .app bundle for Voice Dictation
This creates a proper app that runs without showing Terminal
"""

import os
import sys
import stat
import subprocess
from pathlib import Path

APP_NAME = "Voice Dictation"
BUNDLE_ID = "com.voicedictation.menubar"

def create_app():
    """Create the .app bundle"""

    # Paths
    script_dir = Path(__file__).parent
    app_dir = script_dir / f"{APP_NAME}.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    # Clean existing app
    if app_dir.exists():
        import shutil
        shutil.rmtree(app_dir)

    # Create directory structure
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    # Create Info.plist
    info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_ID}</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>VoiceDictation</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Voice Dictation needs microphone access to transcribe your speech.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Voice Dictation needs accessibility access to paste transcribed text.</string>
</dict>
</plist>
"""

    with open(contents_dir / "Info.plist", 'w') as f:
        f.write(info_plist)

    # Find Python path
    python_path = sys.executable

    # Create Python launcher (avoids bash, runs directly)
    launcher_script = f"""#!/usr/bin/env python3
# Voice Dictation Launcher
import os
import sys

# Change to script directory
os.chdir("{script_dir}")

# Add to path
sys.path.insert(0, "{script_dir}")

# Import and run
exec(open("{script_dir / 'voice_dictation_menubar.py'}").read())
"""

    launcher_path = macos_dir / "VoiceDictation"
    with open(launcher_path, 'w') as f:
        f.write(launcher_script)

    # Make executable
    os.chmod(launcher_path, os.stat(launcher_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Created: {app_dir}")
    print(f"\nTo use:")
    print(f"  1. Double-click '{APP_NAME}.app' in Finder")
    print(f"  2. Or drag it to your Applications folder")
    print(f"  3. Or add it to Login Items (System Settings > General > Login Items)")
    print(f"\nThe app will appear in your menu bar as a microphone icon.")

    return app_dir


def create_icon():
    """Create a simple icon for the app (optional)"""
    # Note: For a proper icon, you'd need an .icns file
    # This is a placeholder - the app will use a default icon
    pass


if __name__ == "__main__":
    app_path = create_app()

    # Ask if user wants to open the app
    response = input("\nWould you like to launch the app now? (y/n): ")
    if response.lower() == 'y':
        subprocess.Popen(['open', str(app_path)])
        print("App launched! Look for the microphone icon in your menu bar.")
