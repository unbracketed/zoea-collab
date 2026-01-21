/**
 * Appearance Settings Tab
 *
 * Color theme and header style settings.
 */

import { Check, ToggleLeft, ToggleRight } from 'lucide-react'
import { THEMES } from '../../stores/themeStore'

const THEME_COLORS = {
  'amber-minimal': '#d4a259',
  'claude': '#c75f2a',
  'corporate': '#2563eb',
  'modern-minimal': '#7c3aed',
  'nature': '#059669',
  'slack': '#611f69',
  'twitter': '#1d9bf0',
  'cyberpunk': '#e11d48',
  'red': '#dc2626',
  'summer': '#ea580c',
  'notebook': '#3b82f6',
}

function AppearanceSettingsTab({
  colorTheme,
  setColorTheme,
  usePrimaryHeader,
  setUsePrimaryHeader,
}) {
  return (
    <section className="bg-card rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold mb-6">Appearance</h2>

      {/* Color Theme Section */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Color Theme</label>
        <div className="flex flex-wrap gap-2">
          {THEMES.map((theme) => (
            <button
              key={theme.id}
              type="button"
              onClick={() => setColorTheme(theme.id)}
              className={`relative w-10 h-10 rounded-lg transition-all ${
                colorTheme === theme.id
                  ? 'ring-2 ring-primary ring-offset-2 ring-offset-card'
                  : 'hover:scale-110'
              }`}
              style={{ backgroundColor: THEME_COLORS[theme.id] }}
              title={theme.name}
              aria-label={`${theme.name} theme`}
              aria-pressed={colorTheme === theme.id}
            >
              {colorTheme === theme.id && (
                <Check className="absolute inset-0 m-auto h-5 w-5 text-white" />
              )}
            </button>
          ))}
        </div>
        {colorTheme && (
          <p className="mt-2 text-sm text-muted-foreground">
            {THEMES.find((t) => t.id === colorTheme)?.name}
          </p>
        )}
      </div>

      {/* Primary Header Toggle */}
      <div>
        <label className="block text-sm font-medium mb-2">Header Style</label>
        <button
          type="button"
          onClick={() => setUsePrimaryHeader(!usePrimaryHeader)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-border hover:bg-muted transition-colors"
        >
          <div className="flex flex-col items-start">
            <span className="text-sm">Use primary color header</span>
            <span className="text-xs text-muted-foreground">
              Apply theme color to app header and navigation
            </span>
          </div>
          {usePrimaryHeader ? (
            <ToggleRight className="h-6 w-6 text-primary flex-shrink-0" />
          ) : (
            <ToggleLeft className="h-6 w-6 text-muted-foreground flex-shrink-0" />
          )}
        </button>
      </div>
    </section>
  )
}

export default AppearanceSettingsTab
