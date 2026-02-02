# Notta Brand Style Guide

## Brand Essence

**Personality:** Friendly, playful, approachable - but competent. Think Pixar meets productivity app.

**Tone:** Warm, slightly irreverent, human. Not corporate. Not childish either - professional with personality.

**Core feeling:** "This tool is fun to use and actually works."

---

## Color Palette

### Primary Colors

| Color | Hex | Usage |
|-------|-----|-------|
| **Warm Orange** | `#F5A623` | Primary brand color, CTAs, highlights |
| **Sunny Yellow** | `#FFD54F` | Backgrounds, gradients, energy |
| **Deep Navy** | `#2C3E50` | Text, headers, contrast |

### Secondary Colors

| Color | Hex | Usage |
|-------|-----|-------|
| **Sky Blue** | `#4A90D9` | Accents, links, tie color callback |
| **Soft White** | `#FFF9F0` | Backgrounds, cards |
| **Warm Gray** | `#7F8C8D` | Secondary text, borders |

### Accent Colors

| Color | Hex | Usage |
|-------|-----|-------|
| **Success Green** | `#27AE60` | Confirmations, "after" state |
| **Alert Red** | `#E74C3C` | Errors only (sparingly) |

### Gradients

**Hero Gradient:** `#FFD54F` → `#F5A623` (top to bottom)
**Subtle Gradient:** `#FFF9F0` → `#FFEFD5` (cards, sections)

---

## Typography

### Primary Font: Inter (or similar clean sans-serif)
- Modern, highly readable
- Works at all sizes
- Free on Google Fonts

### Weights
- **Headlines:** Inter Bold (700)
- **Subheads:** Inter Semi-Bold (600)
- **Body:** Inter Regular (400)
- **Small text:** Inter Medium (500)

### Alternative: Nunito
- Slightly rounder, more playful
- Good for a warmer feel
- Pairs well with the Pixar aesthetic

### Type Scale
```
Hero:     48-64px / Bold
H1:       36-40px / Bold
H2:       28-32px / Semi-Bold
H3:       22-24px / Semi-Bold
Body:     16-18px / Regular
Small:    14px / Medium
Caption:  12px / Regular
```

---

## Visual Style

### Illustration Style
- **3D Pixar-style** characters and scenes
- Warm, soft lighting
- Rounded edges, friendly forms
- Consistent character (glasses chimp) as mascot

### Photography (if needed)
- Warm color grading
- Natural lighting
- Real people in real environments
- Avoid stock photo feel

### Iconography
- Rounded, friendly icons
- 2px stroke weight
- Match primary color palette
- Consider custom 3D icons for key features

### Shadows & Depth
- Soft, warm shadows
- `box-shadow: 0 4px 20px rgba(245, 166, 35, 0.15)`
- Subtle depth, not flat design

### Border Radius
- Buttons: `12px`
- Cards: `16px`
- Large containers: `24px`
- Inputs: `8px`

---

## Components

### Buttons

**Primary Button**
```css
background: linear-gradient(135deg, #FFD54F, #F5A623);
color: #2C3E50;
padding: 14px 28px;
border-radius: 12px;
font-weight: 600;
box-shadow: 0 4px 15px rgba(245, 166, 35, 0.3);
```

**Secondary Button**
```css
background: transparent;
border: 2px solid #F5A623;
color: #F5A623;
padding: 12px 26px;
border-radius: 12px;
```

**Hover states:** Slight lift (translateY -2px) + enhanced shadow

### Cards
```css
background: #FFF9F0;
border-radius: 16px;
padding: 24px;
box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
```

### Input Fields
```css
background: white;
border: 2px solid #E8E8E8;
border-radius: 8px;
padding: 12px 16px;
/* Focus state */
border-color: #F5A623;
box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.1);
```

---

## Website Layout Recommendations

### Hero Section
- Large hero with mascot character
- Warm gradient background (`#FFD54F` → `#F5A623`)
- Bold headline + subhead
- Single clear CTA: "Download for Mac"
- Product screenshot or demo GIF

### Features Section
- Clean white/soft background
- 3-column feature grid
- Each feature with small illustration or icon
- Short, punchy copy

### How It Works
- Step-by-step with numbered circles
- Before/after visual (chaos chimp → zen chimp)
- Optional: embedded demo video

### Pricing
- Simple 2-column layout
- Free trial emphasized
- Warm highlight on recommended plan

### FAQ
- Accordion style
- Clean typography
- Grouped by topic if many questions

### Footer
- Minimal, clean
- Links + social icons
- Mascot waving goodbye? (optional fun touch)

---

## Mascot Usage

### The Character: "Office Chimp" (name TBD)
- Glasses + tie are signature elements
- Use consistently across all materials
- Expressions can vary: frustrated (problem), happy (solution), thoughtful (features)

### Where to Use
- App icon ✓
- Website hero ✓
- Social media posts ✓
- Empty states in app
- Error pages (confused chimp)
- Success states (celebrating chimp)
- Email headers

### Where NOT to Use
- Legal/formal documents
- Serious error messages about data loss
- Anywhere it would undermine trust

---

## Voice & Tone

### Do
- Use contractions (we're, you'll, it's)
- Be conversational
- Use humor sparingly but effectively
- Speak directly to the user ("you")
- Keep it simple

### Don't
- Be corporate or stiff
- Overuse exclamation points!!!
- Be condescending
- Use jargon
- Make promises you can't keep

### Example Headlines
✓ "Stop typing like a monkey"
✓ "Hold. Speak. Done."
✓ "Your voice, your Mac, your privacy"

✗ "Revolutionary AI-powered voice transcription solution"
✗ "Leverage the power of speech-to-text technology"
✗ "Transform your productivity paradigm"

---

## File Naming & Organization

### Assets
```
/brand
  /logos
    notta-logo-full.svg
    notta-icon-only.svg
    notta-wordmark.svg
  /mascot
    chimp-happy.png
    chimp-frustrated.png
    chimp-thinking.png
    chimp-icon.png
  /colors
    palette.ase (Adobe)
    palette.sketchpalette
  /fonts
    (or links to Google Fonts)
```

---

## Quick Reference

| Element | Value |
|---------|-------|
| Primary Color | `#F5A623` |
| Text Color | `#2C3E50` |
| Background | `#FFF9F0` |
| Font | Inter |
| Border Radius | 12-16px |
| Shadow | Warm, soft |
| Mascot | Chimp with glasses + tie |
| Tone | Friendly, playful, competent |
