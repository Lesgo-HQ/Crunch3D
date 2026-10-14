import { useState, useRef } from 'react'
import { uploadMesh } from '../api/client'

export default function FileUpload({ onUploadComplete, disabled }) {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  const ACCEPTED = '.obj,.stl,.ply,.glb,.gltf,.fbx,.off'

  async function handleFile(file) {
    if (!file) return
    setError(null)
    setUploading(true)
    setProgress(0)

    try {
      const result = await uploadMesh(file, setProgress)
      onUploadComplete(result, file)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  function onDragOver(e) {
    e.preventDefault()
    setDragOver(true)
  }

  return (
    <div
      className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={() => setDragOver(false)}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        hidden
        onChange={(e) => handleFile(e.target.files[0])}
      />

      {uploading ? (
        <div className="upload-progress">
          <h2>Uploading & Analyzing...</h2>
          <p>{progress}%</p>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : (
        <>
          <h2>Drop your 3D model here</h2>
          <p>or click to browse — OBJ, STL, PLY, GLB, GLTF, FBX</p>
        </>
      )}

      {error && <p className="error-msg" style={{ marginTop: 16 }}>{error}</p>}
    </div>
  )
}
