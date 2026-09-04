import { useEffect, useState } from 'react'

/* Live connectivity state, so the UI can tell a field worker whether her
   screenings have left the phone yet. */
export function useOnline() {
  const [online, setOnline] = useState(
    () => (typeof navigator === 'undefined' ? true : navigator.onLine)
  )
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}
