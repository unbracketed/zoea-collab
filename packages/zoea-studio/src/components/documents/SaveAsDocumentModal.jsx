/**
 * Save As Document Modal
 *
 * Modal for saving notebook content as a shared document with name and optional folder.
 */

import { useEffect, useRef, useState } from 'react';
import { Folder, X } from 'lucide-react';
import api from '../../services/api';

function SaveAsDocumentModal({
  isOpen,
  onClose,
  onSave,
  workspaceId,
  defaultName = '',
}) {
  const modalRef = useRef(null);
  const [name, setName] = useState(defaultName);
  const [folderId, setFolderId] = useState(null);
  const [folders, setFolders] = useState([]);
  const [foldersLoading, setFoldersLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setName(defaultName);
      setFolderId(null);
      setError(null);
      setSaving(false);
    }
  }, [isOpen, defaultName]);

  // Load folders when modal opens
  useEffect(() => {
    if (!isOpen || !workspaceId) return;

    const loadFolders = async () => {
      setFoldersLoading(true);
      try {
        const result = await api.fetchFolders({ workspace_id: workspaceId });
        setFolders(result || []);
      } catch (err) {
        console.error('Failed to load folders:', err);
        setFolders([]);
      } finally {
        setFoldersLoading(false);
      }
    };

    loadFolders();
  }, [isOpen, workspaceId]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen && !saving) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose, saving]);

  // Close when clicking outside
  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !saving) {
      onClose();
    }
  };

  const handleSave = async () => {
    if (!name.trim()) return;

    setSaving(true);
    setError(null);

    try {
      await onSave({
        name: name.trim(),
        folder_id: folderId,
      });
      onClose();
    } catch (err) {
      console.error('Failed to save document:', err);
      setError(err.message || 'Failed to save document');
      setSaving(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && name.trim() && !saving) {
      handleSave();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="bg-card text-card-foreground rounded-xl shadow-lg border border-border w-full max-w-md mx-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-as-document-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 id="save-as-document-title" className="text-lg font-semibold">
            Save as Document
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Error display */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Name Field */}
          <div>
            <label htmlFor="document-name" className="block text-sm font-medium mb-2">
              Document Name
            </label>
            <input
              id="document-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
              placeholder="Enter document name"
              autoFocus
              disabled={saving}
            />
          </div>

          {/* Folder Field */}
          <div>
            <label htmlFor="document-folder" className="block text-sm font-medium mb-2">
              Folder (optional)
            </label>
            <div className="relative">
              <Folder className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <select
                id="document-folder"
                value={folderId || ''}
                onChange={(e) => setFolderId(e.target.value ? Number(e.target.value) : null)}
                className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors appearance-none"
                disabled={saving || foldersLoading}
              >
                <option value="">No folder (root)</option>
                {folders.map((folder) => (
                  <option key={folder.id} value={folder.id}>
                    {folder.name}
                  </option>
                ))}
              </select>
            </div>
            {foldersLoading && (
              <p className="mt-1 text-xs text-muted-foreground">Loading folders...</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Document'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SaveAsDocumentModal;
