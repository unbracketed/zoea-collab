/**
 * Image Picker Modal for Yoopta Editor
 *
 * Modal component for browsing and selecting images from the project/workspace
 * document library or uploading new images to insert into Yoopta documents.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { X, Search, Upload, Image as ImageIcon, Check } from 'lucide-react';
import { useWorkspaceStore } from '../../stores';
import api from '../../services/api';

/**
 * ImagePickerModal - Browse or upload images for Yoopta editor
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is open
 * @param {Function} props.onClose - Callback when modal closes
 * @param {Function} props.onSelect - Callback when image is selected: ({ src, alt, width, height }) => void
 * @param {number} props.projectId - Project ID to load images from (optional, falls back to store)
 * @param {number} props.workspaceId - Workspace ID for uploads (optional, falls back to store)
 */
export default function ImagePickerModal({ isOpen, onClose, onSelect, projectId: propProjectId, workspaceId: propWorkspaceId }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);

  const fileInputRef = useRef(null);
  const storeProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const storeWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  // Use props if provided, otherwise fall back to store
  const currentProjectId = propProjectId || storeProjectId;
  const currentWorkspaceId = propWorkspaceId || storeWorkspaceId;

  // Define loadImages before the useEffect that uses it
  const loadImages = useCallback(async () => {
    if (!currentProjectId) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchDocuments({
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId || null,
        document_type: 'image',
        page_size: 50,
        include_previews: false,
      });
      setImages(data.documents || []);
    } catch (err) {
      console.error('[ImagePickerModal] Failed to load images', err);
      setError(err.message || 'Failed to load images');
    } finally {
      setLoading(false);
    }
  }, [currentProjectId, currentWorkspaceId]);

  // Load images when modal opens
  useEffect(() => {
    if (isOpen && currentProjectId) {
      loadImages();
    }
  }, [isOpen, currentProjectId, loadImages]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedImage(null);
      setSearchQuery('');
      setError(null);
    }
  }, [isOpen]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!currentProjectId || !currentWorkspaceId) {
      setError('Project and workspace required for upload');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const response = await api.createImageDocument({
        name: file.name,
        description: '',
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        file,
      });

      // Add the new image to the list and select it
      setImages((prev) => [response, ...prev]);
      setSelectedImage(response);
    } catch (err) {
      console.error('Failed to upload image', err);
      setError(err.message || 'Failed to upload image');
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleSelect = (image) => {
    setSelectedImage(image);
  };

  const handleInsert = () => {
    if (selectedImage && selectedImage.image_file) {
      onSelect({
        src: selectedImage.image_file,
        alt: selectedImage.name || 'Image',
        width: selectedImage.width || null,
        height: selectedImage.height || null,
      });
    }
  };

  if (!isOpen) return null;

  // Filter images by search query
  const filteredImages = images.filter((img) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      img.name?.toLowerCase().includes(query) ||
      img.description?.toLowerCase().includes(query)
    );
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-card rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col border border-border" style={{ backgroundColor: 'var(--card, #fff)' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-lg font-semibold">Insert Image</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-background text-text-secondary"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search and upload */}
        <div className="px-4 py-3 border-b border-border">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary" />
              <input
                type="text"
                placeholder="Search images..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleUploadClick}
              disabled={uploading || !currentProjectId || !currentWorkspaceId}
              className="px-4 py-2 bg-primary text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              <Upload className="h-4 w-4" />
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
          {error && (
            <p className="mt-2 text-sm text-red-500">{error}</p>
          )}
        </div>

        {/* Image grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <svg
                className="animate-spin h-6 w-6 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                role="status"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            </div>
          ) : filteredImages.length === 0 ? (
            <div className="text-center py-8 text-text-secondary">
              <ImageIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>{searchQuery ? 'No images match your search.' : 'No images in this project yet.'}</p>
              <p className="text-sm mt-1">Upload an image to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
              {filteredImages.map((img) => {
                const isSelected = selectedImage?.id === img.id;
                return (
                  <button
                    key={img.id}
                    onClick={() => handleSelect(img)}
                    className={`relative aspect-square border-2 rounded-lg overflow-hidden transition ${
                      isSelected
                        ? 'border-primary ring-2 ring-primary/50'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <img
                      src={img.image_file}
                      alt={img.name}
                      className="w-full h-full object-cover"
                    />
                    {isSelected && (
                      <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                        <div className="bg-primary text-white rounded-full p-1">
                          <Check className="h-4 w-4" />
                        </div>
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-1">
                      <p className="text-xs text-white truncate">{img.name}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-background/50">
          <p className="text-sm text-text-secondary">
            {selectedImage ? `Selected: ${selectedImage.name}` : 'Select an image to insert'}
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-border rounded-md hover:bg-background transition"
            >
              Cancel
            </button>
            <button
              onClick={handleInsert}
              disabled={!selectedImage}
              className="px-4 py-2 bg-primary text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              Insert Image
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
