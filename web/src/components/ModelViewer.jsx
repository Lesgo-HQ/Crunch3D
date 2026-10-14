import { useState, Suspense, useEffect, useMemo, useRef, useCallback } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Center, Grid, GizmoHelper, GizmoViewport } from '@react-three/drei'
import * as THREE from 'three'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js'
import ModelInspector from './ModelInspector'
import { getImportanceMap } from '../api/client'

function importanceToColor(t) {
  const stops = [
    [0.0, 0.0, 1.0],
    [0.0, 1.0, 1.0],
    [0.0, 1.0, 0.0],
    [1.0, 1.0, 0.0],
    [1.0, 0.0, 0.0],
  ]
  const positions = [0.0, 0.25, 0.50, 0.75, 1.0]
  let i = 0
  while (i < positions.length - 1 && t > positions[i + 1]) i++
  if (i >= positions.length - 1) return stops[stops.length - 1]
  const lo = positions[i], hi = positions[i + 1]
  const alpha = (t - lo) / (hi - lo)
  const c0 = stops[i], c1 = stops[i + 1]
  return [
    c0[0] * (1 - alpha) + c1[0] * alpha,
    c0[1] * (1 - alpha) + c1[1] * alpha,
    c0[2] * (1 - alpha) + c1[2] * alpha,
  ]
}

function collectModelSummary(rootObject) {
  if (!rootObject) return null

  let meshCount = 0
  let materialCount = 0
  let vertexCount = 0
  let faceCount = 0
  let hasNormals = false
  let hasUVs = false
  const meshNames = []
  const materialSet = new Set()

  rootObject.traverse((child) => {
    if (!child.isMesh || !child.geometry) return
    meshCount += 1
    const geom = child.geometry
    const pos = geom.getAttribute('position')
    if (pos) vertexCount += pos.count
    if (geom.index) {
      faceCount += Math.floor(geom.index.count / 3)
    } else if (pos) {
      faceCount += Math.floor(pos.count / 3)
    }
    hasNormals = hasNormals || !!geom.getAttribute('normal')
    hasUVs = hasUVs || !!geom.getAttribute('uv')
    meshNames.push(child.name || `${child.type}_${meshCount}`)

    const materials = Array.isArray(child.material) ? child.material : [child.material]
    materials.forEach((mat) => {
      if (mat) materialSet.add(mat.uuid)
    })
  })
  materialCount = materialSet.size

  const box = new THREE.Box3().setFromObject(rootObject)
  const size = new THREE.Vector3()
  box.getSize(size)

  return {
    type: rootObject.type || 'Mesh',
    meshCount,
    materialCount,
    vertexCount,
    faceCount,
    hasNormals,
    hasUVs,
    position: rootObject.position ? rootObject.position.clone() : null,
    rotation: rootObject.rotation
      ? {
          x: THREE.MathUtils.radToDeg(rootObject.rotation.x),
          y: THREE.MathUtils.radToDeg(rootObject.rotation.y),
          z: THREE.MathUtils.radToDeg(rootObject.rotation.z),
        }
      : null,
    scale: rootObject.scale ? rootObject.scale.clone() : null,
    bounds: {
      size: { x: size.x, y: size.y, z: size.z },
      min: box.min.toArray(),
      max: box.max.toArray(),
      diagonal: size.length(),
    },
    meshNames,
  }
}

function CameraReporter({ onCameraChange }) {
  const { camera } = useThree()
  const lastReportRef = useRef({
    time: 0,
    x: null,
    y: null,
    z: null,
    fov: null,
    near: null,
    far: null,
  })

  useFrame(() => {
    const now = performance.now()
    const current = {
      x: camera.position.x,
      y: camera.position.y,
      z: camera.position.z,
      fov: camera.fov,
      near: camera.near,
      far: camera.far,
    }

    const prev = lastReportRef.current
    const moved =
      prev.x === null ||
      Math.abs(current.x - prev.x) > 0.001 ||
      Math.abs(current.y - prev.y) > 0.001 ||
      Math.abs(current.z - prev.z) > 0.001 ||
      Math.abs(current.fov - prev.fov) > 0.001 ||
      Math.abs(current.near - prev.near) > 0.001 ||
      Math.abs(current.far - prev.far) > 0.001

    const shouldReport = moved && now - prev.time > 120
    if (!shouldReport) return

    lastReportRef.current = { ...current, time: now }
    onCameraChange({
      position: camera.position.clone(),
      fov: camera.fov,
      near: camera.near,
      far: camera.far,
    })
  })
  return null
}

function MeshFromUrl({ url, filename, wireframe, importanceEnabled, importanceScores, onModelReady, onModelError, viewerName }) {
  const [object, setObject] = useState(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    setObject(null)
    onModelError?.(null)
    const ext = filename?.split('.').pop()?.toLowerCase()
    const manager = new THREE.LoadingManager()

    function onSuccess(obj) {
      if (cancelled) return
      console.group('MeshFromUrl:', viewerName || 'unnamed')
      console.log('Model URL:', url)
      console.log('Filename:', filename)
      obj.traverse((child) => {
        if (!child.isMesh || !child.geometry) return
        const geom = child.geometry
        const pos = geom.getAttribute('position')
        const verts = pos ? pos.count : 0
        const faces = geom.index ? Math.floor(geom.index.count / 3) : Math.floor(verts / 3)
        console.log(`  Mesh "${child.name}" — Vertices: ${verts}, Faces: ${faces}`)
      })
      console.groupEnd()
      setObject(obj)
      onModelReady?.(collectModelSummary(obj))
    }

    function onError(err) {
      if (cancelled) return
      onModelError?.(err)
    }

    if (ext === 'obj') {
      new OBJLoader(manager).load(url, (obj) => onSuccess(obj), undefined, onError)
    } else if (ext === 'stl') {
      new STLLoader(manager).load(url, (geometry) => {
        geometry.computeVertexNormals()
        const mesh = new THREE.Mesh(geometry)
        onSuccess(mesh)
      }, undefined, onError)
    } else if (ext === 'ply') {
      new PLYLoader(manager).load(url, (geometry) => {
        geometry.computeVertexNormals()
        const mesh = new THREE.Mesh(geometry)
        onSuccess(mesh)
      }, undefined, onError)
    } else if (ext === 'glb' || ext === 'gltf') {
      new GLTFLoader(manager).load(url, (gltf) => onSuccess(gltf.scene), undefined, onError)
    } else if (ext === 'fbx') {
      new FBXLoader(manager).load(url, (fbx) => onSuccess(fbx), undefined, onError)
    } else {
      onError(new Error(`Unsupported preview format: ${ext || 'unknown'}`))
    }

    return () => {
      cancelled = true
      // Dispose previous object's geometry to prevent stale render artifacts
      setObject((prev) => {
        if (prev) {
          prev.traverse((child) => {
            if (child.isMesh) {
              child.geometry?.dispose()
            }
          })
        }
        return null
      })
    }
  }, [url, filename, onModelReady, onModelError])

  const material = useMemo(() => {
    if (importanceEnabled && importanceScores) {
      return new THREE.MeshStandardMaterial({
        vertexColors: true,
        color: 0xffffff,
        roughness: 0.8,
        metalness: 0.05,
        wireframe,
        side: THREE.DoubleSide,
      })
    }
    return new THREE.MeshStandardMaterial({
      color: '#d4d4d4',
      wireframe,
      flatShading: !wireframe,
      side: THREE.DoubleSide,
      roughness: 0.78,
      metalness: 0.05,
    })
  }, [wireframe, importanceEnabled, importanceScores])

  useEffect(() => {
    if (!object) return
    object.traverse((child) => {
      if (child.isMesh) {
        child.material = material
      }
    })
  }, [object, material])

  useEffect(() => {
    if (!object || !importanceEnabled || !importanceScores) return

    let vertexOffset = 0
    object.traverse((child) => {
      if (!child.isMesh || !child.geometry) return
      const pos = child.geometry.getAttribute('position')
      if (!pos) return

      const vertCount = pos.count
      const sliceEnd = vertexOffset + vertCount

      if (vertexOffset >= importanceScores.length) {
        console.warn(
          `[Importance] Slice [${vertexOffset}, ${sliceEnd}) exceeds score array length ${importanceScores.length}`
        )
        return
      }

      let meshScores = importanceScores.slice(vertexOffset, Math.min(sliceEnd, importanceScores.length))
      if (meshScores.length < vertCount) {
        // Trimesh vs three vertex count can differ by welding/ordering; pad
        // the tail so the mesh still gets a heatmap instead of staying grey.
        const padded = new Array(vertCount).fill(0)
        for (let i = 0; i < meshScores.length; i++) padded[i] = meshScores[i]
        // fill remainder with the last available score to avoid a hard 0
        const fill = meshScores.length ? meshScores[meshScores.length - 1] : 0.5
        for (let i = meshScores.length; i < vertCount; i++) padded[i] = fill
        meshScores = padded
        console.warn(
          `[Importance] Slice [${vertexOffset}, ${sliceEnd}) truncated to ${meshScores.length} (total ${importanceScores.length})`
        )
      }
      const colors = new Float32Array(vertCount * 3)
      for (let i = 0; i < vertCount; i++) {
        const [r, g, b] = importanceToColor(meshScores[i])
        colors[i * 3 + 0] = r
        colors[i * 3 + 1] = g
        colors[i * 3 + 2] = b
      }
      child.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      child.geometry.attributes.color.needsUpdate = true
      child.material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        color: 0xffffff,
        roughness: 0.78,
        metalness: 0.05,
        side: THREE.DoubleSide,
        flatShading: false,
      })

      vertexOffset += vertCount
    })

    if (vertexOffset !== importanceScores.length) {
      console.warn(
        `[Importance] Vertex mismatch: consumed ${vertexOffset} vertices but received ${importanceScores.length} importance scores.`
      )
    }
  }, [object, importanceEnabled, importanceScores])

  useEffect(() => {
    if (!object || importanceEnabled) return
    object.traverse((child) => {
      if (child.isMesh && child.geometry) {
        child.geometry.deleteAttribute('color')
      }
    })
  }, [object, importanceEnabled])

  useEffect(() => {
    return () => {
      material.dispose()
    }
  }, [material])

  if (!object) return null

  return (
    <Center>
      <primitive object={object} />
    </Center>
  )
}

function Scene({ url, filename, wireframe, importanceEnabled, importanceScores, onModelReady, onModelError, onCameraChange, performanceMode, viewerName }) {

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[4, 5, 4]} intensity={0.85} color="#ffffff" />
      {!performanceMode && <directionalLight position={[-2, -2, 1]} intensity={0.4} color="#e6e6e6" />}
      <Suspense fallback={null}>
        {url && (
          <MeshFromUrl
            url={url}
            filename={filename}
            wireframe={wireframe}
            importanceEnabled={importanceEnabled}
            importanceScores={importanceScores}
            onModelReady={onModelReady}
            onModelError={onModelError}
            viewerName={viewerName}
          />
        )}
      </Suspense>
      <CameraReporter onCameraChange={onCameraChange} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
      
      {!performanceMode && (
        <>
          <axesHelper args={[10]} />
          <GizmoHelper alignment="bottom-right" margin={[40, 40]}>
            <GizmoViewport axisColors={['#ff3653', '#8adb00', '#2c8fff']} labelColor="white" />
          </GizmoHelper>
        </>
      )}

      {!performanceMode && (
        <Grid
          args={[10, 10]}
          cellSize={0.5}
          cellThickness={0.5}
          cellColor="#4a4a4a"
          sectionSize={2}
          sectionThickness={1}
          sectionColor="#7a7a7a"
          fadeDistance={15}
          infiniteGrid
          position={[0, -1, 0]}
        />
      )}
    </>
  )
}

function ImportanceLegend() {
  const items = [
    { label: 'Protected', color: '#ff0000' },
    { label: 'High', color: '#ffff00' },
    { label: 'Medium', color: '#00ff00' },
    { label: 'Low', color: '#0000ff' },
  ]
  return (
    <div className="viewer-legend">
      <div className="viewer-legend-title">Importance</div>
      {items.map((item) => (
        <div key={item.label} className="viewer-legend-row">
          {/* Swatches are the shader's vertex-colour ramp, not theme colours —
              they must stay fixed so the legend keeps describing the mesh. */}
          <span className="viewer-legend-swatch" style={{ background: item.color }} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  )
}

export default function ModelViewer({
  originalUrl,
  optimizedUrl,
  filename,
  optimizedFilename,
  originalStats,
  optimizedStats,
  darkMode,
  processing,
  stage,
  performanceMode,
  hasImportanceMap,
  jobId,
}) {
  const [wireframe, setWireframe] = useState(false)
  const [splitView, setSplitView] = useState(false)
  const [importanceEnabled, setImportanceEnabled] = useState(false)
  const [importanceScores, setImportanceScores] = useState(null)
  const [modelSummary, setModelSummary] = useState(null)
  const [cameraInfo, setCameraInfo] = useState(null)
  const [viewerError, setViewerError] = useState(null)
  const cameraCacheRef = useRef({})

  const canShowImportance = hasImportanceMap && !!originalUrl

  const showSplit = splitView && optimizedUrl

  useEffect(() => {
    if (!importanceEnabled || !jobId) {
      setImportanceScores(null)
      return
    }
    let cancelled = false
    getImportanceMap(jobId).then((data) => {
      if (cancelled) return
      setImportanceScores(data.scores)
    }).catch(() => {
      if (!cancelled) setImportanceEnabled(false)
    })
    return () => { cancelled = true }
  }, [importanceEnabled, jobId])

  const showOriginal = importanceEnabled || !optimizedUrl
  const activeFilename = importanceEnabled ? filename : (optimizedUrl ? optimizedFilename : filename)
  const activeStats = importanceEnabled ? originalStats : (optimizedUrl ? optimizedStats : originalStats)

  const inspectorMode = showSplit ? 'Comparison' : (showOriginal && !optimizedUrl ? 'Original' : importanceEnabled ? 'Original (Importance Map)' : 'Optimized')

  const handleCameraChange = useCallback((next) => {
    const rounded = {
      fov: Number(next.fov.toFixed(2)),
      near: Number(next.near.toFixed(4)),
      far: Number(next.far.toFixed(2)),
      x: Number(next.position.x.toFixed(3)),
      y: Number(next.position.y.toFixed(3)),
      z: Number(next.position.z.toFixed(3)),
    }

    const prev = cameraCacheRef.current
    if (
      prev.fov === rounded.fov &&
      prev.near === rounded.near &&
      prev.far === rounded.far &&
      prev.x === rounded.x &&
      prev.y === rounded.y &&
      prev.z === rounded.z
    ) {
      return
    }
    cameraCacheRef.current = rounded
    setCameraInfo({
      position: new THREE.Vector3(rounded.x, rounded.y, rounded.z),
      fov: rounded.fov,
      near: rounded.near,
      far: rounded.far,
    })
  }, [])

  const handleModelError = useCallback((err) => {
    if (!err) {
      setViewerError(null)
      return
    }
    setViewerError(err?.message || 'Could not load this mesh in the viewer')
  }, [])

  const handleModelReady = useCallback((summary) => {
    setViewerError(null)
    setModelSummary(summary)
  }, [])

  return (
    <div className="viewer-layout">
      <div className="viewer-area">
        <div className="viewer-controls">
          <button
            className={`viewer-btn ${wireframe ? 'active' : ''}`}
            onClick={() => setWireframe(!wireframe)}
          >
            Wireframe
          </button>
          {optimizedUrl && (
            <button
              className={`viewer-btn ${splitView ? 'active' : ''}`}
              onClick={() => {
                setSplitView((on) => {
                  return !on
                })
              }}
            >
              Split View
            </button>
          )}
          <button
            className={`viewer-btn ${importanceEnabled ? 'active' : ''}`}
            onClick={() => {
              if (!canShowImportance) return
              setImportanceEnabled((on) => {
                return !on
              })
            }}
            disabled={!canShowImportance}
            title={!canShowImportance ? 'Run optimization first to generate importance map' : 'Toggle importance heatmap'}
          >
            Importance Map
          </button>
        </div>

      {showSplit ? (
        <div className="viewer-split">
          <div className="viewer-container" style={{ position: 'relative' }}>
            <div className="viewer-label">Original</div>
            <Canvas
              camera={{ position: [3, 2, 3], fov: 50 }}
              dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
              gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
            >
              <Scene
                url={originalUrl}
                filename={filename}
                wireframe={wireframe}
                importanceEnabled={importanceEnabled}
                importanceScores={importanceScores}
                onModelReady={handleModelReady}
                onModelError={handleModelError}
                onCameraChange={handleCameraChange}
                performanceMode={performanceMode}
                viewerName="Original"
              />
            </Canvas>
            {importanceEnabled && <ImportanceLegend />}
          </div>
          <div className="viewer-container">
            <div className="viewer-label">Optimized</div>
            <Canvas
              camera={{ position: [3, 2, 3], fov: 50 }}
              dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
              gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
            >
              <Scene
                url={optimizedUrl}
                filename={optimizedFilename}
                wireframe={wireframe}
                importanceEnabled={false}
                importanceScores={null}
                onModelReady={handleModelReady}
                onModelError={handleModelError}
                onCameraChange={handleCameraChange}
                performanceMode={performanceMode}
                viewerName="Optimized" />
            </Canvas>
          </div>
        </div>
      ) : (
        <div className="viewer-container" style={{ position: 'relative' }}>
          {processing && (
            <div className="processing-overlay">
              <div className="spinner" />
              <p>{stage || 'Processing...'}</p>
            </div>
          )}
          <div className="viewer-label">
            {importanceEnabled ? 'Original (Importance Map)' : (optimizedUrl && !showOriginal ? 'Optimized' : 'Original')}
          </div>
          <Canvas
            camera={{ position: [3, 2, 3], fov: 50 }}
            dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
            gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
          >
            <Scene
              url={showOriginal ? originalUrl : optimizedUrl}
              filename={showOriginal ? filename : optimizedFilename}
              wireframe={wireframe}
              importanceEnabled={importanceEnabled && showOriginal}
              importanceScores={importanceScores}
              onModelReady={handleModelReady}
              onModelError={handleModelError}
              onCameraChange={handleCameraChange}
              performanceMode={performanceMode}
              viewerName={importanceEnabled ? 'Importance Map' : (optimizedUrl ? 'Optimized' : 'Original')} />
          </Canvas>
          {importanceEnabled && <ImportanceLegend />}
        </div>
      )}

        {viewerError && <div className="error-msg" style={{ marginTop: 12 }}>{viewerError}</div>}
      </div>

      <ModelInspector
        modelSummary={modelSummary}
        fileStats={activeStats}
        camera={cameraInfo}
        mode={inspectorMode}
        currentFilename={activeFilename}
        darkMode={darkMode}
      />
    </div>
  )
}
