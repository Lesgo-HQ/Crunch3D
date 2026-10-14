import { useMemo } from 'react'

function formatNumber(value, fractionDigits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-'
  }
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: fractionDigits })
}

export default function ModelInspector({
  modelSummary,
  fileStats,
  camera,
  mode,
  currentFilename,
  darkMode,
}) {
  const rows = useMemo(() => {
    const stats = fileStats || {}
    const bbox = stats.bounding_box || null
    return {
      objectType: modelSummary?.type || 'Mesh',
      meshCount: modelSummary?.meshCount ?? 0,
      materialCount: modelSummary?.materialCount ?? 0,
      vertexCount: stats.vertex_count ?? modelSummary?.vertexCount ?? 0,
      faceCount: stats.face_count ?? modelSummary?.faceCount ?? 0,
      hasNormals: stats.has_normals ?? modelSummary?.hasNormals ?? false,
      hasUVs: stats.has_uvs ?? modelSummary?.hasUVs ?? false,
      diagonal: bbox?.diagonal,
      min: bbox?.min,
      max: bbox?.max,
      fileSize: stats.file_size_mb,
      position: modelSummary?.position,
      rotation: modelSummary?.rotation,
      scale: modelSummary?.scale,
      cameraPosition: camera?.position,
      cameraFov: camera?.fov,
      cameraNear: camera?.near,
      cameraFar: camera?.far,
    }
  }, [modelSummary, fileStats, camera])

  return (
    <aside className="inspector">
      <div className="inspector-header">
        <div>
          <h3>Scene</h3>
          <p>{currentFilename || 'No file selected'}</p>
        </div>
        <span className="tag">{mode}</span>
      </div>

      <div className="inspector-section">
        <h4>Object</h4>
        <div className="kv-grid">
          <div className="kv-key">Type</div>
          <div className="kv-val">{rows.objectType}</div>

          <div className="kv-key">Meshes</div>
          <div className="kv-val">{formatNumber(rows.meshCount, 0)}</div>

          <div className="kv-key">Materials</div>
          <div className="kv-val">{formatNumber(rows.materialCount, 0)}</div>

          <div className="kv-key">Vertices</div>
          <div className="kv-val">{formatNumber(rows.vertexCount, 0)}</div>

          <div className="kv-key">Faces</div>
          <div className="kv-val">{formatNumber(rows.faceCount, 0)}</div>

          <div className="kv-key">Normals</div>
          <div className="kv-val">{rows.hasNormals ? 'Yes' : 'No'}</div>

          <div className="kv-key">UVs</div>
          <div className="kv-val">{rows.hasUVs ? 'Yes' : 'No'}</div>

          <div className="kv-key">File Size</div>
          <div className="kv-val">{rows.fileSize ? `${formatNumber(rows.fileSize)} MB` : '-'}</div>
        </div>
      </div>

      <div className="inspector-section">
        <h4>Scene Graph</h4>
        <div className="graph-list">
          {Array.isArray(modelSummary?.meshNames) && modelSummary.meshNames.length > 0 ? (
            modelSummary.meshNames.slice(0, 8).map((name, idx) => (
              <div key={`${name}-${idx}`} className="graph-item">{name}</div>
            ))
          ) : (
            <div className="graph-item muted">No nodes detected</div>
          )}
        </div>
      </div>

      <div className="inspector-section">
        <h4>Transform</h4>
        <div className="kv-grid mono">
          <div className="kv-key">Position</div>
          <div className="kv-val">
            {rows.position ? `${formatNumber(rows.position.x)}, ${formatNumber(rows.position.y)}, ${formatNumber(rows.position.z)}` : '-'}
          </div>

          <div className="kv-key">Rotation</div>
          <div className="kv-val">
            {rows.rotation
              ? `${formatNumber(rows.rotation.x)}, ${formatNumber(rows.rotation.y)}, ${formatNumber(rows.rotation.z)}`
              : '-'}
          </div>

          <div className="kv-key">Scale</div>
          <div className="kv-val">
            {rows.scale ? `${formatNumber(rows.scale.x)}, ${formatNumber(rows.scale.y)}, ${formatNumber(rows.scale.z)}` : '-'}
          </div>
        </div>
      </div>

      <div className="inspector-section">
        <h4>Bounds</h4>
        <div className="kv-grid mono">
          <div className="kv-key">Diagonal</div>
          <div className="kv-val">{rows.diagonal ? formatNumber(rows.diagonal) : '-'}</div>

          <div className="kv-key">Min</div>
          <div className="kv-val">
            {rows.min ? `${formatNumber(rows.min[0])}, ${formatNumber(rows.min[1])}, ${formatNumber(rows.min[2])}` : '-'}
          </div>

          <div className="kv-key">Max</div>
          <div className="kv-val">
            {rows.max ? `${formatNumber(rows.max[0])}, ${formatNumber(rows.max[1])}, ${formatNumber(rows.max[2])}` : '-'}
          </div>
        </div>
      </div>

      <div className="inspector-section">
        <h4>Camera</h4>
        <div className="kv-grid mono">
          <div className="kv-key">Position</div>
          <div className="kv-val">
            {rows.cameraPosition
              ? `${formatNumber(rows.cameraPosition.x)}, ${formatNumber(rows.cameraPosition.y)}, ${formatNumber(rows.cameraPosition.z)}`
              : '-'}
          </div>

          <div className="kv-key">FOV</div>
          <div className="kv-val">{rows.cameraFov ? `${formatNumber(rows.cameraFov, 1)}°` : '-'}</div>

          <div className="kv-key">Near / Far</div>
          <div className="kv-val">
            {rows.cameraNear != null && rows.cameraFar != null
              ? `${formatNumber(rows.cameraNear, 2)} / ${formatNumber(rows.cameraFar, 0)}`
              : '-'}
          </div>
        </div>
      </div>

      <div className="inspector-footer">
        <span>{darkMode ? 'Dark' : 'Light'} mode</span>
      </div>
    </aside>
  )
}
