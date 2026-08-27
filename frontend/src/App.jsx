import { useState, useEffect } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/* ---------- Background: moving waves + subtle pulse rings ---------- */
const BgCanvas = () => (
  <div className="bg-canvas" aria-hidden="true">
    <div className="bg-grid" />

    {/* Pulse rings — top-left corner, very subtle */}
    <div className="pulse-ring pulse-ring-1" />
    <div className="pulse-ring pulse-ring-2" />
    <div className="pulse-ring pulse-ring-3" />

    {/*
      Each wave is a <use> of an oversized tiling path (2× viewport width).
      SMIL <animateTransform> slides it left by exactly half its width so
      the seam is invisible — this works in every modern browser.
    */}

    {/* Wave 1 — slowest, deepest */}
    <svg className="wave-layer" style={{bottom:'0',height:'38vh'}} viewBox="0 0 2880 320" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wv1g" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="var(--primary)"  stopOpacity="0.28"/>
          <stop offset="50%"  stopColor="var(--accent-1)" stopOpacity="0.22"/>
          <stop offset="100%" stopColor="var(--accent-2)" stopOpacity="0.28"/>
        </linearGradient>
      </defs>
      <path d="M0,160 C360,80 720,240 1080,160 C1440,80 1800,240 2160,160 C2520,80 2700,200 2880,160 L2880,320 L0,320 Z" fill="url(#wv1g)">
        <animateTransform attributeName="transform" type="translate" from="0,0" to="-1440,0" dur="18s" repeatCount="indefinite"/>
      </path>
    </svg>

    {/* Wave 2 — medium, offset phase */}
    <svg className="wave-layer" style={{bottom:'0',height:'28vh'}} viewBox="0 0 2880 260" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wv2g" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="var(--accent-2)" stopOpacity="0.22"/>
          <stop offset="50%"  stopColor="var(--primary)"  stopOpacity="0.18"/>
          <stop offset="100%" stopColor="var(--accent-1)" stopOpacity="0.22"/>
        </linearGradient>
      </defs>
      <path d="M0,130 C480,40 960,220 1440,130 C1920,40 2400,200 2880,130 L2880,260 L0,260 Z" fill="url(#wv2g)">
        <animateTransform attributeName="transform" type="translate" from="-1440,0" to="0,0" dur="12s" repeatCount="indefinite"/>
      </path>
    </svg>

    {/* Wave 3 — fastest, thinnest, closest to bottom */}
    <svg className="wave-layer" style={{bottom:'0',height:'18vh'}} viewBox="0 0 2880 200" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wv3g" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="var(--accent-1)" stopOpacity="0.20"/>
          <stop offset="50%"  stopColor="var(--accent-2)" stopOpacity="0.16"/>
          <stop offset="100%" stopColor="var(--primary)"  stopOpacity="0.20"/>
        </linearGradient>
      </defs>
      <path d="M0,100 C240,40 480,160 720,100 C960,40 1200,150 1440,100 C1680,50 1920,150 2160,100 C2400,50 2640,140 2880,100 L2880,200 L0,200 Z" fill="url(#wv3g)">
        <animateTransform attributeName="transform" type="translate" from="0,0" to="-1440,0" dur="8s" repeatCount="indefinite"/>
      </path>
    </svg>

    {/* Wave 4 — top edge, very faint header accent */}
    <svg className="wave-layer" style={{top:'0',height:'14vh'}} viewBox="0 0 2880 160" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M0,80 C360,130 720,30 1080,80 C1440,130 1800,30 2160,80 C2520,130 2700,50 2880,80 L2880,0 L0,0 Z" fill="var(--primary)" fillOpacity="0.08">
        <animateTransform attributeName="transform" type="translate" from="-1440,0" to="0,0" dur="22s" repeatCount="indefinite"/>
      </path>
    </svg>

    <div className="scanlines" />
  </div>
)

function App() {
  const [theme, setTheme] = useState('light')
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [videoUrl, setVideoUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  /* sync theme attribute */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light')

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
    setAnalyzing(true); setResult(null); setError(null)
    const formData = new FormData()
    formData.append('video', selectedVideo)
    try {
      const response = await fetch(`${API_URL}/extract-pose`, { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok || !data.success) throw new Error(data.error || 'Video analysis failed')
      setResult(data)
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
        body: JSON.stringify(result),
      })
      if (!response.ok) { const e = await response.json(); throw new Error(e.detail || 'PDF generation failed') }
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

  const band = result?.prediction?.band ?? 'low'

  return (
    <div className="app">

      {/* ---- ANIMATED BACKGROUND ---- */}
      <BgCanvas />

      {/* ---- HEADER ---- */}
      <header className="header">
        <div className="logo">
          <div className="logo-icon">OA</div>
          <div className="logo-text">
            <h2>OA Risk AI</h2>
            <p>Gait Analysis System</p>
          </div>
        </div>

        <div className="header-right">
          <span className="header-text">AI-Powered KOA Screening</span>
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
            <div className="theme-toggle-knob">
              {theme === 'light' ? '☀️' : '🌙'}
            </div>
          </button>
        </div>
      </header>

      {/* ---- MAIN ---- */}
      <main className="main-content">

        {/* HERO */}
        <section className="hero-section">
          <div className="badge">
            <span className="badge-dot" />
            AI-Powered Gait Analysis
          </div>
          <h1>
            Detect <span className="grad-text">Osteoarthritis Risk</span><br />
            from a Walking Video
          </h1>
          <p className="subtitle">
            Upload a short walking video and our AI analyzes gait patterns,
            extracts biomechanical features, and estimates your knee OA risk — in seconds.
          </p>
        </section>

        {/* UPLOAD CARD */}
        <section className="glass-card upload-card">

          {!selectedVideo ? (
            <label className="upload-area">
              <input type="file" accept="video/*" onChange={handleVideoChange} style={{ display: 'none' }} />
              <div className="upload-icon">🎥</div>
              <h3>Drop your video here</h3>
              <p>or click to browse files — max 50 MB</p>
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
                  ↺ Change Video
                  <input type="file" accept="video/*" onChange={handleVideoChange} />
                </label>
              </div>
            </div>
          )}

          <button
            className="analyze-button"
            disabled={!selectedVideo || analyzing}
            onClick={handleAnalyze}
          >
            {analyzing ? (
              <><div className="spinner" /> Analyzing gait patterns…</>
            ) : (
              '⚡ Analyze Video'
            )}
          </button>

          {error && (
            <div className="error-message">
              ❌ {error}
            </div>
          )}
        </section>

        {/* RESULTS */}
        {result && result.prediction && (
          <section className={`glass-card results-card risk-${band}`}>

            <div className="report-header">
              <span className="badge"><span className="badge-dot" />Analysis Complete</span>
              <h2>OA Risk Analysis Report</h2>
              <p>Generated from gait analysis · {result.frames_detected} of {result.frames_processed} frames with pose detected</p>
            </div>

            {/* METRICS */}
            <div className="dashboard-grid">

              <div className={`metric-card risk-${band}`}>
                <h3>OA Risk Score</h3>
                <div className="risk-ring-wrap">
                  <div className="risk-circle">
                    {(result.prediction.risk * 100).toFixed(1)}%
                  </div>
                </div>
                <span className="risk-band">{band}</span>
              </div>

              {result.prediction.stage && (
                <div className="metric-card">
                  <h3>Severity Grade</h3>
                  <div className="severity-grade">{result.prediction.stage.grade}</div>
                  <p className="severity-conf">{result.prediction.stage.confidence}</p>
                </div>
              )}
            </div>

            {/* MEASUREMENTS */}
            {result.prediction.measurements?.length > 0 && (
              <div className="measurements">
                <h3>Gait Measurements</h3>
                <div className="measurement-grid">
                  {result.prediction.measurements.map((m, i) => (
                    <div className="measurement" key={i}>
                      <div className="measurement-header">
                        <span className="measurement-label">{m.label}</span>
                        <span className="measurement-value">{m.value} {m.unit}</span>
                      </div>
                      <div className="measurement-reading">{m.reading}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ACTIONS */}
            <div className="report-actions">
              <button className="download-button" onClick={downloadPDF}>
                📄 Download PDF
              </button>
              <button className="download-button" onClick={downloadCSV}>
                📊 Download CSV
              </button>
            </div>

            <p className="disclaimer">
              ⚠️ AI-assisted screening only. Not a medical diagnosis. Consult a qualified physician.
            </p>
          </section>
        )}

        {/* HOW IT WORKS */}
        <section className="steps-section">
          {[
            { n:1, title:'Upload', desc:'Drop or select a clear side-view walking video of the patient.' },
            { n:2, title:'Extract', desc:'MediaPipe extracts 3D pose landmarks from every frame of the video.' },
            { n:3, title:'Predict', desc:'AI computes biomechanical features and runs the KOA risk model.' },
            { n:4, title:'Report', desc:'Download a detailed PDF or CSV report with measurements.' },
          ].map(s => (
            <div className="step" key={s.n}>
              <div className="step-number">{s.n}</div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </section>

      </main>

      <footer>
        <p>KOA Screener &mdash; AI-assisted research tool. Not a substitute for medical advice.</p>
      </footer>

    </div>
  )
}

export default App
