import { useState } from 'react'

export default function StatsPanel({
  original,
  optimized,
  processingTime,
  qualityMeta,
  downloadUrl,
  onDownload,
  downloading,
}) {
  const [error, setError] = useState(null)

  if (!original) return null

  const reductionPercent =
    optimized && original.face_count > 0
      ? Math.round((1 - optimized.face_count / original.face_count) * 100)
      : null

  const sizeReductionPercent =
    optimized && original.file_size_mb > 0
      ? Math.round((1 - optimized.file_size_mb / original.file_size_mb) * 100)
      : null

  const handleDownload = async () => {
    setError(null)
    try {
      await onDownload()
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Download failed'
      setError(msg)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="stats-grid">
        <div className="stat-item">
          <div className="label">Original Faces</div>
          <div className="value">{original.face_count.toLocaleString()}</div>
          <div className="sub">{original.vertex_count.toLocaleString()} vertices</div>
        </div>

        {optimized && (
          <>
            <div className="stat-item">
              <div className="label">Optimized Faces</div>
              <div className="value accent">{optimized.face_count.toLocaleString()}</div>
              <div className="sub">{optimized.vertex_count.toLocaleString()} vertices</div>
            </div>

            <div className="stat-item">
              <div className="label">Reduction</div>
              <div className="value success">{reductionPercent !== null ? `${reductionPercent}%` : '-'}</div>
              <div className="sub">polygons removed</div>
            </div>

            <div className="stat-item">
              <div className="label">File Size</div>
              <div className="value">
                {original.file_size_mb}MB {'->'} {optimized.file_size_mb}MB
              </div>
              <div className="sub">
                {sizeReductionPercent !== null ? (
                  sizeReductionPercent >= 0 
                    ? `${sizeReductionPercent}% smaller` 
                    : `${Math.abs(sizeReductionPercent)}% larger`
                ) : '-'}
              </div>
            </div>

            {processingTime && (
              <div className="stat-item">
                <div className="label">Processing Time</div>
                <div className="value">{processingTime}s</div>
              </div>
            )}
          </>
        )}

        {!optimized && (
          <>
            <div className="stat-item">
              <div className="label">File Size</div>
              <div className="value">{original.file_size_mb} MB</div>
            </div>
            <div className="stat-item">
              <div className="label">UVs</div>
              <div className="value">{original.has_uvs ? 'Yes' : 'No'}</div>
            </div>
            <div className="stat-item">
              <div className="label">Normals</div>
              <div className="value">{original.has_normals ? 'Yes' : 'No'}</div>
            </div>
          </>
        )}
      </div>

      {optimized && qualityMeta?.strictQuality && (
        <div className="card">
          <h3>Quality Lock Report</h3>
          <div style={{ display: 'grid', gap: 8, fontSize: 13 }}>
            <div>
              Target Faces: {qualityMeta.targetRequested?.toLocaleString?.() || '-'}
            </div>
            <div>
              Used Faces: {qualityMeta.targetUsed?.toLocaleString?.() || '-'}
            </div>
            <div>
              Surface Deviation: {qualityMeta.deviationPercent != null ? `${qualityMeta.deviationPercent}%` : 'Not available for this file'}
            </div>
            <div style={{ color: qualityMeta.guardSatisfied ? 'var(--success)' : 'var(--danger)' }}>
              {qualityMeta.guardSatisfied
                ? 'Structure protection: Passed'
                : 'Structure protection: Requested reduction was too aggressive'}
            </div>
            {qualityMeta.guardRelaxed && (
              <div style={{ color: 'var(--text-secondary)' }}>
                Quality lock increased face count above requested target to preserve model structure.
              </div>
            )}
          </div>
        </div>
      )}

      {downloadUrl && (
        <div className="download-bar">
          <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            Optimization complete - ready to download
          </span>
          <button
            className="download-btn"
            onClick={handleDownload}
            disabled={downloading}
            style={{ border: 'none', cursor: downloading ? 'progress' : 'pointer' }}
          >
            {downloading ? 'Downloading...' : 'Download Result'}
          </button>
          {error && <div className="error-msg" style={{ width: '100%' }}>{error}</div>}
        </div>
      )}
    </div>
  )
}