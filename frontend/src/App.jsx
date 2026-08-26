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

            <h2>
              Analysis Result
            </h2>

            <div className="result-main">

              <h3>
                Risk Score
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
                  Stage
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

                    <strong>
                      {measurement.label}
                    </strong>

                    <span>
                      {measurement.value}{' '}
                      {measurement.unit}
                    </span>

                    <p>
                      {measurement.reading}
                    </p>

                  </div>

                )
              )}

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
              Result
            </h3>

            <p>
              View the generated analysis.
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