import { useEffect, useRef, useState } from 'react'

/*
 * Motion helpers.
 *
 * Every animation here has to clarify, guide or confirm — the 2026 guidance
 * is 200-500ms and purposeful, and a health worker in a hurry is exactly the
 * person a gratuitous animation punishes. All of them yield to
 * prefers-reduced-motion, which some users set for medical reasons.
 */

export function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' &&
      !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!mq) return
    const on = e => setReduced(e.matches)
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return reduced
}

/* Counts to `target` so a risk score arrives rather than appears — it gives
   her a beat to read it before she has to explain it. */
export function useCountUp(target, { duration = 700, decimals = 0 } = {}) {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(reduced ? target : 0)
  const raf = useRef(0)

  useEffect(() => {
    // the first frame does the reduced-motion / null case too, so nothing
    // calls setState straight out of the effect body
    const start = performance.now()
    const tick = (now) => {
      if (reduced || target == null) { setValue(target ?? 0); return }
      const t = Math.min((now - start) / duration, 1)
      setValue(target * (1 - Math.pow(1 - t, 3)))
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration, reduced])

  return Number(value).toFixed(decimals)
}
