const PRESETS = [
  { id: 'tiny_ui', label: 'Tiny UI Element', faces: 8000, range: '1K - 10K', notes: 'icons / floating shapes' },
  { id: 'decorative_bg', label: 'Decorative Background', faces: 25000, range: '10K - 30K', notes: 'repeatable background models' },
  { id: 'hero_standard', label: 'Hero Section', faces: 70000, range: '20K - 100K', notes: 'single focus object' },
  { id: 'interactive_model', label: 'Interactive Model', faces: 100000, range: '40K - 140K', notes: 'rotation / hover interactions' },
  { id: 'multi_scene', label: 'Multiple Models Scene', faces: 220000, range: '100K - 300K', notes: 'total scene budget' },
  { id: 'mobile_hero', label: 'Mobile Hero', faces: 45000, range: '20K - 60K', notes: 'performance priority' },
]

export default function PresetSelector({
  selectedPreset,
  onPresetChange,
  targetFaces,
  onTargetChange,
  preserveNormals,
  onNormalsChange,
  preserveBoundaries,
  onBoundariesChange,
  reoptimizeFromLatest,
  onReoptimizeFromLatestChange,
  performanceMode,
  onPerformanceModeChange,
  strictQuality,
  onStrictQualityChange,
  maxDeviationPercent,
  onMaxDeviationChange,
  maxFaces,
  onOptimize,
  canOptimize,
  processing,
}) {
  return (
    <div className="sidebar">
      <div className="card">
        <h3>Target Platform</h3>

        <div className="preset-grid">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              className={`preset-btn ${selectedPreset === p.id ? 'active' : ''}`}
              onClick={() => {
                onPresetChange(p.id)
                onTargetChange(p.faces)
              }}
            >
              <span className="label">{p.label}</span>
              <span className="count">{p.faces.toLocaleString()} faces</span>
              <span className="count">Guide: {p.range}</span>
              <span className="count">{p.notes}</span>
            </button>
          ))}
        </div>

        <div className="slider-group">
          <label>
            Custom Target
            <span>{targetFaces.toLocaleString()} faces</span>
          </label>
          <input
            type="range"
            min={Math.min(4, maxFaces || 4)}
            max={maxFaces || 500000}
            step={1}
            value={targetFaces}
            onChange={(e) => {
              onTargetChange(Number(e.target.value))
              onPresetChange(null)
            }}
          />
        </div>
      </div>

      <div className="card">
        <h3>Options</h3>
        <div className="toggle-row">
          <span>Preserve Normals</span>
          <label className="toggle">
            <input type="checkbox" checked={preserveNormals} onChange={(e) => onNormalsChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>
        <div className="toggle-row">
          <span>Preserve Boundaries</span>
          <label className="toggle">
            <input type="checkbox" checked={preserveBoundaries} onChange={(e) => onBoundariesChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>Re-modify From Last Output</span>
          <label className="toggle">
            <input type="checkbox" checked={reoptimizeFromLatest} onChange={(e) => onReoptimizeFromLatestChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>FPS Performance Mode</span>
          <label className="toggle">
            <input type="checkbox" checked={performanceMode} onChange={(e) => onPerformanceModeChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>Strict Quality Lock</span>
          <label className="toggle">
            <input type="checkbox" checked={strictQuality} onChange={(e) => onStrictQualityChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        {strictQuality && (
          <div className="slider-group">
            <label>
              Max Shape Deviation (diag %)
              <span>{maxDeviationPercent.toFixed(2)}%</span>
            </label>
            <input
              type="range"
              min={0.5}
              max={8.0}
              step={0.05}
              value={maxDeviationPercent}
              onChange={(e) => onMaxDeviationChange(Number(e.target.value))}
            />
          </div>
        )}

        <div style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.4 }}>
          Performance limits: Safe {'<'} 50K faces, Moderate 50K-150K, Heavy 150K-500K, Avoid {'>'} 500K for landing pages.
        </div>
      </div>

      <button
        className="optimize-btn"
        onClick={onOptimize}
        disabled={!canOptimize || processing}
      >
        {processing ? 'Processing...' : 'Optimize Mesh'}
      </button>
    </div>
  )
}
