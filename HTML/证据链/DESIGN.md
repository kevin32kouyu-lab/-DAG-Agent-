---
name: Cognitive Workspace
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#444651'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#757682'
  outline-variant: '#c5c5d3'
  surface-tint: '#4059aa'
  primary: '#00236f'
  on-primary: '#ffffff'
  primary-container: '#1e3a8a'
  on-primary-container: '#90a8ff'
  inverse-primary: '#b6c4ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#222a3e'
  on-tertiary: '#ffffff'
  tertiary-container: '#384055'
  on-tertiary-container: '#a4acc5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b6c4ff'
  on-primary-fixed: '#00164e'
  on-primary-fixed-variant: '#264191'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#dae2fd'
  tertiary-fixed-dim: '#bec6e0'
  on-tertiary-fixed: '#131b2e'
  on-tertiary-fixed-variant: '#3f465c'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  confidence-high: '#059669'
  confidence-medium: '#D97706'
  confidence-low: '#DC2626'
  border-subtle: '#E2E8F0'
  agent-active: '#3B82F6'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  margin-page: 32px
  gutter: 24px
  container-max-width: 1280px
  report-reading-width: 800px
---

## Brand & Style

The design system is centered on the concept of **Cognitive Workspace**. It moves away from the flashy, high-velocity aesthetics of consumer AI and instead leans into the steady, methodical nature of high-end market research and intelligence gathering. The primary goal is to foster "Analytical Trust"—a psychological state where the user feels the data is scrutinized, verified, and objective.

The design style is **Corporate / Modern** with a strong influence from **Minimalism**. 
- **Credibility over Decoration:** Every visual element must serve a functional purpose. There are no decorative gradients or floating shapes.
- **Data-Focused:** Information density is high but organized via a strict grid to ensure "scannability."
- **Institutional Weight:** The UI uses subtle borders and structural alignment to feel like a stable, professional tool rather than a lightweight utility.
- **Narrative Flow:** The style supports a linear, four-stage progression, ensuring the transition from raw data (Sources) to final insights (Report) feels logical and inevitable.

## Colors

The palette is anchored by **Deep Intelligence Blue** (#1E3A8A), chosen for its association with academic research and institutional reliability. 

- **Primary:** Used for the main navigation, primary actions, and key branding elements. It is never used for backgrounds to maintain its impact.
- **Secondary:** A Slate Gray used for metadata, secondary text, and less prominent UI controls, ensuring a calm visual hierarchy.
- **Tertiary:** A near-black for high-contrast typography, providing maximum legibility for long-form report reading.
- **Neutral:** A cool, off-white background (#F8FAFC) that reduces eye strain compared to pure white, mimicking the feel of high-quality paper.
- **Semantic Colors:** Critical for the "Evidence" and "Sources" pages. A specific range of Green, Amber, and Red is used to denote confidence scores and source reliability.

## Typography

The typography strategy prioritizes "Clarity and Lineage." 

- **Headlines (Hanken Grotesk):** A sharp, contemporary grotesque that feels "designed" yet professional. It provides the necessary "Report" character for the final analysis outputs.
- **Body (Inter):** The workhorse for data density. It is highly legible at small sizes, which is essential for the Sources and Evidence tables.
- **Labels & Metadata (JetBrains Mono):** Monospaced type is used exclusively for the **Technical Trace** and **Source Links**. This creates a visual distinction between "Human Conclusion" (Sans) and "System/Source Data" (Mono), reinforcing the traceability of the AI's logic.
- **Hierarchy:** We use generous line heights (1.5x for body text) to ensure that the competitive analysis reports feel like a comfortable reading experience, not a cramped spreadsheet.

## Layout & Spacing

The layout follows a **Fixed Grid** philosophy for the core workspace, ensuring consistency when displaying complex tables and multi-agent workflows.

- **Grid System:** A 12-column grid with a 1280px max-width. For the "Report" page, the primary content is centered and restricted to 800px to optimize line length for readability, with the "Evidence Sidebar" occupying the remaining right-hand columns.
- **Spacing Rhythm:** Based on a 4px base unit. 
    - Use `16px` (4 units) for internal card padding.
    - Use `24px` (6 units) for gaps between layout sections.
    - Use `48px` (12 units) for major vertical section breaks in the final report.
- **Responsive Behavior:** 
    - **Desktop:** Sidebar navigation is persistent.
    - **Tablet:** Sidebar collapses to icons; tables scroll horizontally.
    - **Mobile:** Single column flow; reports transition to a simplified "Executive Summary" view. Large headlines scale down to `headline-lg-mobile`.

## Elevation & Depth

This design system avoids heavy shadows to maintain a flat, "architectural" feel. Depth is communicated through **Tonal Layers** and **Low-contrast Outlines**.

- **Surface Levels:**
    - **Level 0 (Background):** #F8FAFC. The base of the application.
    - **Level 1 (Cards/Sections):** Pure White (#FFFFFF) with a 1px solid border (#E2E8F0).
    - **Level 2 (Active States/Popovers):** Pure White with a soft, 4px blur, 5% opacity black shadow to indicate temporary interaction.
- **Separation:** Instead of shadows, use subtle background shifts (e.g., a Slate-50 header in a table) to define boundaries. This keeps the interface clean and "research-oriented."
- **Agent Trace:** In the Technical Trace view, use nested containers with slightly darker borders to show the hierarchy of the DAG nodes.

## Shapes

The shape language is **Soft** (roundedness: 1). 

- **Primary UI Elements:** Buttons, input fields, and tags use a `4px` (0.25rem) radius. This provides just enough softness to feel modern without losing the "professional edge" required for a research tool.
- **Containers:** Cards and report sections use `8px` (0.5rem) to create a clear structural distinction.
- **System Indicators:** Progress bars and agent status dots use "Pill" shapes (full rounding) to denote dynamic, living elements within the static report framework.

## Components

- **Buttons:** 
    - *Primary:* Solid Deep Blue (#1E3A8A) with white text. Square-ish (4px radius).
    - *Secondary:* Ghost style with 1px Slate border. Used for "Add Competitor" or "Export PDF."
- **Confidence Chips:** Small badges using `label-sm` font. Colors: #059669 (High), #D97706 (Medium), #DC2626 (Low). They should have a subtle background tint of the same hue at 10% opacity.
- **Data Tables (Sources/Technical Trace):** 
    - Header: Slate-50 background, uppercase `label-sm` text.
    - Rows: 1px bottom border only. Minimal padding to maximize information density.
- **Progress Indicator (The 4-Stage Analysis):** 
    - Use a horizontal "Stepped" progress bar.
    - Active stage: Highlighted in Intelligence Blue with a pulsating "Agent Active" dot.
    - Completed stages: Checkmark icon with a success green color.
- **Executive Summary Cards:** 
    - Placed at the top of the report. Use a light Slate-50 left-border (4px width) to differentiate "Insights" from standard body text.
- **Input Fields:** 
    - Minimalist 1px border. Focus state uses a 1px Blue ring. 
    - Support for "Tags" inside the competitor input field for multi-product analysis.
- **Charts:** 
    - Use a professional, monochromatic blue scale for heatmaps. 
    - Avoid vibrant multi-colors; use shades of Slate for secondary data points in bar charts.