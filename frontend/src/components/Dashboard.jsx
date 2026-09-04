import { useEffect, useState, useCallback } from 'react'
import {
  Users, AlertTriangle, AlertCircle, CheckCircle2, CloudOff, RefreshCw,
} from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import { listScreenings, pendingScreenings, syncPending } from '../lib/db'
import { useOnline } from '../lib/useOnline'

// Render's fromService supplies a bare hostname with no scheme; without
// this the value would be treated as a relative path by fetch().
const RAW_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_URL = /^https?:\/\//.test(RAW_API) ? RAW_API : `https://${RAW_API}`

/* Bands are STATUS, not categorical: fixed meaning, never reused as series
   colors, and always carried by an icon + label as well as the hue — amber
   fails 3:1 on a light surface, so colour alone is never the encoding. */
const BANDS = [
  { key: 'low', token: 'var(--success)', Icon: CheckCircle2 },
  { key: 'borderline', token: 'var(--warning)', Icon: AlertCircle },
  { key: 'elevated', token: 'var(--danger)', Icon: AlertTriangle },
]

const Dashboard = () => {
  const { t } = useLanguage()
  const online = useOnline()
  const [rows, setRows] = useState([])
  const [pending, setPending] = useState(0)
  const [syncing, setSyncing] = useState(false)

  const refresh = useCallback(async () => {
    setRows(await listScreenings())
    setPending((await pendingScreenings()).length)
  }, [])

  // read IndexedDB once on mount; the await keeps setState out of the
  // effect body, and `alive` drops a late resolve after unmount
  useEffect(() => {
    let alive = true
    ;(async () => {
      const all = await listScreenings()
      if (!alive) return
      setRows(all)
      setPending(all.filter(r => !r.synced).length)
    })()
    return () => { alive = false }
  }, [])

  const doSync = async () => {
    setSyncing(true)
    try { await syncPending(API_URL) } finally {
      setSyncing(false)
      refresh()
    }
  }

  const total = rows.length
  const counts = BANDS.map(b => ({
    ...b,
    n: rows.filter(r => r.result?.prediction?.band === b.key).length,
  }))
  const elevated = counts.find(c => c.key === 'elevated')?.n ?? 0

  const villages = Object.values(
    rows.reduce((acc, r) => {
      const v = r.patient?.village?.trim() || '—'
      acc[v] = acc[v] || { village: v, n: 0, elevated: 0 }
      acc[v].n++
      if (r.result?.prediction?.band === 'elevated') acc[v].elevated++
      return acc
    }, {})
  ).sort((a, b) => b.n - a.n).slice(0, 8)

  if (total === 0) {
    return (
      <section className="dash">
        <h2>{t('dashTitle')}</h2>
        <p className="dash-empty">{t('dashEmpty')}</p>
      </section>
    )
  }

  return (
    <section className="dash">
      <div className="dash-head">
        <h2>{t('dashTitle')}</h2>
        <button className="dash-sync" onClick={doSync} disabled={syncing || !online}>
          {online ? <RefreshCw size={14} className={syncing ? 'spin' : ''} /> : <CloudOff size={14} />}
          {online ? (pending ? t('dashSyncNow') : t('dashAllSynced')) : t('dashOffline')}
        </button>
      </div>

      {/* headline numbers — a stat tile, not a chart */}
      <div className="dash-tiles">
        <div className="dash-tile">
          <Users size={15} />
          <strong>{total}</strong>
          <span>{t('dashTotal')}</span>
        </div>
        <div className="dash-tile">
          <AlertTriangle size={15} />
          <strong>{elevated}</strong>
          <span>{t('dashElevated')}</span>
        </div>
        <div className="dash-tile">
          <CloudOff size={15} />
          <strong>{pending}</strong>
          <span>{t('dashPending')}</span>
        </div>
      </div>

      {/* band mix — every segment is directly labelled, so hue is never the
          sole encoding (amber is below 3:1 on this surface) */}
      <div className="dash-block">
        <h3>{t('dashByBand')}</h3>
        <div className="dash-bar" role="img"
             aria-label={counts.map(c => `${t('band' + c.key[0].toUpperCase() + c.key.slice(1))}: ${c.n}`).join(', ')}>
          {counts.filter(c => c.n > 0).map(c => (
            <span key={c.key} className="dash-seg"
                  style={{ flexGrow: c.n, background: c.token }} />
          ))}
        </div>
        <ul className="dash-legend">
          {counts.map(({ key, token, Icon, n }) => (
            <li key={key}>
              <Icon size={14} style={{ color: token }} />
              <span className="dash-legend-label">
                {t(`band${key[0].toUpperCase()}${key.slice(1)}`)}
              </span>
              <strong>{n}</strong>
              <span className="dash-legend-pct">
                {total ? Math.round((n / total) * 100) : 0}%
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="dash-block">
        <h3>{t('dashByVillage')}</h3>
        <table className="dash-table">
          <thead>
            <tr>
              <th>{t('fieldVillage')}</th>
              <th>{t('dashScreened')}</th>
              <th>{t('dashElevated')}</th>
            </tr>
          </thead>
          <tbody>
            {villages.map(v => (
              <tr key={v.village}>
                <td>{v.village}</td>
                <td>{v.n}</td>
                <td className={v.elevated ? 'is-elevated' : ''}>{v.elevated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default Dashboard
