# Theme System

Zoea Studio uses a shadcn.io-based theme system with OKLCH color space for perceptually uniform colors across 11 themes.

## Overview

The theme system provides:

- **11 color themes**: Each with distinct primary colors and personalities
- **Light/Dark mode**: Toggle via `.dark` class on `<html>`
- **OKLCH color space**: Perceptually uniform colors that look consistent
- **Semantic tokens**: Consistent naming across all themes
- **Tailwind integration**: All tokens available as Tailwind utilities

## Quick Reference

### Applying Themes

```jsx
// In components, use Tailwind classes with semantic token names
<div className="bg-background text-foreground">
  <button className="bg-primary text-primary-foreground">
    Click me
  </button>
</div>

// For sidebar/navigation areas
<nav className="bg-sidebar text-sidebar-foreground">
  <button className="bg-sidebar-primary text-sidebar-primary-foreground">
    Active
  </button>
</nav>
```

### Theme Store

```javascript
import { useThemeStore, THEMES, MODES } from '../stores/themeStore';

function ThemeSelector() {
  const { theme, mode, setTheme, setMode } = useThemeStore();

  return (
    <>
      <select value={theme} onChange={(e) => setTheme(e.target.value)}>
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>

      <select value={mode} onChange={(e) => setMode(e.target.value)}>
        {MODES.map((m) => (
          <option key={m.id} value={m.id}>{m.name}</option>
        ))}
      </select>
    </>
  );
}
```

## Available Themes

| Theme ID | Name | Primary Color | Description |
|----------|------|---------------|-------------|
| `amber-minimal` | Amber Minimal | Warm amber | Minimal design with warm tones |
| `claude` | Claude | Orange | Anthropic-inspired (default) |
| `corporate` | Corporate | Blue | Professional enterprise look |
| `modern-minimal` | Modern | Purple | Clean contemporary design |
| `nature` | Nature | Green | Earthy, organic feel |
| `slack` | Slack | Purple | Familiar collaboration theme |
| `twitter` | Twitter | Sky blue | Social media inspired |
| `cyberpunk` | Cyberpunk | Pink/Neon | Bold neon vibes |
| `red` | Red | Crimson | Bold accent color |
| `summer` | Summer | Orange | Bright and warm |
| `notebook` | Notebook | Blue | Paper-like, scholarly |

## CSS Custom Properties

All themes define the following CSS custom properties. Use these directly in CSS or via Tailwind utilities.

### Core Colors

| CSS Variable | Tailwind Class | Usage |
|-------------|----------------|-------|
| `--background` | `bg-background` | Page/app background |
| `--foreground` | `text-foreground` | Primary text color |
| `--card` | `bg-card` | Card/panel backgrounds |
| `--card-foreground` | `text-card-foreground` | Text on cards |
| `--popover` | `bg-popover` | Popover/dropdown backgrounds |
| `--popover-foreground` | `text-popover-foreground` | Text in popovers |

### Interactive Colors

| CSS Variable | Tailwind Class | Usage |
|-------------|----------------|-------|
| `--primary` | `bg-primary` | Primary actions, CTAs |
| `--primary-foreground` | `text-primary-foreground` | Text on primary buttons |
| `--secondary` | `bg-secondary` | Secondary actions |
| `--secondary-foreground` | `text-secondary-foreground` | Text on secondary elements |
| `--accent` | `bg-accent` | Hover states, highlights |
| `--accent-foreground` | `text-accent-foreground` | Text on accented areas |
| `--destructive` | `bg-destructive` | Delete, error states |
| `--destructive-foreground` | `text-destructive-foreground` | Text on destructive buttons |

### Muted/Subtle Colors

| CSS Variable | Tailwind Class | Usage |
|-------------|----------------|-------|
| `--muted` | `bg-muted` | Subtle backgrounds |
| `--muted-foreground` | `text-muted-foreground` | Secondary/helper text |

### Structural Colors

| CSS Variable | Tailwind Class | Usage |
|-------------|----------------|-------|
| `--border` | `border-border` | Borders, dividers |
| `--input` | `border-input` | Input field borders |
| `--ring` | `ring-ring` | Focus rings |

### Sidebar Colors

Dedicated color zone for navigation sidebars and app shell:

| CSS Variable | Tailwind Class | Usage |
|-------------|----------------|-------|
| `--sidebar` | `bg-sidebar` | Sidebar background |
| `--sidebar-foreground` | `text-sidebar-foreground` | Sidebar text |
| `--sidebar-primary` | `bg-sidebar-primary` | Active nav item background |
| `--sidebar-primary-foreground` | `text-sidebar-primary-foreground` | Active nav item text |
| `--sidebar-accent` | `bg-sidebar-accent` | Hover state for nav items |
| `--sidebar-accent-foreground` | `text-sidebar-accent-foreground` | Text on hover |
| `--sidebar-border` | `border-sidebar-border` | Sidebar borders |
| `--sidebar-ring` | `ring-sidebar-ring` | Focus rings in sidebar |

### Chart Colors

For data visualization:

| CSS Variable | Usage |
|-------------|-------|
| `--chart-1` | Primary chart color |
| `--chart-2` | Secondary chart color |
| `--chart-3` | Tertiary chart color |
| `--chart-4` | Fourth chart color |
| `--chart-5` | Fifth chart color |

### Typography & Spacing

| CSS Variable | Usage |
|-------------|-------|
| `--font-sans` | Sans-serif font stack |
| `--font-serif` | Serif font stack |
| `--font-mono` | Monospace font stack |
| `--radius` | Default border radius |
| `--spacing` | Base spacing unit |

### Shadows

| CSS Variable | Tailwind Class | Size |
|-------------|----------------|------|
| `--shadow-2xs` | `shadow-2xs` | Extra extra small |
| `--shadow-xs` | `shadow-xs` | Extra small |
| `--shadow-sm` | `shadow-sm` | Small |
| `--shadow` | `shadow` | Default |
| `--shadow-md` | `shadow-md` | Medium |
| `--shadow-lg` | `shadow-lg` | Large |
| `--shadow-xl` | `shadow-xl` | Extra large |
| `--shadow-2xl` | `shadow-2xl` | Extra extra large |

## Usage Patterns

### Component Zone Mapping

Use the right color zone for each part of the layout:

```
+---------------------------------------------------+
|  AppHeader (bg-sidebar, text-sidebar-foreground)  |
+----------+----------------------------------------+
| Projects |  NavigationBar (bg-sidebar)            |
|   Bar    +----------------------------------------+
|          |                                        |
| (sidebar)|  ViewContainer (bg-background)         |
|  tokens  |  - Cards use bg-card                   |
|          |  - Text uses text-foreground           |
|          |  - Actions use bg-primary              |
+----------+----------------------------------------+
```

### App Shell Components

```jsx
// AppHeader, NavigationBar, ProjectsBar, Sidebar
<aside className="bg-sidebar border-r border-sidebar-border">
  <button className="text-sidebar-foreground hover:bg-sidebar-accent">
    Item
  </button>
  <button className="bg-sidebar-primary text-sidebar-primary-foreground">
    Active Item
  </button>
</aside>
```

### Content Area Components

```jsx
// Cards, forms, main content
<div className="bg-background text-foreground">
  <div className="bg-card border border-border rounded-lg p-4">
    <h2 className="text-foreground">Title</h2>
    <p className="text-muted-foreground">Description</p>
    <button className="bg-primary text-primary-foreground">
      Action
    </button>
  </div>
</div>
```

### Inline Styles

When Tailwind isn't available, use CSS variables directly:

```jsx
<div style={{ backgroundColor: 'var(--card)', color: 'var(--card-foreground)' }}>
  Content
</div>

<button style={{ backgroundColor: 'var(--primary)', color: 'var(--primary-foreground)' }}>
  Action
</button>
```

## Dark Mode

### How It Works

Dark mode is controlled by the `.dark` class on `<html>`:

```javascript
// themeStore.js handles this automatically
if (mode === 'dark') {
  document.documentElement.classList.add('dark');
} else {
  document.documentElement.classList.remove('dark');
}
```

### System Preference

The `auto` mode respects the user's system preference:

```javascript
const getPreferredMode = () => {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};
```

### Tailwind Configuration

```javascript
// tailwind.config.js
export default {
  darkMode: 'class', // Uses .dark class
  // ...
}
```

## Theme Switching

### Color Theme

Set via `data-theme` attribute on `<html>`:

```javascript
document.documentElement.setAttribute('data-theme', 'nature');
```

### Combining Theme and Mode

Both attributes work together:

```html
<!-- Light mode, Corporate theme -->
<html data-theme="corporate">

<!-- Dark mode, Corporate theme -->
<html data-theme="corporate" class="dark">

<!-- Light mode, Cyberpunk theme -->
<html data-theme="cyberpunk">

<!-- Dark mode, Cyberpunk theme -->
<html data-theme="cyberpunk" class="dark">
```

## File Locations

| File | Purpose |
|------|---------|
| `frontend/src/styles/shadcn-themes.css` | Theme CSS definitions (38KB) |
| `frontend/src/stores/themeStore.js` | Theme state management |
| `frontend/src/components/ThemeSelector.jsx` | Theme picker UI |
| `frontend/tailwind.config.js` | Tailwind token mappings |
| `frontend/src/index.css` | Imports and sidebar utilities |

## Adding Custom Themes

To add a new theme:

1. **Add CSS definitions** in `shadcn-themes.css`:

```css
[data-theme="my-theme"] {
  --background: oklch(0.98 0.01 95);
  --foreground: oklch(0.34 0.03 95);
  --primary: oklch(0.65 0.15 240);
  /* ... all other tokens */
}

[data-theme="my-theme"].dark {
  --background: oklch(0.20 0.01 95);
  --foreground: oklch(0.90 0.01 95);
  /* ... dark variants */
}
```

2. **Register in theme store**:

```javascript
// themeStore.js
export const THEMES = [
  // ... existing themes
  { id: 'my-theme', name: 'My Theme', description: 'Custom theme' },
];
```

3. **Add color swatch** (optional) in `ThemeSelector.jsx`:

```javascript
const THEME_COLORS = {
  // ... existing colors
  'my-theme': '#3b82f6',
};
```

## Migration from Legacy System

The codebase was migrated from a legacy theme system. Old theme IDs are automatically mapped:

| Old Theme | New Theme |
|-----------|-----------|
| `slate` | `corporate` |
| `aubergine` | `slack` |
| `ocean` | `twitter` |
| `forest` | `nature` |
| `copper` | `amber-minimal` |
| `midnight` | `cyberpunk` |
| `sunrise` | `summer` |

This mapping happens automatically when localStorage is rehydrated.

## Troubleshooting

### Colors Not Applying

1. Check that `shadcn-themes.css` is imported in `index.css`
2. Verify `data-theme` attribute is set on `<html>`
3. For dark mode, check that `.dark` class is present

### Sidebar Classes Not Working

Sidebar utilities are defined in `index.css`:

```css
@layer utilities {
  .bg-sidebar { background-color: var(--sidebar); }
  .text-sidebar-foreground { color: var(--sidebar-foreground); }
  /* ... etc */
}
```

### Theme Not Persisting

Check browser localStorage for `zoea-theme` key. The store persists `theme` and `mode` values.

## Related Documentation

- [Frontend Architecture](../architecture/frontend.md) - Layout system and components
- [Tailwind Configuration](../reference/configuration.md) - Build configuration
