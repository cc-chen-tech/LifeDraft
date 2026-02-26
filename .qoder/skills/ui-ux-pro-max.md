# UI/UX Pro Max - Design Intelligence

> Source: [nextlevelbuilder/ui-ux-pro-max-skill](https://skills.sh/nextlevelbuilder/ui-ux-pro-max-skill/ui-ux-pro-max) (20K+ installs)

Comprehensive design guide for web and mobile applications. Contains 50+ styles, 97 color palettes, 57 font pairings, 99 UX guidelines, and 25 chart types. Searchable database with priority-based recommendations.

## When to Apply

Reference these guidelines when:

- Designing new UI components or pages
- Choosing color palettes and typography
- Reviewing code for UX issues
- Building landing pages or dashboards
- Implementing accessibility requirements

## Rule Categories by Priority

| Priority | Category | Impact | Domain |
| --- | --- | --- | --- |
| 1 | Accessibility | CRITICAL | ux |
| 2 | Touch & Interaction | CRITICAL | ux |
| 3 | Performance | HIGH | ux |
| 4 | Layout & Responsive | HIGH | ux |
| 5 | Typography & Color | MEDIUM | typography, color |
| 6 | Animation | MEDIUM | ux |
| 7 | Style Selection | MEDIUM | style, product |
| 8 | Charts & Data | LOW | chart |

## 1. Accessibility (CRITICAL)

- **color-contrast** - Minimum 4.5:1 ratio for normal text
- **focus-states** - Visible focus rings on interactive elements
- **alt-text** - Descriptive alt text for meaningful images
- **aria-labels** - aria-label for icon-only buttons
- **keyboard-nav** - Tab order matches visual order
- **form-labels** - Use label with for attribute

## 2. Touch & Interaction (CRITICAL)

- **touch-target-size** - Minimum 44x44px touch targets
- **hover-vs-tap** - Use click/tap for primary interactions
- **loading-buttons** - Disable button during async operations
- **error-feedback** - Clear error messages near problem
- **cursor-pointer** - Add cursor-pointer to clickable elements

## 3. Performance (HIGH)

- **image-optimization** - Use WebP, srcset, lazy loading
- **reduced-motion** - Check prefers-reduced-motion
- **content-jumping** - Reserve space for async content

## 4. Layout & Responsive (HIGH)

- **viewport-meta** - width=device-width initial-scale=1
- **readable-font-size** - Minimum 16px body text on mobile
- **horizontal-scroll** - Ensure content fits viewport width
- **z-index-management** - Define z-index scale (10, 20, 30, 50)

## 5. Typography & Color (MEDIUM)

- **line-height** - Use 1.5-1.75 for body text
- **line-length** - Limit to 65-75 characters per line
- **font-pairing** - Match heading/body font personalities

## 6. Animation (MEDIUM)

- **duration-timing** - Use 150-300ms for micro-interactions
- **transform-performance** - Use transform/opacity, not width/height
- **loading-states** - Skeleton screens or spinners

## 7. Style Selection (MEDIUM)

- **style-match** - Match style to product type
- **consistency** - Use same style across all pages
- **no-emoji-icons** - Use SVG icons, not emojis

## 8. Charts & Data (LOW)

- **chart-type** - Match chart type to data type
- **color-guidance** - Use accessible color palettes
- **data-table** - Provide table alternative for accessibility

---

## Style Recommendations by Product Type

### Games / Interactive Storytelling
- **Recommended Styles**: Narrative UI, Immersive Dark, Cinematic
- **Color Palette**: Deep darks with accent highlights, atmospheric gradients
- **Typography**: Serif for narrative text (literary feel), Sans-serif for UI elements
- **Key Principles**:
  - Minimize chrome, maximize content area
  - Use animation sparingly but impactfully (story reveals, transitions)
  - Dark themes reduce eye strain for long sessions
  - Progressive disclosure: show options only when relevant

### SaaS / Dashboard
- **Recommended Styles**: Clean Minimal, Corporate Professional
- **Color Palette**: Neutral base with 1-2 accent colors
- **Typography**: System fonts or clean sans-serif

### E-commerce
- **Recommended Styles**: Modern Retail, Lifestyle
- **Color Palette**: Brand-heavy with CTA contrast
- **Typography**: Clean, readable, brand-aligned

---

## UX Best Practices Quick Reference

### Loading States
- Use skeleton screens instead of spinners when layout is known
- Show progress indicators for operations > 2 seconds
- Disable trigger button during async operation
- Provide cancel option for long operations

### Error Handling
- Show errors inline near the cause
- Use clear, actionable error messages
- Offer recovery actions (retry, alternative)
- Don't clear user input on error

### Empty States
- Never show blank pages
- Provide helpful guidance or call-to-action
- Use illustrations to make empty states welcoming

### Navigation
- Current location always visible
- Breadcrumbs for deep hierarchies
- Back button behavior matches expectation
- Preserve scroll position on return

### Forms
- Group related fields
- Mark optional fields (not required)
- Real-time validation where possible
- Smart defaults reduce effort

### Mobile
- Bottom-aligned primary actions (thumb zone)
- Swipe gestures for common actions
- Pull-to-refresh for list updates
- Respect safe areas (notch, home indicator)

---

## Animation Timing Reference

| Type | Duration | Easing |
| --- | --- | --- |
| Button hover | 150ms | ease-out |
| Tooltip appear | 200ms | ease-out |
| Modal open | 250ms | ease-out |
| Modal close | 200ms | ease-in |
| Page transition | 300ms | ease-in-out |
| Skeleton shimmer | 1.5s | linear (loop) |
| Toast appear | 300ms | ease-out |
| Toast dismiss | 200ms | ease-in |

## Z-Index Scale

| Layer | Z-Index | Use |
| --- | --- | --- |
| Base | 0 | Default content |
| Dropdown | 10 | Menus, tooltips |
| Sticky | 20 | Headers, sidebars |
| Modal backdrop | 30 | Overlay backgrounds |
| Modal | 40 | Dialog content |
| Toast | 50 | Notifications |
