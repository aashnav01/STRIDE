import { useEffect, useRef } from 'react'
import { Check } from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import { useReducedMotion } from '../lib/motion'

/*
 * The 30-60s analysis wait is the moment she wonders whether the app has
 * frozen. A little figure walking the length of the track says "we are
 * watching the walk" without asking her to read anything, and it keeps
 * moving so the screen never looks dead.
 */
const STEP_KEYS = ['progUpload', 'progPose', 'progMetrics', 'progScore']

const RAD = Math.PI / 180
const SEG = { thigh: 15, shank: 15, upper: 11, fore: 10, spine: 18 }

const WalkProgress = ({ step, slow }) => {
  const { t } = useLanguage()
  const reduced = useReducedMotion()
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf = 0

    const draw = (now) => {
      raf = requestAnimationFrame(draw)
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const r = canvas.getBoundingClientRect()
      const w = r.width, h = r.height
      if (canvas.width !== Math.round(w * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const frac = (step + 0.5) / STEP_KEYS.length
      const ground = h - 9
      const x = 16 + (w - 42) * frac

      // track
      ctx.strokeStyle = 'rgba(15,23,42,0.10)'
      ctx.lineWidth = 2; ctx.lineCap = 'round'
      ctx.beginPath(); ctx.moveTo(10, ground); ctx.lineTo(w - 10, ground); ctx.stroke()
      // covered ground
      ctx.strokeStyle = 'rgba(79,70,229,0.85)'
      ctx.beginPath(); ctx.moveTo(10, ground); ctx.lineTo(Math.max(10, x - 6), ground); ctx.stroke()

      const ph = reduced ? 1.1 : now / 300
      const hip = { x, y: ground - 30 }
      const sho = { x: x + 1.5, y: hip.y - SEG.spine }

      const leg = (p) => {
        const tA = 28 * Math.sin(p) * RAD
        const kF = (22 + 26 * (1 - Math.cos(p + 1.15)) / 2) * RAD
        const knee = { x: hip.x + SEG.thigh * Math.sin(tA), y: hip.y + SEG.thigh * Math.cos(tA) }
        const sA = tA - kF
        return { knee, ankle: { x: knee.x + SEG.shank * Math.sin(sA), y: knee.y + SEG.shank * Math.cos(sA) } }
      }
      const arm = (p) => {
        const uA = 30 * Math.sin(p) * RAD
        const el = { x: sho.x + SEG.upper * Math.sin(uA), y: sho.y + SEG.upper * Math.cos(uA) }
        const fA = uA + 28 * RAD
        return { el, wr: { x: el.x + SEG.fore * Math.sin(fA), y: el.y + SEG.fore * Math.cos(fA) } }
      }
      const L = leg(ph), R = leg(ph + Math.PI)
      const aL = arm(ph + Math.PI), aR = arm(ph)

      ctx.lineWidth = 2.2
      ctx.strokeStyle = 'rgba(79,70,229,0.45)'
      ctx.beginPath()
      ctx.moveTo(sho.x, sho.y); ctx.lineTo(aR.el.x, aR.el.y); ctx.lineTo(aR.wr.x, aR.wr.y)
      ctx.moveTo(hip.x, hip.y); ctx.lineTo(R.knee.x, R.knee.y); ctx.lineTo(R.ankle.x, R.ankle.y)
      ctx.stroke()

      ctx.strokeStyle = 'rgba(79,70,229,1)'
      ctx.beginPath()
      ctx.moveTo(sho.x, sho.y); ctx.lineTo(hip.x, hip.y)
      ctx.moveTo(sho.x, sho.y); ctx.lineTo(aL.el.x, aL.el.y); ctx.lineTo(aL.wr.x, aL.wr.y)
      ctx.moveTo(hip.x, hip.y); ctx.lineTo(L.knee.x, L.knee.y); ctx.lineTo(L.ankle.x, L.ankle.y)
      ctx.stroke()

      ctx.beginPath(); ctx.arc(sho.x + 1, sho.y - 6, 5, 0, 7)
      ctx.fillStyle = 'rgba(79,70,229,1)'; ctx.fill()
    }

    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [step, reduced])

  return (
    <div className="walkprog">
      <canvas ref={ref} className="walkprog-canvas" aria-hidden="true" />
      {slow && <p className="walkprog-slow">{t('progSlow')}</p>}
      <ol className="walkprog-steps">
        {STEP_KEYS.map((k, i) => (
          <li key={k} className={i < step ? 'done' : i === step ? 'on' : ''}>
            <span className="walkprog-dot">{i < step ? <Check size={11} /> : null}</span>
            {t(k)}
          </li>
        ))}
      </ol>
    </div>
  )
}

export default WalkProgress
