# Icon Placeholders

The Thunderbird add-on requires icon files in the following sizes:

- `icon-16.png` - 16x16 pixels (toolbar icon)
- `icon-32.png` - 32x32 pixels (popup icon)
- `icon-48.png` - 48x48 pixels (add-ons manager)
- `icon-128.png` - 128x128 pixels (add-ons manager detail view)

## Creating Icons

You can create icons using:

1. **Design Tool**: Use Figma, Adobe Illustrator, or similar
2. **Online Generator**: Use https://favicon.io/ or similar services
3. **Export from Logo**: If you have an OpenMailBot logo

## Icon Design Guidelines

- Use the OpenMailBot robot emoji 🤖 or a mail envelope with AI elements
- Keep design simple and recognizable at small sizes
- Use OpenMailBot brand colors (purple/blue gradient)
- Ensure icons work on both light and dark backgrounds
- Save as PNG with transparency

## Quick Icon Generation

For testing, you can use these commands to generate placeholder icons:

```bash
# Install ImageMagick (if not already installed)
# macOS: brew install imagemagick
# Ubuntu: sudo apt-get install imagemagick

# Generate placeholder icons with text
convert -size 16x16 xc:purple -pointsize 10 -fill white -gravity center \
  -annotate +0+0 "🤖" icon-16.png

convert -size 32x32 xc:purple -pointsize 20 -fill white -gravity center \
  -annotate +0+0 "🤖" icon-32.png

convert -size 48x48 xc:purple -pointsize 30 -fill white -gravity center \
  -annotate +0+0 "🤖" icon-48.png

convert -size 128x128 xc:purple -pointsize 80 -fill white -gravity center \
  -annotate +0+0 "🤖" icon-128.png
```

## Temporary Solution

Until proper icons are created, the add-on will use default Thunderbird icons.
The add-on will still function normally without custom icons.
