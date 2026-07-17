import { useCallback, useState } from 'react'

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const [stored, setStored] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key)
      return item ? (JSON.parse(item) as T) : initialValue
    } catch {
      return initialValue
    }
  })

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const next = value instanceof Function ? value(stored) : value
        setStored(next)
        window.localStorage.setItem(key, JSON.stringify(next))
      } catch (e) {
        console.warn(`useLocalStorage: failed to write key "${key}"`, e)
      }
    },
    [key, stored],
  )

  const removeValue = useCallback(() => {
    try {
      window.localStorage.removeItem(key)
      setStored(initialValue)
    } catch {}
  }, [key, initialValue])

  return [stored, setValue, removeValue]
}
