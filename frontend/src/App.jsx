
import { useState } from 'react'
import './App.css'

function App() {
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [videoUrl, setVideoUrl] = useState(null)

  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleVideoChange = (event) => {
    const file = event.target.files[0]

    if (file) {
      setSelectedVideo(file)
      setVideoUrl(URL.createObjectURL(file))
      setResult(null)
      setError(null)
    }
  }

  const handleAnalyze = async () => {
    if (!selectedVideo) return

    setAnalyzing(true)
    setResult(null)
    setError(null)

    const formData = new FormData()
    formData.append('video', selectedVideo)

    try {
      console.log('📤 Sending video to backend...')

      const response = await fetch(
        'http://127.0.0.1:8000/extract-pose',
        {
          method: 'POST',
          body: formData
        }
      )

      console.log('📥 Backend response:', response.status)

      const data = await response.json()

      console.log('📊 Result:', data)

      if (!response.ok || !data.success) {
        throw new Error(
          data.error || 'Video analysis failed'
        )
      }

      setResult(data)

    } catch (err) {
      console.error('❌ Analysis error:', err)

      setError(
        err.message ||
        'Could not connect to the backend.'
      )

    } finally {
      setAnalyzing(false)
    }
  }
  const downloadPDF = async () => {
    if (!result) return

    try {
      console.log('📄 Generating PDF...')

      const response = await fetch(
        'http://127.0.0.1:8000/generate-report',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(result),
        }
      )

      console.log('📥 PDF response:', response.status)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(
          errorData.detail || 'PDF generation failed'
        )
      }

      const blob = await response.blob()

      const url = window.URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = url
      link.download = 'OA_Screening_Report.pdf'

      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      window.URL.revokeObjectURL(url)

      console.log('✅ PDF downloaded successfully')

    } catch (err) {
      console.error('❌ PDF error:', err)

      setError(
        err.message || 'Could not generate PDF report.'
      )
    }
  }
  const downloadCSV = () => {
    if (!result) return

    const prediction = result.prediction

    let csv = 'OA Risk Analysis Report\n\n'

    csv += 'Risk Score,' +
      `${(prediction.risk * 100).toFixed(1)}%\n`

    csv += 'Risk Band,' +
      `${prediction.band}\n`

    if (prediction.stage) {
      csv += 'Severity Grade,' +
        `${prediction.stage.grade}\n`

      csv += 'Confidence,' +
        `"${prediction.stage.confidence}"\n`
    }

    csv += '\nGait Measurements\n'
    csv += 'Measurement,Value,Unit,Reading\n'

    if (prediction.measurements) {
      prediction.measurements.forEach((measurement) => {
        csv += `"${measurement.label}",`
        csv += `"${measurement.value}",`
        csv += `"${measurement.unit}",`
        csv += `"${measurement.reading}"\n`
      })
    }

    csv += '\nAnalysis Information\n'
    csv += `Frames Processed,${result.frames_processed}\n`
    csv += `Frames Detected,${result.frames_detected}\n`

    csv += '\nDisclaimer\n'
    csv += '"AI-assisted screening result. Not a medical diagnosis."\n'

    const blob = new Blob(
      [csv],
      { type: 'text/csv;charset=utf-8;' }
    )

    const url = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = url
    link.download = 'OA_Analysis_Report.csv'

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    URL.revokeObjectURL(url)
  }

  return (
    <div className="app">

      <header className="header">

        <div className="logo">

          <div className="logo-icon">
            OA
          </div>

          <div>
            <h2>OA Risk AI</h2>
            <p>Early Detection System</p>
          </div>

        </div>

        <div className="header-text">
          AI-Assisted Osteoarthritis Risk Screening
        </div>

      </header>


      <main className="main-content">

        <section className="hero-section">

          <span className="badge">
            AI-POWERED GAIT ANALYSIS
          </span>

          <h1>
            Early Detection of
            <span> Osteoarthritis Risk</span>
          </h1>

          <p className="subtitle">
            Upload a walking video to analyze gait patterns,
            extract movement features, and estimate
            osteoarthritis risk.
          </p>

        </section>


        <section className="upload-card">

          <h2>
            Upload Walking Video
          </h2>

          <p>
            Upload a clear video of a person walking
            for AI-based gait analysis.
          </p>


          {!selectedVideo ? (

            <label className="upload-area">

              <input
                type="file"
                accept="video/*"
                onChange={handleVideoChange}
              />

              <div className="upload-icon">
                🎥
              </div>

              <h3>
                Drag and drop your video here
              </h3>

              <p>
                or click to browse files
              </p>

              <span className="file-types">
                Supported formats: MP4, MOV, AVI
              </span>

            </label>

          ) : (

            <div className="video-section">

              <video
                className="video-preview"
                controls
                src={videoUrl}
              >
                Your browser does not support
                video playback.
              </video>


              <div className="file-info">

                <h3>
                  {selectedVideo.name}
                </h3>

                <p>
                  Size:{' '}
                  {(selectedVideo.size / (1024 * 1024))
                    .toFixed(2)} MB
                </p>


                <label className="change-video">

                  Change Video

                  <input
                    type="file"
                    accept="video/*"
                    onChange={handleVideoChange}
                  />

                </label>

              </div>

            </div>

          )}


          <button
            className="analyze-button"
            disabled={!selectedVideo || analyzing}
            onClick={handleAnalyze}
          >

            {analyzing
              ? 'Analyzing... Please wait'
              : 'Analyze Video'}

          </button>


          {error && (

            <div className="error-message">
              ❌ {error}
            </div>

          )}

        </section>


        {result && result.prediction && (

          <section className="results-card">

            <div className="report-header">

              <span className="badge">
                ANALYSIS COMPLETE
              </span>

              <h2>
                OA Risk Analysis Report
              </h2>

              <p>
                Generated from gait analysis of the
                uploaded walking video.
              </p>

            </div>


            <div className="result-main">

              <h3>
                OA Risk Score
              </h3>

              <div className="risk-score">

                {(
                  result.prediction.risk * 100
                ).toFixed(1)}%

              </div>

              <p>
                Risk band:{' '}
                <strong>
                  {result.prediction.band}
                </strong>
              </p>

            </div>


            {result.prediction.stage && (

              <div className="stage-result">

                <h3>
                  Severity
                </h3>

                <p>
                  Grade:{' '}
                  <strong>
                    {result.prediction.stage.grade}
                  </strong>
                </p>

                <p>
                  Confidence:{' '}
                  {result.prediction.stage.confidence}
                </p>

              </div>

            )}


            <div className="measurements">

              <h3>
                Gait Measurements
              </h3>

              {result.prediction.measurements?.map(
                (measurement, index) => (

                  <div
                    className="measurement"
                    key={index}
                  >

                    <div>
                      <strong>
                        {measurement.label}
                      </strong>

                      <p>
                        {measurement.reading}
                      </p>
                    </div>

                    <span>
                      {measurement.value}{' '}
                      {measurement.unit}
                    </span>

                  </div>

                )
              )}

            </div>


            <div className="analysis-info">

              <h3>
                Analysis Information
              </h3>

              <p>
                <strong>
                  Frames processed:
                </strong>{' '}
                {result.frames_processed}
              </p>

              <p>
                <strong>
                  Frames detected:
                </strong>{' '}
                {result.frames_detected}
              </p>

              <p>
                <strong>
                  Pose extraction:
                </strong>{' '}
                Completed
              </p>

              <p>
                <strong>
                  KOA prediction:
                </strong>{' '}
                Completed
              </p>

            </div>


            <div className="report-actions">


              <button
                className="download-button"
                onClick={downloadPDF}
                disabled={!result}
              >
                📄 Download PDF
              </button>

            </div>


            <p className="disclaimer">

              This is an AI-assisted screening result,
              not a medical diagnosis.

            </p>

          </section>

        )}


        <section className="steps-section">

          <div className="step">

            <div className="step-number">
              1
            </div>

            <h3>
              Upload
            </h3>

            <p>
              Upload a person's walking video.
            </p>

          </div>


          <div className="step">

            <div className="step-number">
              2
            </div>

            <h3>
              Analyze
            </h3>

            <p>
              AI extracts gait and movement features.
            </p>

          </div>


          <div className="step">

            <div className="step-number">
              3
            </div>

            <h3>
              Predict
            </h3>

            <p>
              Receive an estimated OA risk score.
            </p>

          </div>


          <div className="step">

            <div className="step-number">
              4
            </div>

            <h3>
              Report
            </h3>

            <p>
              Download the analysis report.
            </p>

          </div>

        </section>

      </main>


      <footer>

        <p>
          AI-assisted screening tool for research purposes.
          Not a medical diagnosis.
        </p>

      </footer>

    </div>
  )
}

export default App

