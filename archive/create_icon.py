#!/usr/bin/env python3
"""Create a simple microphone icon for the Voice Dictation app"""

import os
from PIL import Image, ImageDraw

# Create a 512x512 image with transparent background
size = 512
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Define colors
mic_color = (66, 133, 244, 255)  # Google Blue
highlight_color = (255, 255, 255, 100)  # White highlight

# Draw microphone body (rounded rectangle)
mic_width = 140
mic_height = 200
mic_x = (size - mic_width) // 2
mic_y = size // 2 - 150

# Main microphone body
draw.rounded_rectangle(
    [(mic_x, mic_y), (mic_x + mic_width, mic_y + mic_height)],
    radius=70,
    fill=mic_color
)

# Draw microphone stand
stand_width = 20
stand_height = 100
stand_x = (size - stand_width) // 2
stand_y = mic_y + mic_height - 10

draw.rectangle(
    [(stand_x, stand_y), (stand_x + stand_width, stand_y + stand_height)],
    fill=mic_color
)

# Draw base
base_width = 100
base_height = 20
base_x = (size - base_width) // 2
base_y = stand_y + stand_height - 10

draw.rounded_rectangle(
    [(base_x, base_y), (base_x + base_width, base_y + base_height)],
    radius=10,
    fill=mic_color
)

# Draw sound waves (curved lines)
wave_color = (66, 133, 244, 180)
for i in range(3):
    offset = 30 + i * 25
    # Left wave
    draw.arc(
        [(mic_x - offset - 30, mic_y - 20), 
         (mic_x - offset + 30, mic_y + mic_height - 50)],
        start=60, end=120, fill=wave_color, width=8
    )
    # Right wave
    draw.arc(
        [(mic_x + mic_width + offset - 30, mic_y - 20), 
         (mic_x + mic_width + offset + 30, mic_y + mic_height - 50)],
        start=60, end=120, fill=wave_color, width=8
    )

# Save as PNG
output_path = os.path.expanduser('~/Documents/VoiceDictation/VoiceDictation.app/Contents/Resources/AppIcon.png')
img.save(output_path, 'PNG')

print(f"Icon created at: {output_path}")

# Also create an .icns file for macOS (requires iconutil)
iconset_path = os.path.expanduser('~/Documents/VoiceDictation/VoiceDictation.app/Contents/Resources/AppIcon.iconset')
os.makedirs(iconset_path, exist_ok=True)

# Create multiple sizes for iconset
sizes = [16, 32, 128, 256, 512]
for s in sizes:
    resized = img.resize((s, s), Image.Resampling.LANCZOS)
    resized.save(f"{iconset_path}/icon_{s}x{s}.png")
    resized.save(f"{iconset_path}/icon_{s}x{s}@2x.png")

print("Iconset created. Converting to .icns...")
os.system(f"iconutil -c icns {iconset_path} -o {os.path.expanduser('~/Documents/VoiceDictation/VoiceDictation.app/Contents/Resources/AppIcon.icns')}")
os.system(f"rm -rf {iconset_path}")
print("Icon conversion complete!")