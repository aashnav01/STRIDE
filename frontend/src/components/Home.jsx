import { useEffect, useState } from 'react'
import {
  Play, WifiOff, ChevronRight, CheckCircle2, AlertTriangle, AlertCircle,
} from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import { listScreenings } from '../lib/db'

const BAND_ICON = { low: CheckCircle2, borderline: AlertCircle, elevated: AlertTriangle }

/*
 * The ASHA worker's home. She opens this standing next to a patient, so it
 * shows one obvious action and her own numbers — no scrolling, no pitch.
 * The narrative lives behind "How it works" for judges and demos.
 */
const Home = ({ onStart }) => {
  const { t } = useLanguage()
  const [rows, setRows] = useState([])

  useEffect(() => {
    let alive = true
    listScreenings().then(all => { if (alive) setRows(all) })
    return () => { alive = false }
  }, [])

  const hour = new Date().getHours()
  const greetKey = hour < 12 ? 'greetMorning' : hour < 17 ? 'greetAfternoon' : 'greetEvening'

  const today = new Date().toDateString()
  const todayCount = rows.filter(r => new Date(r.createdAt).toDateString() === today).length
  const pending = rows.filter(r => !r.synced).length
  const recent = rows.slice(0, 4)

  return (
    <section className="home">
      <p className="home-greet">{t(greetKey)}</p>
      <h1 className="home-title">{t('homeHeading')}</h1>
      <p className="home-sub">{t('homeSub')}</p>

      <button className="home-start" onClick={onStart}>
        <span className="home-start-icon"><Play size={22} /></span>
        <span className="home-start-text">
          <strong>{t('homeStart')}</strong>
          <small>{t('homeStartHint')}</small>
        </span>
        <ChevronRight size={20} className="home-start-arrow" />
      </button>

      <div className="home-stats">
        <div><strong>{todayCount}</strong><span>{t('homeToday')}</span></div>
        <div><strong>{rows.length}</strong><span>{t('homeTotal')}</span></div>
        <div className={pending ? 'is-pending' : ''}>
          <strong>{pending}</strong><span>{t('homePending')}</span>
        </div>
      </div>

      <p className="home-offline">
        <WifiOff size={14} /> {t('homeOfflineNote')}
      </p>

      {recent.length > 0 && (
        <div className="home-recent">
          <h2>{t('homeRecent')}</h2>
          <ul>
            {recent.map(r => {
              const b = r.result?.prediction?.band || 'low'
              const Icon = BAND_ICON[b] || CheckCircle2
              return (
                <li key={r.id}>
                  <Icon size={16} className={`band-${b}`} />
                  <span className="home-recent-name">
                    {r.patient?.name || t('homeUnnamed')}
                  </span>
                  <span className="home-recent-village">{r.patient?.village || '—'}</span>
                  <span className={`home-recent-band band-${b}`}>
                    {t(`band${b[0].toUpperCase()}${b.slice(1)}`)}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

    </section>
  )
}

export default Home
