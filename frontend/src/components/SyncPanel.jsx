import { useEffect, useState, useCallback } from 'react'
import { CloudOff, CloudUpload, Check, Award } from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import { pendingScreenings, listScreenings, markSynced } from '../lib/db'
import { useOnline } from '../lib/useOnline'
import { useReducedMotion } from '../lib/motion'

// VITE_API_URL is read by Vite at BUILD time and compiled into the
// bundle. If it is unset in a production build the app will call
// localhost and fail, so say so loudly rather than failing at DNS.
const RAW_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_URL = /^https?:\/\//.test(RAW_API) ? RAW_API : `https://${RAW_API}`

if (import.meta.env.PROD) {
  const host = API_URL.replace(/^https?:\/\//, '').split('/')[0]
  if (!import.meta.env.VITE_API_URL) {
    console.error(
      '[config] VITE_API_URL was not set at build time. Set it on the ' +
      'frontend service and redeploy — a restart will not rebuild the bundle.'
    )
  } else if (!host.includes('.')) {
    // a bare service name has no domain and will never resolve
    console.error(
      `[config] VITE_API_URL is "${import.meta.env.VITE_API_URL}", which is a ` +
      'bare hostname with no domain. Use the full public URL, e.g. ' +
      'https://your-service.onrender.com'
    )
  }
}

/*
 * The moment a day in the field lands.
 *
 * ASHA workers are chronically under-acknowledged; watching a dozen
 * screenings tick off one at a time is the closest this app comes to saying
 * "that counted". Records are uploaded one by one (not batched) purely so
 * she can see each one go.
 */
const SyncPanel = ({ onDone }) => {
  const { t } = useLanguage()
  const online = useOnline()
  const reduced = useReducedMotion()
  const [queue, setQueue] = useState([])
  const [doneIds, setDoneIds] = useState([])
  const [running, setRunning] = useState(false)
  const [milestone, setMilestone] = useState(null)

  const load = useCallback(async () => {
    setQueue(await pendingScreenings())
  }, [])

  useEffect(() => {
    let alive = true
    pendingScreenings().then(p => { if (alive) setQueue(p) })
    return () => { alive = false }
  }, [])

  const run = async () => {
    if (running || !online) return
    setRunning(true)
    setDoneIds([])
    const pending = await pendingScreenings()
    for (const row of pending) {
      try {
        const res = await fetch(`${API_URL}/screenings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(row),
        })
        if (!res.ok) break
        await markSynced(row.id)
        setDoneIds(d => [...d, row.id])
        // one at a time, visibly — this pause is the whole point
        if (!reduced) await new Promise(r => setTimeout(r, 260))
      } catch {
        break
      }
    }
    const all = await listScreenings()
    const synced = all.filter(r => r.synced).length
    if (synced > 0 && synced % 10 === 0) setMilestone(synced)
    setRunning(false)
    await load()
    onDone?.()
  }

  if (!queue.length && !running && !milestone) return null

  return (
    <div className="sync">
      {milestone ? (
        <div className="sync-milestone">
          <Award size={26} />
          <strong>{t('milestoneTitle').replace('{n}', milestone)}</strong>
          <span>{t('milestoneSub')}</span>
          <button onClick={() => setMilestone(null)}>{t('milestoneOk')}</button>
        </div>
      ) : (
        <>
          <div className="sync-head">
            <span className="sync-title">
              {online ? <CloudUpload size={16} /> : <CloudOff size={16} />}
              {online ? t('syncReady').replace('{n}', queue.length) : t('syncWaiting').replace('{n}', queue.length)}
            </span>
            <button className="sync-go" onClick={run} disabled={!online || running}>
              {running ? t('syncSending') : t('syncSend')}
            </button>
          </div>
          <ul className="sync-list">
            {queue.map(r => (
              <li key={r.id} className={doneIds.includes(r.id) ? 'sent' : ''}>
                <span className="sync-check">
                  {doneIds.includes(r.id) ? <Check size={13} /> : null}
                </span>
                <span className="sync-name">{r.patient?.name || t('homeUnnamed')}</span>
                <span className="sync-village">{r.patient?.village || '—'}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export default SyncPanel
