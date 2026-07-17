import { useEffect } from 'react'

type KeyCombo = {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  shiftKey?: boolean
  altKey?: boolean
}

export function useKeyboardShortcut(combo: KeyCombo, handler: (e: KeyboardEvent) => void) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const match =
        e.key.toLowerCase() === combo.key.toLowerCase() &&
        (combo.ctrlKey ? e.ctrlKey : true) &&
        (combo.metaKey ? e.metaKey : true) &&
        (combo.shiftKey ? e.shiftKey : true) &&
        (combo.altKey ? e.altKey : true)

      if (match) {
        handler(e)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [combo, handler])
}
