/**
 * Email Settings Tab
 *
 * Canonical email and email alias configuration.
 */

import { Copy, CheckCircle } from 'lucide-react'

function EmailSettingsTab({
  canonicalEmail,
  emailAlias,
  setEmailAlias,
  organizationSlug,
  copiedEmail,
  handleCopyEmail,
}) {
  const aliasPreview = emailAlias
    ? `${emailAlias}.${organizationSlug || 'org'}@zoea.studio`
    : null

  return (
    <section className="bg-card rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold mb-6">Email Settings</h2>

      {/* Canonical Email (read-only) */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">Canonical Email</label>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={canonicalEmail || 'Not configured'}
            readOnly
            className="flex-1 px-3 py-2 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed"
          />
          {canonicalEmail && (
            <button
              type="button"
              onClick={() => handleCopyEmail(canonicalEmail, 'canonical')}
              className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
              title="Copy to clipboard"
            >
              {copiedEmail === 'canonical' ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Auto-generated from project and organization names. Cannot be changed.
        </p>
      </div>

      {/* Email Alias */}
      <div className="mb-6">
        <label htmlFor="email-alias" className="block text-sm font-medium mb-2">
          Email Alias
        </label>
        <input
          id="email-alias"
          type="text"
          value={emailAlias}
          onChange={(e) => setEmailAlias(e.target.value.toLowerCase())}
          className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
          placeholder="custom-alias"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Must start with a letter, 2-64 characters, lowercase letters, numbers, hyphens, or
          underscores only.
        </p>
      </div>

      {/* Alias Email Preview (read-only) */}
      {aliasPreview && (
        <div>
          <label className="block text-sm font-medium mb-2">Alias Email Preview</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={aliasPreview}
              readOnly
              className="flex-1 px-3 py-2 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed"
            />
            <button
              type="button"
              onClick={() => handleCopyEmail(aliasPreview, 'alias')}
              className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
              title="Copy to clipboard"
            >
              {copiedEmail === 'alias' ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            This will be your custom email address after saving.
          </p>
        </div>
      )}
    </section>
  )
}

export default EmailSettingsTab
