#!/bin/bash

# OpenMailBot Thunderbird Add-on - Build Script
# Packages the add-on into an XPI file

set -e

echo "📦 Building OpenMailBot Thunderbird Add-on"
echo "==========================================="
echo ""

cd "$(dirname "$0")"

# Create icons directory if it doesn't exist
if [ ! -d "icons" ]; then
    echo "⚠️  Creating icons directory..."
    mkdir -p icons
    echo "Note: Please add icon files (icon-16.png, icon-32.png, icon-48.png, icon-128.png)"
fi

# Remove old build
if [ -f "openmailbot.xpi" ]; then
    echo "🗑️  Removing old build..."
    rm openmailbot.xpi
fi

# Create XPI (zip file with .xpi extension)
echo "📦 Packaging add-on..."
zip -r openmailbot.xpi \
    manifest.json \
    background.js \
    popup/ \
    options/ \
    icons/ \
    README.md \
    -x "*.DS_Store" "*.git*" "build.sh"

echo ""
echo "✅ Build complete!"
echo ""
echo "📄 File created: openmailbot.xpi"
echo ""
echo "To install:"
echo "1. Open Thunderbird"
echo "2. Go to Tools → Add-ons and Themes"
echo "3. Click gear icon ⚙️ → Install Add-on From File"
echo "4. Select openmailbot.xpi"
echo ""
echo "For testing:"
echo "1. Go to Tools → Developer Tools → Debug Add-ons"
echo "2. Click 'Load Temporary Add-on'"
echo "3. Select manifest.json from this directory"
echo ""
