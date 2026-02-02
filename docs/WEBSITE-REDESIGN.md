# Notta Website Redesign - Implementation Guide

**For:** Development Team  
**Created:** 2026-01-30  
**Brand Style:** Warm Pixar aesthetic (see Brand Style Guide)

---

## Overview

Transform the current dark, tech-focused website into a warm, friendly Pixar-style design using the mascot character throughout.

**Current:** Dark theme, blue accents, minimal/cold
**Target:** Light theme, orange/yellow warmth, playful mascot-driven

---

## Color Palette

Replace these colors throughout:

| Element | Current | New |
|---------|---------|-----|
| Page background | `#0a0a0a` (black) | `#FFF9F0` (warm cream) |
| Text color | `#ffffff` | `#2C3E50` (navy) |
| Primary accent | `#4A90D9` (blue) | `#F5A623` (orange) |
| Secondary accent | Dark gray | `#FFD54F` (yellow) |
| Card backgrounds | Dark gray | `#FFFFFF` with warm shadow |
| CTA buttons | Blue | Orange gradient `#FFD54F → #F5A623` |

---

## Image Assets & Placement

### Asset Library (Google Drive)

All images: [Notta GTM Folder](https://drive.google.com/drive/folders/1jTrrphIUsLxZyuNvzSlACBzurFksnllp)

| Filename | Drive Link | Dimensions |
|----------|------------|------------|
| chaos-chimp.png | [Download](https://drive.google.com/file/d/1ebCBQDYp9B-l8Uwz8FInUb059Zjldak6/view) | 1536x1024 |
| zen-chimp.png | [Download](https://drive.google.com/file/d/11wLgUAXIIlLa1rO1XMH6NprV8tYdNjOV/view) | 1536x1024 |
| step1-hold.png | [Download](https://drive.google.com/file/d/18nlwUSvqSFwz9spCwl9Cn55lNufPVO38/view) | 1024x1024 |
| step2-speak.png | [Download](https://drive.google.com/file/d/14hL-nBn1N9g7XuFWAEWurnT70zVeUaOI/view) | 1024x1024 |
| step3-release.png | [Download](https://drive.google.com/file/d/1tcKGBtApf6_C6NpZq2FdLLrOTZxqLWuk/view) | 1024x1024 |
| celebrating-chimp.png | [Download](https://drive.google.com/file/d/1oOhhdthsRqJ_wKMDF16TUFS8bldSB-XP/view) | 1024x1024 |
| app-icon.png | [Download](https://drive.google.com/file/d/1H0AhuoHUf2wNEk4M_QhxYJhdlEpZsTSv/view) | 1024x1024 |

---

## Section-by-Section Implementation

### 1. FAVICON & APP ICON

**Asset:** `app-icon.png`

**Instructions:**
- Use as favicon (resize to 32x32, 16x16)
- Use as Apple Touch Icon (180x180)
- Use in navigation bar next to "Notta" wordmark (24x24 or 32x32)

```html
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
```

---

### 2. NAVIGATION BAR

**Changes:**
- Background: Transparent (over hero) or `#FFF9F0`
- Logo: Add `app-icon.png` (32px) next to "Notta" text
- Text color: `#2C3E50`
- CTA button ("Download"): Orange gradient

**Layout:**
```
[Chimp Icon] Notta          Features  Pricing  FAQ  [Download Button]
```

---

### 3. HERO SECTION

**Asset:** `chaos-chimp.png` OR `zen-chimp.png`

**Background:** Warm gradient
```css
background: linear-gradient(180deg, #FFD54F 0%, #F5A623 100%);
```

**Layout (2 columns):**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   [LEFT COLUMN - 50%]           [RIGHT COLUMN - 50%]       │
│                                                             │
│   • "Now available for macOS"    ┌─────────────────────┐   │
│     (small badge)                │                     │   │
│                                  │   chaos-chimp.png   │   │
│   Voice Notes,                   │        OR           │   │
│   Instantly                      │   zen-chimp.png     │   │
│   (large headline)               │                     │   │
│                                  │   (max-width: 500px)│   │
│   Professional voice-to-text... │                     │   │
│   (subtext)                      └─────────────────────┘   │
│                                                             │
│   [Download for Mac]  [See How It Works]                   │
│   (primary CTA)       (secondary CTA)                      │
│                                                             │
│   Free 7-day trial...                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Image placement:**
- Position: Right side of hero
- Size: Max-width 500px, maintain aspect ratio
- Alignment: Vertically centered with text content

**Option A:** Use `chaos-chimp.png` (frustrated typing) to show the problem
**Option B:** Use `zen-chimp.png` (calm speaking) to show the solution

**Recommendation:** Use `zen-chimp.png` - shows the positive outcome

---

### 4. PAIN POINT QUOTE SECTION

**Current:** Dark quote block
**New:** Light card with warm styling

**Changes:**
```css
background: #FFF9F0;
border-radius: 16px;
padding: 40px;
box-shadow: 0 4px 20px rgba(245, 166, 35, 0.1);
```

**Optional:** Add small frustrated chimp icon (crop from `chaos-chimp.png`) next to quote

---

### 5. FEATURES SECTION ("Everything you need...")

**Background:** White or `#FFFFFF`

**Changes:**
- Section background: Light
- Feature cards: White with soft shadow
- Icons: Replace blue icons with orange/warm colored icons

**Layout remains 2x2 grid:**
```
┌─────────────────────┐  ┌─────────────────────┐
│  🎤 Hold-to-Speak   │  │  🔒 Private by      │
│                     │  │     Design          │
│  Description...     │  │  Description...     │
└─────────────────────┘  └─────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐
│  🌐 Works           │  │  📊 Voice Health    │
│     Everywhere      │  │     Insights        │
│  Description...     │  │  Description...     │
└─────────────────────┘  └─────────────────────┘
```

**Icon style:**
- Color: `#F5A623` (orange) or `#2C3E50` (navy)
- Style: Rounded, friendly (not sharp/technical)
- Consider: Custom 3D icons matching mascot style (future enhancement)

---

### 6. HOW IT WORKS SECTION ("Three steps. That's it.")

**Assets:**
- `step1-hold.png`
- `step2-speak.png`
- `step3-release.png`

**Background:** Light cream `#FFF9F0` or subtle gradient

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│              Three steps. That's it.                        │
│         No setup wizards. No configuration headaches.       │
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │             │   │             │   │             │       │
│  │   step1-    │   │   step2-    │   │   step3-    │       │
│  │   hold.png  │   │   speak.png │   │  release.png│       │
│  │             │   │             │   │             │       │
│  │ (300x300)   │   │ (300x300)   │   │ (300x300)   │       │
│  │             │   │             │   │             │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
│                                                             │
│       1. Hold            2. Speak          3. Release       │
│                                                             │
│   Press and hold     Talk naturally—    Text appears at    │
│   your hotkey        medical terms,     your cursor.       │
│   (Option by         names, numbers,    Done.              │
│   default)           whatever                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Image specifications:**
- Size: 300x300px (or responsive, max 300px)
- Spacing: Equal gaps between images
- Border-radius: 16px (optional, for softer look)
- Shadow: `box-shadow: 0 4px 20px rgba(0,0,0,0.08)`

**Note:** The step images already contain "STEP 1: HOLD", "STEP 2: SPEAK", "STEP 3: RELEASE" text. You can either:
- Use images as-is (text included)
- Crop/mask the text and add your own typography below

---

### 7. PRICING SECTION

**Background:** Light `#FFF9F0`

**Changes:**
- Card backgrounds: White
- "Most Popular" badge: Orange `#F5A623`
- CTA buttons: Orange gradient
- Card shadows: Warm tint

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                 Simple, honest pricing                      │
│            Start free. Upgrade when you're ready.           │
│                                                             │
│     ┌─────────────────┐     ┌─────────────────┐            │
│     │   Free Trial    │     │   [Most Popular]│            │
│     │                 │     │                 │            │
│     │   7 days, all   │     │   Notta Pro     │            │
│     │   features      │     │                 │            │
│     │                 │     │   $7.99/month   │            │
│     │      $0         │     │                 │            │
│     │                 │     │   • Everything  │            │
│     │   • Unlimited   │     │   • Priority    │            │
│     │   • Voice health│     │   • Early access│            │
│     │   • Auto-paste  │     │   • Cancel      │            │
│     │   • No card     │     │     anytime     │            │
│     │                 │     │                 │            │
│     │ [Start Trial]   │     │ [Get Notta Pro] │            │
│     │ (outline btn)   │     │ (filled btn)    │            │
│     │                 │     │                 │            │
│     └─────────────────┘     └─────────────────┘            │
│                                                             │
│           Or save 25% with annual: $59.99/year             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Button styles:**
```css
/* Primary CTA (filled) */
.btn-primary {
  background: linear-gradient(135deg, #FFD54F, #F5A623);
  color: #2C3E50;
  border: none;
  padding: 14px 28px;
  border-radius: 12px;
  font-weight: 600;
}

/* Secondary CTA (outline) */
.btn-secondary {
  background: transparent;
  color: #F5A623;
  border: 2px solid #F5A623;
  padding: 12px 26px;
  border-radius: 12px;
}
```

---

### 8. FAQ SECTION

**Background:** White

**Changes:**
- Accordion style: Rounded corners, soft shadows
- Expand/collapse icons: Orange or navy
- Text: Navy `#2C3E50`

**Styling:**
```css
.faq-item {
  background: #FFFFFF;
  border-radius: 12px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.faq-question {
  color: #2C3E50;
  font-weight: 600;
}

.faq-answer {
  color: #7F8C8D;
}
```

---

### 9. FINAL CTA SECTION ("Ready to stop typing?")

**Asset:** `celebrating-chimp.png`

**Background:** Warm gradient (callback to hero)
```css
background: linear-gradient(180deg, #F5A623 0%, #FFD54F 100%);
```

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                     (warm gradient background)              │
│                                                             │
│              Ready to stop typing?                          │
│                        OR                                   │
│          Ready to stop monkeying around?                    │
│                                                             │
│       Download Notta and start your free 7-day trial.      │
│                                                             │
│  ┌─────────────────┐              ┌─────────────────────┐  │
│  │                 │              │                     │  │
│  │  celebrating-   │              │  [Download for Mac] │  │
│  │  chimp.png      │              │   (white button)    │  │
│  │                 │              │                     │  │
│  │  (max 250px)    │              │  Version 1.0 •      │  │
│  │                 │              │  macOS 13+ •        │  │
│  └─────────────────┘              │  Intel & Silicon    │  │
│                                   └─────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Image placement:**
- Position: Left side, or centered above CTA
- Size: Max 250px width
- The confetti in the image adds to the celebratory feel

**Alternative headline:** "Ready to stop monkeying around?" (ties back to campaign)

---

### 10. FOOTER

**Background:** `#FFF9F0` (cream) or `#FFFFFF`

**Changes:**
- Text color: `#2C3E50` or `#7F8C8D`
- Links: `#F5A623` on hover
- Optional: Add small mascot waving in corner

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [Chimp Icon] Notta        Support  Privacy  Terms          │
│                                                             │
│                    © 2026 Indie Studio                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Typography

**Font:** Inter (Google Fonts) or system font stack

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```

**Import:**
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

**Sizes:**
- Hero headline: 48-56px, bold (700)
- Section headlines: 32-36px, bold (700)
- Subheadings: 20-24px, semi-bold (600)
- Body text: 16-18px, regular (400)
- Small text: 14px, medium (500)

---

## Shadows

Use warm-tinted shadows throughout:

```css
/* Card shadow */
box-shadow: 0 4px 20px rgba(245, 166, 35, 0.1);

/* Button shadow */
box-shadow: 0 4px 15px rgba(245, 166, 35, 0.25);

/* Subtle shadow */
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
```

---

## Border Radius

Keep it soft and friendly:

- Buttons: `12px`
- Cards: `16px`
- Large sections: `24px`
- Input fields: `8px`
- Images: `16px` (optional)

---

## Checklist

### Phase 1: Colors & Typography
- [ ] Update background colors (dark → light)
- [ ] Update text colors (white → navy)
- [ ] Update accent colors (blue → orange)
- [ ] Update button styles
- [ ] Add Inter font

### Phase 2: Images
- [ ] Add favicon & apple touch icon (`app-icon.png`)
- [ ] Add mascot to navigation
- [ ] Add hero image (`zen-chimp.png`)
- [ ] Add step images to How It Works section
- [ ] Add celebrating chimp to CTA section

### Phase 3: Polish
- [ ] Update shadows to warm tint
- [ ] Update border radius
- [ ] Add hover states
- [ ] Test on mobile
- [ ] Test dark mode (if applicable)

---

## Questions?

Contact Tyron or review the Brand Style Guide in the same Drive folder.
