import { describe, it, expect, vi, afterEach } from 'vitest'
import { copyTextToClipboard } from './clipboard'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('copyTextToClipboard', () => {
  it('uses navigator.clipboard.writeText when available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    const execCommand = vi.fn()
    Object.defineProperty(document, 'execCommand', { value: execCommand, configurable: true })

    await copyTextToClipboard('hi')

    expect(writeText).toHaveBeenCalledWith('hi')
    expect(execCommand).not.toHaveBeenCalled()
  })

  it('falls back to document.execCommand when writeText fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    const execCommand = vi.fn().mockReturnValue(true)
    Object.defineProperty(document, 'execCommand', { value: execCommand, configurable: true })

    await copyTextToClipboard('fallback')

    expect(writeText).toHaveBeenCalledWith('fallback')
    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('throws when both clipboard methods fail', async () => {
    vi.stubGlobal('navigator', { clipboard: undefined })

    const execCommand = vi.fn().mockReturnValue(false)
    Object.defineProperty(document, 'execCommand', { value: execCommand, configurable: true })

    await expect(copyTextToClipboard('nope')).rejects.toThrow(/Copy/)
    expect(execCommand).toHaveBeenCalledWith('copy')
  })
})

