#!/bin/bash

# OpenMailBot - Zoho Mail Extension Build Script
# Creates a production-ready package for Zoho Marketplace

echo "🔨 Building OpenMailBot for Zoho Mail..."

# Set variables
EXTENSION_DIR="zoho-extension"
BUILD_DIR="build/zoho-extension"
PACKAGE_NAME="openmailbot-zoho-$(date +%Y%m%d-%H%M%S).zip"

# Clean previous build
echo "🧹 Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy extension files
echo "📦 Copying extension files..."
cp -r "$EXTENSION_DIR/manifest.json" "$BUILD_DIR/"
cp -r "$EXTENSION_DIR/src" "$BUILD_DIR/"
cp -r "$EXTENSION_DIR/settings" "$BUILD_DIR/"
cp -r "$EXTENSION_DIR/assets" "$BUILD_DIR/" 2>/dev/null || echo "ℹ️  No assets folder found"

# Copy documentation
echo "📄 Copying documentation..."
cp "$EXTENSION_DIR/README.md" "$BUILD_DIR/"

# Validate manifest
echo "✅ Validating manifest.json..."
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found, skipping validation"
else
    if jq empty "$BUILD_DIR/manifest.json" 2>/dev/null; then
        echo "✓ manifest.json is valid JSON"
    else
        echo "❌ manifest.json is invalid!"
        exit 1
    fi
fi

# Create package
echo "📦 Creating package..."
cd build
zip -r "$PACKAGE_NAME" zoho-extension/
cd ..

echo "✨ Build complete!"
echo "📦 Package created: build/$PACKAGE_NAME"
echo ""
echo "Next steps:"
echo "1. Test the extension in Zoho Mail Developer Mode"
echo "2. Upload to Zoho Marketplace for review"
echo ""
