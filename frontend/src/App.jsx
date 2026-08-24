import { useState } from 'react'
import './App.css'

function App() {
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [videoUrl, setVideoUrl] = useState(null)

  const handleVideoChange = (event) => {
    const file = event.target.files[0]

    if (file) {
      setSelectedVideo(file)
      setVideoUrl(URL.createObjectURL(file))
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <div className="logo-icon">OA</div>
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
          <span className="badge">AI-POWERED GAIT ANALYSIS</span>

          <h1>
            Early Detection of
            <span> Osteoarthritis Risk</span>
          </h1>

          <p className="subtitle">
            Upload a walking video to analyze gait patterns, extract movement
            features, and estimate the probability of Osteoarthritis risk.
          </p>
        </section>

        <section className="upload-card">
          <h2>Upload Walking Video</h2>
          <p>
            Upload a clear video of a person walking for AI-based gait analysis.
          </p>

          {!selectedVideo ? (
            <label className="upload-area">
              <input
                type="file"
                accept="video/*"
                onChange={handleVideoChange}
              />

              <div className="upload-icon">🎥</div>
              <h3>Drag and drop your video here</h3>
              <p>or click to browse files</p>

              <span className="file-types">
                Supported formats: MP4, MOV, AVI
              </span>
            </label>
          ) : (
            <div className="video-section">
              <video className="video-preview" controls src={videoUrl}>
                Your browser does not support video playback.
              </video>

              <div className="file-info">
                <h3>{selectedVideo.name}</h3>
                <p>
                  Size: {(selectedVideo.size / (1024 * 1024)).toFixed(2)} MB
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
            disabled={!selectedVideo}
          >
            Analyze Video
          </button>
        </section>

        <section className="steps-section">
          <div className="step">
            <div className="step-number">1</div>
            <h3>Upload</h3>
            <p>Upload a person's walking video.</p>
          </div>

          <div className="step">
            <div className="step-number">2</div>
            <h3>Analyze</h3>
            <p>AI extracts gait and movement features.</p>
          </div>

          <div className="step">
            <div className="step-number">3</div>
            <h3>Predict</h3>
            <p>Receive an OA probability from 0 to 1.</p>
          </div>

          <div className="step">
            <div className="step-number">4</div>
            <h3>Download</h3>
            <p>Download the generated gait features CSV.</p>
          </div>
        </section>
      </main>

      <footer>
        <p>
          AI-assisted screening tool for research purposes. Not a medical diagnosis.
        </p>
      </footer>
    </div>
  )
}

export default App