import { useEffect, useState } from 'react'
import FileUpload from './components/FileUpload'
import ModelViewer from './components/ModelViewer'
import PresetSelector from './components/PresetSelector'
import StatsPanel from './components/StatsPanel'
import Navbar from './components/Navbar'
import {
  optimizeMesh,
  downloadResult,
  getDownloadUrl,
  getPreviewUrl,
} from './api/client'

export default function DemoApp() {
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('optimesh-theme')
    if (saved === 'dark') return true
    if (saved === 'light') return false
    return prefersDark
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light')
    localStorage.setItem('optimesh-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  // Upload state
  const [jobId, setJobId] = useState(null)
  const [filename, setFilename] = useState(null)
  const [originalStats, setOriginalStats] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)

  // Optimization config
  const [selectedPreset, setSelectedPreset] = useState('hero_standard')
  const [targetFaces, setTargetFaces] = useState(70000)
  const [preserveNormals, setPreserveNormals] = useState(true)
  const [preserveBoundaries, setPreserveBoundaries] = useState(true)
  const [reoptimizeFromLatest, setReoptimizeFromLatest] = useState(true)
  const [performanceMode, setPerformanceMode] = useState(true)
  const [strictQuality, setStrictQuality] = useState(true)
  const [maxDeviationPercent, setMaxDeviationPercent] = useState(2.0)

  // Result state
  const [processing, setProcessing] = useState(false)
  const [stage, setStage] = useState('')
  const [optimizedStats, setOptimizedStats] = useState(null)
  const [optimizedUrl, setOptimizedUrl] = useState(null)
  const [optimizedFilename, setOptimizedFilename] = useState(null)
  const [processingTime, setProcessingTime] = useState(null)
  const [qualityMeta, setQualityMeta] = useState(null)
  const [hasImportanceMap, setHasImportanceMap] = useState(false)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => () => {
    if (originalUrl) URL.revokeObjectURL(originalUrl)
  }, [originalUrl])

  async function handleDownload() {
    if (!jobId || downloading) return
    setDownloading(true)
    try {
      const response = await downloadResult(jobId)
      const contentType = response.headers['content-type'] || ''
      const disposition = response.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^";]+)"?/)
      const filename =
        match?.[1] ||
        optimizedFilename ||
        (contentType.includes('zip') ? `optimesh_${jobId}.zip` : `optimesh_${jobId}.obj`)

      // Trigger the browser download from the blob
      const url = URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = decodeURIComponent(filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      setTimeout(() => URL.revokeObjectURL(url), 5000)

    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Download failed'
      throw new Error(msg)
    } finally {
      setDownloading(false)
    }
  }

  function handleUploadComplete(result, file) {
    setJobId(result.job_id)
    setFilename(result.filename)
    setOriginalStats(result.original_stats)
    setOriginalUrl(URL.createObjectURL(file))
    // Reset results
    setOptimizedStats(null)
    setOptimizedUrl(null)
    setQualityMeta(null)
    setHasImportanceMap(false)
    setError(null)

    // Set slider max to original face count
    if (targetFaces > result.original_stats.face_count) {
      setTargetFaces(Math.max(4, Math.floor(result.original_stats.face_count * 0.5)))
      setSelectedPreset(null)
    }

  }

  async function handleOptimize() {
    if (!jobId) return
    setProcessing(true)
    setStage('Starting optimization...')
    setError(null)

    try {
      const result = await optimizeMesh({
        jobId,
        targetFaces,
        preset: selectedPreset,
        preserveNormals,
        preserveBoundaries,
        reoptimizeFromLatest,
        strictQuality,
        maxDeviationPercent,
      })

      setOptimizedStats(result.optimized_stats)
      setProcessingTime(result.processing_time_seconds)
      setOptimizedFilename(result.optimized_filename)
      setHasImportanceMap(result.has_importance_map)
      setQualityMeta({
        strictQuality,
        targetRequested: targetFaces,
        targetUsed: result.target_faces_used ?? result.optimized_stats?.face_count,
        deviationPercent: result.quality_deviation_percent,
        guardRelaxed: result.quality_guard_relaxed,
        guardSatisfied: result.quality_guard_satisfied,
      })

      // Use dedicated preview endpoint so renderer always gets a direct mesh file.
      setOptimizedUrl(getPreviewUrl(jobId))
      setStage('Complete')

    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Optimization failed'
      setError(msg)
    } finally {
      setProcessing(false)
    }
  }

  function handleReset() {
    setJobId(null)
    setFilename(null)
    setOriginalStats(null)
    setOriginalUrl(null)
    setOptimizedStats(null)
    setOptimizedUrl(null)
    setOptimizedFilename(null)
    setProcessingTime(null)
    setQualityMeta(null)
    setHasImportanceMap(false)
    setError(null)
  }

  return (
    <div className="app">
      <Navbar />

      <header className="header">
        <div>
          <h1>Crunch3D</h1>
          <p>Local 3D Mesh Optimization</p>
        </div>
        <div className="header-actions">
          <button
            className={`viewer-btn ${darkMode ? 'active' : ''}`}
            onClick={() => setDarkMode((v) => !v)}
            aria-label="Toggle theme"
          >
            {darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
          {jobId && (
            <button className="viewer-btn" onClick={handleReset}>
              New Upload
            </button>
          )}
        </div>
      </header>

      {!jobId ? (
        <FileUpload onUploadComplete={handleUploadComplete} disabled={processing} />
      ) : (
        <div className="main-layout">
          <PresetSelector
            selectedPreset={selectedPreset}
            onPresetChange={setSelectedPreset}
            targetFaces={targetFaces}
            onTargetChange={setTargetFaces}
            preserveNormals={preserveNormals}
            onNormalsChange={setPreserveNormals}
            preserveBoundaries={preserveBoundaries}
            onBoundariesChange={setPreserveBoundaries}
            reoptimizeFromLatest={reoptimizeFromLatest}
            onReoptimizeFromLatestChange={setReoptimizeFromLatest}
            performanceMode={performanceMode}
            onPerformanceModeChange={setPerformanceMode}
            strictQuality={strictQuality}
            onStrictQualityChange={setStrictQuality}
            maxDeviationPercent={maxDeviationPercent}
            onMaxDeviationChange={setMaxDeviationPercent}
            maxFaces={originalStats?.face_count || 500000}
            onOptimize={handleOptimize}
            canOptimize={!!jobId && !processing}
            processing={processing}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <ModelViewer
              originalUrl={originalUrl}
              optimizedUrl={optimizedUrl}
              filename={filename}
              optimizedFilename={optimizedFilename}
              originalStats={originalStats}
              optimizedStats={optimizedStats}
              darkMode={darkMode}
              processing={processing}
              stage={stage}
              performanceMode={performanceMode}
              hasImportanceMap={hasImportanceMap}
              jobId={jobId}
            />

            {error && <div className="error-msg">{error}</div>}

            <StatsPanel
              original={originalStats}
              optimized={optimizedStats}
              processingTime={processingTime}
              qualityMeta={qualityMeta}
              downloadUrl={optimizedStats ? getDownloadUrl(jobId) : null}
              onDownload={handleDownload}
              downloading={downloading}
            />
          </div>
        </div>
      )}

      <footer className="app-footer">
        <p>© 2026 Crunch3d. Open-source 3D optimization.</p>
        <div className="app-footer-links">
          <a href="https://github.com/Lesgo-HQ/Crunch3D">GitHub</a>
        </div>
      </footer>
    </div>
  )
}
