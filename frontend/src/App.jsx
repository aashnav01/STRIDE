import { useState, useEffect } from 'react'
import { Camera, Play, FileDown, Table, AlertTriangle, RotateCcw, CloudOff, Cloud, ChevronLeft } from 'lucide-react'
import { useLanguage } from './i18n/useLanguage'
import LanguageSwitcher from './components/LanguageSwitcher'
import RecordingChecklist from './components/RecordingChecklist'
import ScreeningIntake from './components/ScreeningIntake'
import Dashboard from './components/Dashboard'
import Home from './components/Home'
import AppBackground from './components/AppBackground'
import { Kingkhap } from './components/Gamosa'
import WalkProgress from './components/WalkProgress'
import SyncPanel from './components/SyncPanel'
import { useCountUp } from './lib/motion'
import Guidance from './components/Guidance'
import { saveScreening, syncPending } from './lib/db'
import { useOnline } from './lib/useOnline'
import { useParallax } from './lib/useParallax'
import { SYMPTOM_QUESTIONS, symptomBand } from './constants/symptomQuestions'
import ReferralCard from './components/ReferralCard'
import WhyNER from './components/WhyNER'
import './App.css'

// VITE_API_URL is read by Vite at BUILD time and compiled into the
// bundle. If it is unset in a production build the app will call
// localhost and fail, so say so loudly rather than failing at DNS.
const RAW_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
if (import.meta.env.PROD && !import.meta.env.VITE_API_URL) {
  console.error(
    '[config] VITE_API_URL was not set at build time. Set it on the ' +
    'frontend service and redeploy — a restart will not rebuild the bundle.'
  )
}
const API_URL = /^https?:\/\//.test(RAW_API) ? RAW_API : `https://${RAW_API}`

const PROGRESS_STEP_COUNT = 4     // labels live in WalkProgress, translated
const PROGRESS_STEP_MS = 7500

function App() {
  const { t } = useLanguage()
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [videoUrl, setVideoUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [intake, setIntake] = useState({ patient: {}, symptoms: {} })
  const [savedId, setSavedId] = useState(null)
  // her home, then the screening flow — there is no third surface
  const [view, setView] = useState('home')
  const online = useOnline()
  useParallax()   // publishes --px/--py for the depth layers

  /* ---------- flush the offline queue when a network appears ---------- */
  useEffect(() => {
    if (online) syncPending(API_URL).catch(() => {})
  }, [online])

  /* ---------- fake step progress while analyzing ---------- */
  useEffect(() => {
    if (!analyzing) return
    const id = setInterval(() => {
      setProgressStep(s => Math.min(s + 1, PROGRESS_STEP_COUNT - 1))
    }, PROGRESS_STEP_MS)
    return () => clearInterval(id)
  }, [analyzing])

  /* ---------- video change ---------- */
  const handleVideoChange = (event) => {
    const file = event.target.files[0]
    if (!file) return
    const MAX_SIZE = 50 * 1024 * 1024
    if (file.size > MAX_SIZE) {
      setSelectedVideo(null); setVideoUrl(null); setResult(null)
      setError('Video is too large. Please select a video smaller than 50 MB.')
      return
    }
    setSelectedVideo(file)
    setVideoUrl(URL.createObjectURL(file))
    setResult(null); setError(null)
  }

  /* ---------- analyze ---------- */
  const handleAnalyze = async () => {
    if (!selectedVideo) return
    setAnalyzing(true); setProgressStep(0); setResult(null); setError(null)
    const formData = new FormData()
    formData.append('video', selectedVideo)
    try {
      const response = await fetch(`${API_URL}/extract-pose`, { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok || !data.success) {
        // FastAPI HTTPException uses `detail`; keep `error` as a fallback.
        throw new Error(data.detail || data.error || 'Video analysis failed')
      }
      setResult(data)

      // written to IndexedDB first: the screening survives with no network,
      // and the sync pass promotes it whenever one appears
      const total = SYMPTOM_QUESTIONS.reduce((n, q) => n + (intake.symptoms[q.id] ?? 0), 0)
      const row = await saveScreening({
        patient: intake.patient,
        symptoms: intake.symptoms,
        symptomTotal: total,
        symptomBand: symptomBand(total),
        result: data,
      })
      setSavedId(row.id)
      syncPending(API_URL).catch(() => {})
    } catch (err) {
      setError(err.message || 'Could not connect to the backend.')
    } finally {
      setAnalyzing(false)
    }
  }

  /* ---------- download PDF ---------- */
  const downloadPDF = async () => {
    if (!result) return
    try {
      const response = await fetch(`${API_URL}/generate-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...result, intake }),
      })
      if (!response.ok) {
        const e = await response.json().catch(() => ({}))
        throw new Error(e.detail || 'PDF generation failed')
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = 'OA_Screening_Report.pdf'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err) { setError(err.message || 'Could not generate PDF report.') }
  }

  /* ---------- download CSV ---------- */
  const downloadCSV = () => {
    if (!result) return
    const p = result.prediction
    let csv = 'OA Risk Analysis Report\n\n'
    csv += `Risk Score,${(p.risk * 100).toFixed(1)}%\nRisk Band,${p.band}\n`
    if (p.stage) csv += `Severity Grade,${p.stage.grade}\nConfidence,"${p.stage.confidence}"\n`
    csv += '\nGait Measurements\nMeasurement,Value,Unit,Reading\n'
    p.measurements?.forEach(m => { csv += `"${m.label}","${m.value}","${m.unit}","${m.reading}"\n` })
    csv += `\nFrames Processed,${result.frames_processed}\nFrames Detected,${result.frames_detected}\n`
    csv += '\nDisclaimer\n"AI-assisted screening result. Not a medical diagnosis."\n'
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'OA_Analysis_Report.csv'
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const riskPct = useCountUp(result ? result.prediction.risk * 100 : 0, { decimals: 1 })
  const band = result?.prediction?.band ?? 'low'
  const bandLabel = t(`band${band.charAt(0).toUpperCase()}${band.slice(1)}`)
  // Prefer the backend's dedicated worse_knee block; fall back to a "Worse
  // knee ..." measurement if a future model surfaces one.
  const worseKnee = result?.prediction?.worse_knee
  const worseKneeMeasurement = result?.prediction?.measurements?.find(m => m.label?.startsWith('Worse knee'))
  const worseKneeSide = worseKnee?.side ?? result?.prediction?.worse_knee_side
  const worseKneeReading = worseKnee?.reading ?? worseKneeMeasurement?.reading

  return (
    <div className="app">
      <AppBackground />

      {/* ---- HEADER ---- */}
      <header className="header">
        <div className="logo">
          <div className="logo-icon"><Kingkhap size={27} /></div>
          <div className="logo-text">
            <h2>{t('homeTitle')}</h2>
            <p>{t('tagline')}</p>
          </div>
        </div>

        <div className="header-right">
          <span className={`net-badge${online ? '' : ' off'}`}>
            {online ? <Cloud size={13} /> : <CloudOff size={13} />}
            {online ? t('dashAllSynced') : t('dashOffline')}
          </span>
          <LanguageSwitcher />
        </div>
      </header>

      {/* ---- MAIN ---- */}
      <main className="main-content">

        {view === 'home' && (
          <>
            <Home onStart={() => setView('screen')} />
            <SyncPanel />
          </>
        )}


        {view === 'screen' && (<>
        <button className="back-link" onClick={() => setView('home')}>
          <ChevronLeft size={16} /> {t('backHome')}
        </button>

        {/* UPLOAD CARD */}
        <section className="glass-card upload-card" id="upload-section">

          <ScreeningIntake value={intake} onChange={setIntake} />

          {!selectedVideo ? (
            <label className="upload-area">
              <input type="file" accept="video/*" onChange={handleVideoChange} style={{ display: 'none' }} />
              <div className="upload-icon"><Camera size={30} /></div>
              <h3>{t('dropVideo')}</h3>
              <p>{t('browseFiles')}</p>
              <span className="file-types">MP4 · MOV · AVI · MKV · WEBM</span>
            </label>
          ) : (
            <div className="video-section">
              <video className="video-preview" controls src={videoUrl}>
                Your browser does not support video.
              </video>
              <div className="file-info">
                <div className="file-info-text">
                  <h3>{selectedVideo.name}</h3>
                  <p>{(selectedVideo.size / (1024 * 1024)).toFixed(2)} MB</p>
                </div>
                <label className="change-video">
                  <RotateCcw size={16} /> {t('changeVideo')}
                  <input type="file" accept="video/*" onChange={handleVideoChange} />
                </label>
              </div>
            </div>
          )}

          {!analyzing && !result && <RecordingChecklist />}

          <button
            className="analyze-button"
            disabled={!selectedVideo || analyzing}
            onClick={handleAnalyze}
          >
            {analyzing ? t('analyzing') : (<><Play size={18} /> {t('analyzeVideo')}</>)}
          </button>

          {analyzing && <WalkProgress step={progressStep} />}

          {error && (
            <div className="error-message">
              <AlertTriangle size={18} /> {error}
            </div>
          )}
        </section>

        {/* RESULTS */}
        {result && result.prediction && (
          <section className={`glass-card results-card reveal risk-${band}`}>

            {/* STICKY ACTIONS */}
            <div className="sticky-actions">
              <button className="download-button primary" onClick={downloadPDF}>
                <FileDown size={16} /> {t('downloadPDF')}
              </button>
            </div>

            <div className="report-header">
              <span className="badge"><span className="badge-dot" />{t('analysisComplete')}</span>
              <h2>{t('reportTitle')}</h2>
              <p>{t('reportSubtitle')} · {result.frames_detected} of {result.frames_processed} frames with pose detected</p>
            </div>

            {/* RISK + BAND */}
            <div className="dashboard-grid">
              <div className={`metric-card risk-${band}`}>
                <h3>{t('riskScoreLabel')}</h3>
                <div className="risk-ring-wrap">
                  <div className="risk-circle">
                    {riskPct}%
                  </div>
                </div>
                <span className="risk-band">{bandLabel}</span>
              </div>

              {worseKneeSide && (
                <div className="metric-card worse-knee-card">
                  <h3>{t('worseKneeLabel')}</h3>
                  <div className="worse-knee-side">
                    {t(`worseKnee_${worseKneeSide}`)}
                  </div>
                  {worseKneeReading && (
                    <p className="worse-knee-reading">{worseKneeReading}</p>
                  )}
                </div>
              )}
            </div>

            {/* WHY THIS SCORE */}
            {result.prediction.reasons?.length > 0 && (
              <div className="measurements">
                <h3>{t('whyThisScore')}</h3>
                <ul style={{margin:0, paddingLeft:'1.2em', lineHeight:1.5}}>
                  {result.prediction.reasons.map((r, i) => (
                    <li key={i} style={{marginBottom:8}}>{r}</li>
                  ))}
                </ul>
                {result.prediction.surrogate_fidelity != null && (
                  <p className="disclaimer" style={{marginTop:10}}>
                    Explainability model fidelity: {result.prediction.surrogate_fidelity}
                  </p>
                )}
              </div>
            )}

            {/* SEVERITY — hidden for the low band; a "moderate" grade on a
                healthy-range subject is misleading, so we don't show it. */}
            {band !== 'low' && (
              <>
                {result.prediction.stage && (
                  <div className="dashboard-grid single">
                    <div className="metric-card">
                      <h3>{t('severityGrade')}</h3>
                      <div className="severity-grade">{result.prediction.stage.grade}</div>
                      <p className="severity-conf">{result.prediction.stage.confidence}</p>
                    </div>
                  </div>
                )}

                {result.prediction.stage?.probabilities && (
                  <div className="measurements">
                    <h3>Severity Stage Breakdown</h3>
                    <div className="measurement-grid">
                      {['early', 'moderate', 'severe'].map(g => {
                        const p = result.prediction.stage.probabilities[g] ?? 0
                        return (
                          <div className="measurement" key={g}>
                            <div className="measurement-header">
                              <span className="measurement-label" style={{textTransform:'capitalize'}}>{g}</span>
                              <span className="measurement-value">{(p * 100).toFixed(1)}%</span>
                            </div>
                            <div className="measurement-reading" aria-hidden="true">
                              <div style={{
                                height: 6, borderRadius: 3, marginTop: 6,
                                background: 'rgba(15,23,42,0.08)', overflow: 'hidden'
                              }}>
                                <div style={{
                                  width: `${(p * 100).toFixed(1)}%`, height: '100%',
                                  background: 'var(--primary)'
                                }}/>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                    {result.prediction.stage.note && (
                      <p className="disclaimer" style={{marginTop:12}}>
                        {result.prediction.stage.note}
                      </p>
                    )}
                  </div>
                )}
              </>
            )}

            {/* MEASUREMENTS */}
            {result.prediction.measurements?.length > 0 && (
              <div className="measurements">
                <h3>{t('gaitMeasurements')}</h3>
                <div className="measurement-grid">
                  {result.prediction.measurements.map((m, i) => (
                    <div className="measurement" key={i}>
                      <div className="measurement-header">
                        <span className="measurement-label">{m.label}</span>
                        <span className="measurement-value">{m.value} {m.unit}</span>
                      </div>
                      <div className="measurement-reading">
                        {m.reading}
                        {m.cohort_median != null && (
                          <span style={{opacity:0.7}}> · cohort median {m.cohort_median} {m.unit}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CAPTURE QUALITY */}
            {result.quality && (
              <div className="measurements">
                <h3>{t('captureQuality')}</h3>
                <div className="measurement-grid">
                  <div className="measurement">
                    <div className="measurement-header">
                      <span className="measurement-label">Clip length</span>
                      <span className="measurement-value">{result.quality.duration_s} s</span>
                    </div>
                  </div>
                  <div className="measurement">
                    <div className="measurement-header">
                      <span className="measurement-label">Pose detected</span>
                      <span className="measurement-value">
                        {(result.quality.detection_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="measurement">
                    <div className="measurement-header">
                      <span className="measurement-label">Mean knee visibility</span>
                      <span className="measurement-value">
                        {result.quality.mean_knee_visibility.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <div className="measurement">
                    <div className="measurement-header">
                      <span className="measurement-label">Frame rate</span>
                      <span className="measurement-value">
                        {result.quality.source_fps} → {result.quality.target_fps} fps
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* CAVEATS */}
            {result.prediction.caveats?.length > 0 && (
              <div className="measurements">
                <h3>{t('limitsOfResult')}</h3>
                <ul style={{margin:0, paddingLeft:'1.2em', lineHeight:1.5, fontSize:'0.9em', opacity:0.85}}>
                  {result.prediction.caveats.map((c, i) => (
                    <li key={i} style={{marginBottom:6}}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* REFERRAL */}
            <ReferralCard band={band} />

            {/* PREVENTIVE GUIDANCE — SIH26004 (h) */}
            <Guidance band={band} />

            {savedId && (
              <p className="saved-note">
                <CloudOff size={13} /> {t('savedOffline')}
              </p>
            )}

            {/* ACTIONS */}
            <div className="report-actions">
              <button className="download-button" onClick={downloadPDF}>
                <FileDown size={16} /> {t('downloadPDF')}
              </button>
              <button className="download-button" onClick={downloadCSV}>
                <Table size={16} /> {t('downloadCSV')}
              </button>
            </div>

            <p className="disclaimer">
              <AlertTriangle size={14} style={{verticalAlign:'-2px', marginRight:4}} />
              {t('disclaimer')}
            </p>
          </section>
        )}

        </>)}

        {view === 'home' && (
          <>
            <Dashboard />
            <WhyNER />
          </>
        )}

      </main>

      <footer>
        <p>KOA Screener &mdash; AI-assisted research tool. Not a substitute for medical advice.</p>
      </footer>

    </div>
  )
}

export default App
