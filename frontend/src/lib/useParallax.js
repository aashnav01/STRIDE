import { useEffect } from 'react'

/*
 * Pointer-driven depth.
 *
 * What actually makes a page read as three-dimensional is not a static
 * tilt — it is layers moving at different rates as the viewer moves.
 * This publishes the pointer position as two CSS custom properties on
 * <html> (--px and --py, each -1..1) and everything else reads from them,
 * so the whole scene responds with one listener and zero per-element JS.
 *
 * Values are eased toward the target each frame rather than snapped, so
 * the scene has weight instead of jitter. The loop only runs while the
 * pointer is actually moving; it parks itself once the scene settles.
 */
export function useParallax() {
  useEffect(() => {
    const fine = window.matchMedia?.('(pointer: fine)').matches
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!fine || reduced) return

    const root = document.documentElement
    let tx = 0, ty = 0      // target
    let cx = 0, cy = 0      // current
    let raf = 0, running = false

    const tick = () => {
      cx += (tx - cx) * 0.075
      cy += (ty - cy) * 0.075
      root.style.setProperty('--px', cx.toFixed(4))
      root.style.setProperty('--py', cy.toFixed(4))
      // park the loop once it has effectively arrived
      if (Math.abs(tx - cx) < 0.0015 && Math.abs(ty - cy) < 0.0015) {
        running = false
        return
      }
      raf = requestAnimationFrame(tick)
    }

    const wake = () => {
      if (!running) { running = true; raf = requestAnimationFrame(tick) }
    }

    const onMove = (e) => {
      tx = (e.clientX / window.innerWidth) * 2 - 1
      ty = (e.clientY / window.innerHeight) * 2 - 1
      wake()
    }
    const onLeave = () => { tx = 0; ty = 0; wake() }

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerleave', onLeave, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerleave', onLeave)
    }
  }, [])
}
