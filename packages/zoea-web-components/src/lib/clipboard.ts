export async function copyTextToClipboard(text: string | null | undefined): Promise<void> {
  if (text === undefined || text === null) {
    throw new Error('No text provided to copy')
  }

  const normalizedText = String(text)

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(normalizedText)
      return
    } catch {
      // Fall back to execCommand below (e.g., permission denied / unsupported environment)
    }
  }

  if (typeof document === 'undefined') {
    throw new Error('Clipboard API not available in this environment')
  }

  const textarea = document.createElement('textarea')
  textarea.value = normalizedText
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'

  document.body.appendChild(textarea)

  const selection = document.getSelection?.()
  const originalRange =
    selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null

  textarea.focus()
  textarea.select()

  try {
    const ok = document.execCommand?.('copy')
    if (!ok) {
      throw new Error('Copy command was not successful')
    }
  } finally {
    document.body.removeChild(textarea)
    if (selection && originalRange) {
      selection.removeAllRanges()
      selection.addRange(originalRange)
    }
  }
}
