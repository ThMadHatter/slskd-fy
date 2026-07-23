---
name: SoulFinder
colors:
  surface: '#131314'
  surface-dim: '#131314'
  surface-bright: '#3a393a'
  surface-container-lowest: '#0e0e0f'
  surface-container-low: '#1c1b1c'
  surface-container: '#201f20'
  surface-container-high: '#2a2a2b'
  surface-container-highest: '#353436'
  on-surface: '#e5e2e3'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#e5e2e3'
  inverse-on-surface: '#313031'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#c8c6c9'
  on-secondary: '#303033'
  secondary-container: '#47464a'
  on-secondary-container: '#b6b4b8'
  tertiary: '#ffb3af'
  on-tertiary: '#650911'
  tertiary-container: '#fc7c78'
  on-tertiary-container: '#711419'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#e4e1e5'
  secondary-fixed-dim: '#c8c6c9'
  on-secondary-fixed: '#1b1b1e'
  on-secondary-fixed-variant: '#47464a'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3af'
  on-tertiary-fixed: '#410005'
  on-tertiary-fixed-variant: '#842225'
  background: '#131314'
  on-background: '#e5e2e3'
  surface-variant: '#353436'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '500'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: 0.02em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.1em
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  container-max: 1440px
---

## Brand & Style
The design system is engineered to evoke the precision of high-end rack-mounted audio hardware and the meticulous nature of archival database software. It targets the technical audiophile who values clarity, utility, and understated luxury over visual flourish.

The aesthetic follows a **Technical Minimalism** approach. It rejects decorative trends like gradients and blurs in favor of structural integrity, sharp definition, and a rigid information hierarchy. The emotional response should be one of "quiet authority"—a tool that feels both expensive and highly functional, prioritizing the long-term legibility of complex metadata over immediate visual stimulation.

## Colors
The palette is deeply anchored in a dark, monochromatic foundation to minimize eye strain during long listening or cataloging sessions. 

- **Foundation:** The primary surface is a near-black (#0a0a0b), providing a high-contrast base for technical data.
- **Accents:** Emerald Green (#10b981) is used sparingly and exclusively for primary actions, success states, and active audio indicators.
- **Typography:** Headlines utilize an off-white (#f9fafb) to ensure maximum readability without the harshness of pure white. Secondary metadata is suppressed using mid-gray (#9ca3af).
- **Structure:** Borders and dividers use a deep neutral gray (#27272a), creating a "blueprint" feel that organizes the interface without introducing visual noise.

## Typography
This design system utilizes a dual-font strategy to balance modern elegance with technical utility. 

**Hanken Grotesk** serves as the primary typeface for branding, navigation, and large headings. Its clean, contemporary geometry maintains a premium feel. 

**JetBrains Mono** is utilized for all technical data, including file formats, bitrates, timestamps, and database IDs. This monospaced font reinforces the "archival" nature of the tool. Use `label-caps` for table headers and category descriptors to create clear visual separation between functional labels and user content.

## Layout & Spacing
The layout is governed by a strict 4px grid system, ensuring mathematical precision in alignment. 

- **Grid:** A 12-column fluid grid is used for desktop views. Content should be grouped into logical "modules" separated by 1px solid borders.
- **Density:** High information density is encouraged. Use tighter vertical spacing for lists of tracks or technical specs, while maintaining generous 32px margins around the main container to frame the content.
- **Responsive:** On mobile devices, the 12-column grid collapses to a single column. Horizontal padding is reduced to 16px, and all monospaced labels remain at their fixed sizes to preserve legibility.

## Elevation & Depth
This design system rejects shadows and blurs. Depth is communicated through **Tonal Layering** and **Line Work**.

- **Surface 0:** Background (#0a0a0b).
- **Surface 1:** Modules and Cards (#1a1a1c).
- **Borders:** All interactive or distinct areas are defined by a 1px solid border (#27272a). 
- **Active State:** To show elevation or focus, change the border color to the primary emerald green (#10b981) or lighten the surface slightly to #27272a. Do not use drop shadows; the UI should remain perfectly flat, resembling a precision-machined instrument.

## Shapes
In alignment with the "archival hardware" aesthetic, all UI elements utilize **sharp, 0px corners**. 

This includes buttons, input fields, cards, and dropdown menus. The absence of rounded corners emphasizes the technical, no-nonsense nature of the tool. The only exceptions are specific circular iconography (e.g., play/pause controls) which should be rendered with mathematical precision.

## Components
- **Buttons:** Rectangular with 0px radius. Primary buttons use an Emerald Green background with black text. Secondary buttons use a transparent background with a 1px gray border.
- **Data Grids:** Use 1px borders between rows and columns. Header cells use `label-caps` typography. Row hover states should use a subtle background shift to #1a1a1c.
- **Input Fields:** Flat #0a0a0b background with a #27272a border. Focus state is indicated by a 1px Emerald Green border. Text should use the monospaced font for consistency in data entry.
- **Chips/Tags:** Used for genres or file types. Small, rectangular boxes with `data-mono` text. No background fill—only a 1px border.
- **Audio Visualizers:** Rendered as sharp vertical bars or clean waveforms using the primary Emerald Green. No glows or soft edges.
- **Status Indicators:** Small, solid squares (not circles) in Emerald Green for "Online/Live" and Mid-Gray for "Inactive".