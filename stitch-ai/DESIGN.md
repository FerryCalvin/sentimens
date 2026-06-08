---
name: Structured Silence
colors:
  surface: '#07122a'
  surface-dim: '#07122a'
  surface-bright: '#2f3952'
  surface-container-lowest: '#030d25'
  surface-container-low: '#101b33'
  surface-container: '#151f37'
  surface-container-high: '#1f2942'
  surface-container-highest: '#2a344e'
  on-surface: '#d9e2ff'
  on-surface-variant: '#c5c6cd'
  inverse-surface: '#d9e2ff'
  inverse-on-surface: '#263049'
  outline: '#8f9097'
  outline-variant: '#44474d'
  surface-tint: '#b9c7e4'
  primary: '#d6e3ff'
  on-primary: '#233147'
  primary-container: '#b9c7e4'
  on-primary-container: '#45536b'
  inverse-primary: '#515f78'
  secondary: '#c7c6c4'
  on-secondary: '#2f312f'
  secondary-container: '#464745'
  on-secondary-container: '#b5b5b2'
  tertiary: '#d7e2ff'
  on-tertiary: '#20304f'
  tertiary-container: '#b6c6ed'
  on-tertiary-container: '#425273'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#b9c7e4'
  on-primary-fixed: '#0d1c31'
  on-primary-fixed-variant: '#3a475f'
  secondary-fixed: '#e3e2e0'
  secondary-fixed-dim: '#c7c6c4'
  on-secondary-fixed: '#1a1c1a'
  on-secondary-fixed-variant: '#464745'
  tertiary-fixed: '#d8e2ff'
  tertiary-fixed-dim: '#b6c6ed'
  on-tertiary-fixed: '#091b39'
  on-tertiary-fixed-variant: '#374767'
  background: '#07122a'
  on-background: '#d9e2ff'
  surface-variant: '#2a344e'
  outline-opaque: rgba(217, 226, 255, 0.1)
  terminal-placeholder: rgba(197, 198, 205, 0.5)
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.02em
  body-base:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0em
  mono-code:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0em
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.1em
spacing:
  base: 8px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
  container-max: 1200px
  section-gap: 128px
---

## Brand & Style

The brand identity, "Structured Silence," is defined by a fusion of **Technical Brutalism** and **Atmospheric Minimalism**. It targets developers, data architects, and high-stakes system operators who require technical precision without cognitive overload.

The visual style is characterized by "Digital Quietude"—an environment that feels both expansive and highly controlled. Key aesthetic pillars include:
- **Hairline Precision:** Extensive use of 1px borders and razor-sharp corners to evoke a sense of engineering rigor.
- **Kinetic Geometry:** Subtle, slow-moving linear background animations that suggest a living system beneath the surface.
- **Glassmorphism Lite:** Minimal use of backdrop blurs (blur-xl) on surfaces to maintain depth without sacrificing the "flat" architectural feel.
- **Editorial Data:** Large, bold typography usually reserved for fashion or news, applied to technical telemetry to create an "Editorial Dashboard" experience.

## Colors

The palette is a "Deep Space" monochromatic blue-grey base, accented by high-fidelity desaturated cool tones. 

- **Primary & Tertiary:** These are "Electronic Blues" (#b9c7e4, #b6c6ed), used for progress indicators, status labels, and active navigation states.
- **Surface Strategy:** The UI uses a "Dark-on-Dark" approach. The base background is a deep navy (`#07122a`), with containers defined by subtle borders rather than significant value shifts.
- **Contrast:** High-contrast white (`#faf9f6`) is reserved strictly for primary calls-to-action and major headlines, ensuring they "cut through" the atmospheric background.
- **Functional Accents:** Status colors (like error reds) should be desaturated and lean towards pastel to maintain the "Silence" of the brand.

## Typography

The system uses a dual-font strategy:
1. **Plus Jakarta Sans** for the "Human" layer: Display titles, headlines, and body copy. It provides a soft, approachable counter-balance to the rigid grid.
2. **Geist** for the "Machine" layer: All labels, metadata, and data inputs. This monospaced/technical-leaning font reinforces the system's precision.

**Style Rules:**
- **Titling:** Major titles should use tight letter-spacing and "Structured" phrasing (e.g., periods at the end of display phrases).
- **Labels:** Always uppercase with tracked-out letter spacing (0.1em) to distinguish them from body text.
- **Data:** Numerical values should prioritize the primary color to draw focus within a layout.

## Layout & Spacing

The layout is a **12-column Fixed Grid** with an emphasis on vertical rhythm and vast "air" between sections.

- **The Grid:** Desktop uses a 1200px max-width container. 24px gutters provide a standard breathing room for content cards.
- **Margins:** Generous 48px side margins on desktop create an "island" effect, making the data feel curated.
- **Sectioning:** Large vertical gaps (128px / `gap-32`) are used to separate logical blocks (Hero vs. Progress vs. Dashboard), preventing the screen from feeling cluttered despite the dark theme.
- **Mobile Reflow:** On mobile, the 12-column grid collapses to a single column, and display font sizes scale down significantly (48px -> 32px) to maintain readability.

## Elevation & Depth

This system rejects traditional shadows in favor of **Tonal Layering and Glassmorphism**.

- **Level 0 (Background):** Solid `surface-dim` with geometric line animations.
- **Level 1 (Navigation/Cards):** Semi-transparent `surface/70` with `backdrop-blur-xl`. Depth is communicated via a 1px border of `on-surface/10` rather than a shadow.
- **Interactive Depth:** When an element is focused (like an input), a very subtle "Glow" shadow is used (`0 0 15px rgba(185, 199, 228, 0.1)`) instead of an offset shadow, suggesting light emission from the screen.
- **Active State:** Elements do not "lift" (move up); they react with subtle scaling (`active:scale-95`) to feel tactile yet grounded.

## Shapes

The shape language is **Strictly Geometric**.

- **Corners:** Everything uses 0px roundedness (Sharp). This includes cards, buttons, inputs, and progress bars.
- **Exceptions:** Icons (Material Symbols) and purely decorative profile buttons may use full rounding (Pill-shaped) to serve as soft points of interest in an otherwise rigid environment.
- **Visual Weight:** Heavy use of horizontal and vertical rules (1px lines) to box in content, creating a "blueprint" aesthetic.

## Components

### Buttons
- **Primary:** High-contrast white background, sharp corners, black Geist caps text. Hover state reduces opacity slightly (90%).
- **Icon Buttons:** Circular background on hover (`on-surface/5`), no border, thin icon weight (300).

### Input Fields
- **Glass Input:** `surface-bright/5` background, backdrop blur, 1px border. Uses Geist Mono for input text to signify technical entry. Placeholder text is highly de-emphasized.

### Cards
- **Dashboard Card:** Sharp corners, 1px border, no shadow. Structure: Icon (top left) + Label (top right) + Value (bottom).
- **Visual Card:** Overlays a desaturated image with a gradient fade to `surface-dim` to ensure legibility of bottom-aligned text.

### Progress Indicators
- **Hairline Progress:** A 2px high track. The fill uses the Primary color. Animation should be a smooth cubic-bezier to feel sophisticated rather than mechanical.

### Navigation
- **Top Bar:** Fixed, blurred, with a hairline bottom border. Active links use a 2px bottom border in the Primary color rather than a background change.