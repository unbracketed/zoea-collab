/**
 * General Settings Tab
 *
 * Project name, description, and avatar management.
 */

import { Upload, Trash2 } from 'lucide-react'

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

function GeneralSettingsTab({
  name,
  setName,
  description,
  setDescription,
  colorTheme,
  avatarPreview,
  fileInputRef,
  handleAvatarSelect,
  handleRemoveAvatar,
  hasExistingAvatar,
}) {
  return (
    <section className="bg-card rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold mb-6">General Settings</h2>

      {/* Avatar Section */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Project Avatar</label>
        <div className="flex items-center gap-4">
          {/* Avatar preview */}
          <div className="relative">
            {avatarPreview ? (
              <img
                src={avatarPreview}
                alt="Project avatar"
                className="h-16 w-16 rounded-xl object-cover border border-border"
              />
            ) : (
              <div
                className="h-16 w-16 rounded-xl flex items-center justify-center text-2xl font-bold text-white border border-white/10"
                style={{ backgroundColor: THEME_COLORS[colorTheme] || THEME_COLORS.claude }}
              >
                {name?.[0]?.toUpperCase() || '?'}
              </div>
            )}
          </div>

          {/* Avatar actions */}
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              onChange={handleAvatarSelect}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors"
            >
              <Upload className="h-4 w-4" />
              Upload
            </button>
            {(avatarPreview || hasExistingAvatar) && (
              <button
                type="button"
                onClick={handleRemoveAvatar}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Remove
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Name Field */}
      <div className="mb-6">
        <label htmlFor="project-name" className="block text-sm font-medium mb-2">
          Name
        </label>
        <input
          id="project-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
          placeholder="Project name"
        />
      </div>

      {/* Description Field */}
      <div>
        <label htmlFor="project-description" className="block text-sm font-medium mb-2">
          Description
        </label>
        <textarea
          id="project-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors resize-none"
          placeholder="Project description (optional)"
        />
      </div>
    </section>
  )
}

export default GeneralSettingsTab
