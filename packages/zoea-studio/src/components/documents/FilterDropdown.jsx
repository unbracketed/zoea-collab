/**
 * Filter Dropdown Component
 *
 * Reusable dropdown for filter selection (Google Drive style).
 */

import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

function FilterDropdown({ label, options, value, onChange, icon: Icon }) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Find selected option label
  const selectedOption = options.find((opt) => opt.id === value)
  const displayLabel = selectedOption ? selectedOption.label : label

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const handleSelect = (optionId) => {
    onChange(optionId)
    setIsOpen(false)
  }

  const isActive = value !== null

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
          isActive
            ? 'bg-primary/10 text-primary border-primary/30 font-medium'
            : 'border-border hover:bg-muted/50 text-text-primary'
        }`}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        {Icon && <Icon className="h-4 w-4" />}
        <span>{displayLabel}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-1 min-w-[160px] bg-card border border-border rounded-lg shadow-lg z-50 py-1">
          {/* Clear option if filter is active */}
          {isActive && (
            <>
              <button
                type="button"
                onClick={() => handleSelect(null)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors text-muted-foreground"
              >
                Clear filter
              </button>
              <div className="border-t border-border my-1" />
            </>
          )}

          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => handleSelect(option.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors ${
                value === option.id ? 'text-primary font-medium' : ''
              }`}
            >
              {option.icon && <option.icon className="h-4 w-4 text-text-secondary" />}
              <span className="flex-1">{option.label}</span>
              {value === option.id && <Check className="h-4 w-4 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default FilterDropdown
