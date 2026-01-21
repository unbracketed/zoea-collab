import { useState, useEffect } from 'react'

const ThemeToggler = ({ inline = false }) => {
  const getStoredTheme = () => localStorage.getItem('theme')
  const setStoredTheme = (theme) => localStorage.setItem('theme', theme)

  const getPreferredTheme = () => {
    const storedTheme = getStoredTheme()
    if (storedTheme) {
      return storedTheme
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }

  const [theme, setTheme] = useState(getPreferredTheme())
  const [showDropdown, setShowDropdown] = useState(false)

  const setThemeAttribute = (theme) => {
    const resolvedTheme = theme === 'auto'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme
    if (resolvedTheme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  useEffect(() => {
    setThemeAttribute(theme)
    setStoredTheme(theme)
  }, [theme])

  useEffect(() => {
    // Listen for system theme changes when in auto mode
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      if (theme === 'auto') {
        setThemeAttribute('auto')
      }
    }
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme])

  const handleThemeChange = (newTheme) => {
    setTheme(newTheme)
    setShowDropdown(false)
  }

  const getActiveIcon = () => {
    if (theme === 'auto') {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-circle-half" viewBox="0 0 16 16">
          <path d="M8 15A7 7 0 1 0 8 1zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16"/>
        </svg>
      )
    } else if (theme === 'light') {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-sun-fill" viewBox="0 0 16 16">
          <path d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708"/>
        </svg>
      )
    } else {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-moon-stars-fill" viewBox="0 0 16 16">
          <path d="M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278"/>
          <path d="M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.73 1.73 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.73 1.73 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.73 1.73 0 0 0 1.097-1.097z"/>
        </svg>
      )
    }
  }

  // Inline version for Settings page
  if (inline) {
    return (
      <div>
        <label className="block text-sm font-medium mb-1">Theme</label>
        <div className="flex w-full rounded-md border border-border" role="group" aria-label="Theme selection">
          <button
            type="button"
            className={`flex-1 px-3 py-2 text-sm transition-colors rounded-l-md ${theme === 'light' ? 'bg-primary text-white' : 'bg-transparent text-text-secondary hover:bg-surface-hover'}`}
            onClick={() => handleThemeChange('light')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="inline mr-2" viewBox="0 0 16 16">
              <path d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708"/>
            </svg>
            Light
          </button>
          <button
            type="button"
            className={`flex-1 px-3 py-2 text-sm border-l border-border transition-colors ${theme === 'dark' ? 'bg-primary text-white' : 'bg-transparent text-text-secondary hover:bg-surface-hover'}`}
            onClick={() => handleThemeChange('dark')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="inline mr-2" viewBox="0 0 16 16">
              <path d="M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278"/>
              <path d="M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.73 1.73 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.73 1.73 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.73 1.73 0 0 0 1.097-1.097z"/>
            </svg>
            Dark
          </button>
          <button
            type="button"
            className={`flex-1 px-3 py-2 text-sm border-l border-border transition-colors rounded-r-md ${theme === 'auto' ? 'bg-primary text-white' : 'bg-transparent text-text-secondary hover:bg-surface-hover'}`}
            onClick={() => handleThemeChange('auto')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="inline mr-2" viewBox="0 0 16 16">
              <path d="M8 15A7 7 0 1 0 8 1zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16"/>
            </svg>
            Auto
          </button>
        </div>
        <small className="block text-sm text-text-secondary mt-2">
          {theme === 'auto'
            ? 'Automatically matches your system preference'
            : `Currently using ${theme} theme`
          }
        </small>
      </div>
    )
  }

  // Fixed floating version (legacy, kept for compatibility)
  return (
    <div className="fixed bottom-0 right-0 mb-3 mr-3 relative">
      <button
        className="bg-primary text-white py-2 px-3 rounded-md flex items-center gap-1 hover:opacity-90 transition-opacity"
        id="bd-theme"
        type="button"
        aria-expanded={showDropdown}
        aria-label="Toggle theme (auto)"
        onClick={() => setShowDropdown(!showDropdown)}
      >
        {getActiveIcon()}
        <span className="sr-only" id="bd-theme-text">Toggle theme</span>
      </button>
      {showDropdown && (
        <ul
          className="absolute bottom-full right-0 mb-1 bg-surface border border-border rounded-md shadow-lg py-1 min-w-32"
          aria-labelledby="bd-theme-text"
        >
          <li>
            <button
              type="button"
              className={`w-full px-3 py-2 text-left flex items-center text-sm hover:bg-surface-hover transition-colors ${theme === 'light' ? 'bg-surface-hover' : ''}`}
              onClick={() => handleThemeChange('light')}
              aria-pressed={theme === 'light'}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="mr-2" viewBox="0 0 16 16">
                <path d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708"/>
              </svg>
              Light
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className={`ml-auto ${theme === 'light' ? '' : 'hidden'}`} viewBox="0 0 16 16">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0"/>
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`w-full px-3 py-2 text-left flex items-center text-sm hover:bg-surface-hover transition-colors ${theme === 'dark' ? 'bg-surface-hover' : ''}`}
              onClick={() => handleThemeChange('dark')}
              aria-pressed={theme === 'dark'}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="mr-2" viewBox="0 0 16 16">
                <path d="M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278"/>
                <path d="M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.73 1.73 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.73 1.73 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.73 1.73 0 0 0 1.097-1.097z"/>
              </svg>
              Dark
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className={`ml-auto ${theme === 'dark' ? '' : 'hidden'}`} viewBox="0 0 16 16">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0"/>
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`w-full px-3 py-2 text-left flex items-center text-sm hover:bg-surface-hover transition-colors ${theme === 'auto' ? 'bg-surface-hover' : ''}`}
              onClick={() => handleThemeChange('auto')}
              aria-pressed={theme === 'auto'}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="mr-2" viewBox="0 0 16 16">
                <path d="M8 15A7 7 0 1 0 8 1zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16"/>
              </svg>
              Auto
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className={`ml-auto ${theme === 'auto' ? '' : 'hidden'}`} viewBox="0 0 16 16">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0"/>
              </svg>
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}

export default ThemeToggler
