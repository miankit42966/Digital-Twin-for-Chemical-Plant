import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Billboard, Html, OrbitControls, Text } from '@react-three/drei'
import { CatmullRomCurve3, DoubleSide, MathUtils, Vector3, type Group, type Mesh, type OrthographicCamera } from 'three'
import type { Asset } from './types'

type Point = [number, number, number]
type Props = { assets: Asset[]; selectedId: string | null; select: (asset: Asset) => void; playing: boolean; speed: number }
const routes: Point[][] = [
  [[-5.75,.95,.25],[-4.95,.95,.25]],
  [[-4.1,2.55,.25],[-4.1,2.95,.25],[-2.4,2.95,-.7],[-2.4,2.32,-.7]],
  [[-1.07,2.32,-.7],[.6,2.32,-.7],[.6,1.85,-.25]],
  [[.6,.52,-.25],[.6,.25,-.25],[4,.25,.2],[4,.65,.2]],
  [[4,.18,.2],[5.45,.18,.2]],
  [[.6,1.85,-.25],[.6,2.15,2.1],[-1.4,2.15,2.1],[-1.4,1.35,2.1]],
  [[-1.4,.95,2.1],[-3.85,.95,2.1],[-4.1,1.05,1.05]],
]

const byId = (assets: Asset[], id: string) => assets.find(asset => asset.asset_id === id)

function FitSceneCamera() {
  const { camera, size } = useThree()
  useEffect(() => {
    const view = camera as OrthographicCamera
    view.zoom = Math.min(54, Math.max(22, size.width / 15))
    view.updateProjectionMatrix()
  }, [camera, size.width])
  return null
}

function ProcessPipe({ points, color = '#58c6d3', radius = 0.055, playing, speed, flowRatio = 1 }: { points: Point[]; color?: string; radius?: number; playing: boolean; speed: number; flowRatio?: number }) {
  const curve = useMemo(() => new CatmullRomCurve3(points.map(point => new Vector3(...point)), false, 'catmullrom', .2), [points])
  const markers = useRef<(Mesh | null)[]>([])
  const phase = useRef(0)
  const direction = useMemo(() => curve.getTangentAt(.5), [curve])
  const arrow = useRef<Mesh>(null)
  useEffect(() => { arrow.current?.quaternion.setFromUnitVectors(new Vector3(0, 1, 0), direction) }, [direction])
  useFrame((_, delta) => {
    if (playing && flowRatio > 0) phase.current = (phase.current + Math.min(delta, .1) * speed * flowRatio / Math.max(.5, curve.getLength())) % 1
    markers.current.forEach((marker, index) => marker?.position.copy(curve.getPointAt((phase.current + index / 5) % 1)))
  })
  return <group>
    <mesh><tubeGeometry args={[curve, 48, radius, 10, false]} /><meshStandardMaterial color={color} metalness={.55} roughness={.32} emissive={color} emissiveIntensity={.13} /></mesh>
    <mesh ref={arrow} position={curve.getPointAt(.5)}><coneGeometry args={[.14, .27, 10]} /><meshBasicMaterial color={color} /></mesh>
    {Array.from({ length: 5 }, (_, index) => <mesh key={index} ref={mesh => { markers.current[index] = mesh }} visible={flowRatio > 0}><sphereGeometry args={[radius * 1.7, 10, 8]} /><meshBasicMaterial color={color === '#bb9e6b' ? '#ffe5a2' : '#b5fbff'} /></mesh>)}
  </group>
}

function SmoothLiquid({ percent, maxHeight, base, radius, width, depth }: { percent: number; maxHeight: number; base: number; radius?: number; width?: number; depth?: number }) {
  const mesh = useRef<Mesh>(null)
  const target = Math.max(.02, Math.min(1, percent / 100)) * maxHeight
  const initial = useRef(target)
  useFrame((_, delta) => {
    if (!mesh.current) return
    mesh.current.scale.y = MathUtils.damp(mesh.current.scale.y, target, 5, Math.min(delta, .1))
    mesh.current.position.y = base + mesh.current.scale.y / 2
  })
  return <mesh ref={mesh} position={[0, base + initial.current / 2, 0]} scale={[1, initial.current, 1]}>
    {radius ? <cylinderGeometry args={[radius, radius, 1, 36]} /> : <boxGeometry args={[width, 1, depth]} />}
    <meshStandardMaterial color="#43c2c7" emissive="#1b858c" emissiveIntensity={.18} transparent opacity={.72} />
  </mesh>
}

function Agitator({ playing, speed }: { playing: boolean; speed: number }) {
  const rotor = useRef<Group>(null)
  useFrame((_, delta) => { if (playing && rotor.current) rotor.current.rotation.y += Math.min(delta, .1) * speed * 1.8 })
  return <group><mesh position={[0, 1.35, 0]}><cylinderGeometry args={[.035, .035, 1.9, 10]} /><meshStandardMaterial color="#bad6de" /></mesh><group ref={rotor} position={[0, 1, 0]}>{[0, Math.PI / 3, 2 * Math.PI / 3].map(angle => <mesh key={angle} rotation={[0, angle, 0]}><boxGeometry args={[1.1, .06, .12]} /><meshStandardMaterial color="#d6edf0" metalness={.6} roughness={.3} /></mesh>)}</group></group>
}

function UnitLabel({ position, name, detail, context = false }: { position: Point; name: string; detail: string; context?: boolean }) {
  return <Billboard position={position} follow><Text fontSize={.27} color="#f2fbff" anchorX="center" outlineWidth={.012} outlineColor="#061520">{name}</Text><Text position={[0, -.28, 0]} fontSize={.16} color={context ? '#91aab9' : '#70dce8'} anchorX="center" outlineWidth={.008} outlineColor="#061520">{detail}</Text></Billboard>
}

function LevelGauge({ percent, position }: { percent: number; position: Point }) {
  return <group position={position}>
    <mesh position={[0, .65, 0]}><boxGeometry args={[.18, 1.3, .12]} /><meshStandardMaterial color="#0c2631" metalness={.4} roughness={.35} /></mesh>
    <group position={[0, 0, .075]}><SmoothLiquid percent={percent} maxHeight={1.28} base={.01} width={.12} depth={.025} /></group>
    <mesh position={[0, .65, .08]}><boxGeometry args={[.22, 1.34, .03]} /><meshStandardMaterial color="#84b9c9" transparent opacity={.23} /></mesh>
  </group>
}

function Reactor({ asset, selected, onClick, playing, speed }: { asset: Asset; selected: boolean; onClick: () => void; playing: boolean; speed: number }) {
  return <group position={[-4.1, 0, .25]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <mesh position={[0, 1.25, 0]}><cylinderGeometry args={[.82, .82, 2.35, 40]} /><meshStandardMaterial color="#7a9aaa" metalness={.5} roughness={.3} transparent opacity={.47} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={2.05} base={.2} radius={.72} />
    <Agitator playing={playing} speed={speed} />
    <mesh position={[0, 2.42, 0]} scale={[1,.28,1]}><sphereGeometry args={[.82, 32, 16]} /><meshStandardMaterial color="#acc1cb" metalness={.55} roughness={.28} /></mesh>
    <mesh position={[0, .08, 0]} scale={[1,.22,1]}><sphereGeometry args={[.82, 32, 16]} /><meshStandardMaterial color="#9cb5bf" metalness={.45} /></mesh>
    <mesh position={[0, .04, 0]}><cylinderGeometry args={[.95, .95, .1, 40]} /><meshStandardMaterial color={selected ? '#84e3e9' : '#668796'} emissive={selected ? '#26aebb' : '#000000'} emissiveIntensity={.25} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[.96, .4, .25]} />
    <UnitLabel position={[0, 3.5, 0]} name="REACTOR" detail="Measured · RX-201" />
  </group>
}

function Condenser() {
  return <group position={[-1.75, 2.32, -.7]}>
    <mesh rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.4, .4, 1.35, 32]} /><meshStandardMaterial color="#7695a4" metalness={.68} roughness={.27} /></mesh>
    {[-.45, -.15, .15, .45].map(x => <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[.41, .035, 8, 32]} /><meshStandardMaterial color="#a8c5cf" metalness={.7} /></mesh>)}
    <UnitLabel position={[0, 1.25, 0]} name="CONDENSER" detail="Process context" context />
  </group>
}

function Separator({ asset, selected, onClick }: { asset: Asset; selected: boolean; onClick: () => void }) {
  return <group position={[.6, .55, -.25]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <mesh position={[0, .65, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.65, .65, 2.05, 36]} /><meshStandardMaterial color="#7897a7" metalness={.5} roughness={.32} transparent opacity={.65} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={.85} base={.15} width={1.75} depth={.85} />
    <mesh position={[-.65, .06, 0]}><boxGeometry args={[.13, .4, .45]} /><meshStandardMaterial color="#7d9aa6" /></mesh>
    <mesh position={[.65, .06, 0]}><boxGeometry args={[.13, .4, .45]} /><meshStandardMaterial color="#7d9aa6" /></mesh>
    <mesh position={[0, -.04, 0]}><boxGeometry args={[2.25, .11, 1.42]} /><meshStandardMaterial color={selected ? '#83e0e9' : '#698995'} emissive={selected ? '#31a5b1' : '#000000'} emissiveIntensity={.2} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[1.2, .12, .22]} />
    <UnitLabel position={[0, 2.7, 0]} name="SEPARATOR" detail="Measured · SP-201" />
  </group>
}

function Stripper({ asset, selected, onClick }: { asset: Asset; selected: boolean; onClick: () => void }) {
  return <group position={[4, 0, .2]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <mesh position={[0, 1.55, 0]}><cylinderGeometry args={[.54, .67, 2.95, 36]} /><meshStandardMaterial color="#8ba3ae" metalness={.48} roughness={.35} transparent opacity={.5} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={2.65} base={.14} radius={.5} />
    {[.7, 1.35, 2, 2.65].map(y => <mesh key={y} position={[0,y,0]}><torusGeometry args={[.65,.065,8,36]} /><meshStandardMaterial color="#a5c2cb" metalness={.65} /></mesh>)}
    <mesh position={[0, .02, 0]}><cylinderGeometry args={[.78, .78, .1, 36]} /><meshStandardMaterial color={selected ? '#83e0e9' : '#698995'} emissive={selected ? '#31a5b1' : '#000000'} emissiveIntensity={.2} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[.82, .35, .1]} />
    <UnitLabel position={[0, 4.05, 0]} name="STRIPPER" detail="Measured · ST-301" />
  </group>
}

function Compressor({ playing, speed }: { playing: boolean; speed: number }) {
  const rotor = useRef<Group>(null)
  useFrame((_, delta) => { if (playing && rotor.current) rotor.current.rotation.z -= Math.min(delta, .1) * speed * 3 })
  return <group position={[-1.4, .42, 2.1]}>
    <mesh position={[0,.52,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[.48,.18,14,40]} /><meshStandardMaterial color="#6f96a6" metalness={.65} roughness={.3} /></mesh>
    <mesh position={[0,.52,-.12]}><circleGeometry args={[.34,32]} /><meshStandardMaterial color="#32687d" emissive="#164458" emissiveIntensity={.2} /></mesh>
    <group ref={rotor} position={[0,.52,.19]}>{[0, Math.PI / 3, 2 * Math.PI / 3].map(angle => <mesh key={angle} rotation={[0,0,angle]}><boxGeometry args={[.65,.055,.03]} /><meshStandardMaterial color="#b0d5dd" /></mesh>)}</group>
    <mesh position={[0,.02,0]}><boxGeometry args={[1.25,.16,.85]} /><meshStandardMaterial color="#77929f" metalness={.55} /></mesh>
    <UnitLabel position={[0, 1.9, 0]} name="COMPRESSOR" detail="Recycle context" context />
  </group>
}

export default function PlantScene({ assets, selectedId, select, playing, speed }: Props) {
  const reactor = byId(assets, 'RX-201')
  const separator = byId(assets, 'SP-201')
  const stripper = byId(assets, 'ST-301')
  const normalizedFlow = (asset: Asset | undefined, reference: number) => (asset?.flow_value ?? 0) > 0 ? Math.max(.15, Math.min(2.5, asset!.flow_value! / reference)) : 0
  return <div className={`scene ${playing ? 'is-playing' : ''}`} aria-label={`3D process view, ${playing ? 'playing' : 'paused'}`}>
    <Canvas orthographic fallback={<p className="scene-loading" role="status">WebGL is unavailable. Choose the 2D flow view.</p>} camera={{ position: [8, 8, 13], zoom: 54, near: .1, far: 100 }} onCreated={({ camera }) => camera.lookAt(0, 1.7, 0)}>
      <Suspense fallback={<Html center><p className="scene-loading" role="status">Loading 3D process view…</p></Html>}>
      <FitSceneCamera />
      <color attach="background" args={['#081b26']} />
      <ambientLight intensity={1.25} /><hemisphereLight intensity={.8} groundColor="#1b3440" />
      <directionalLight position={[-3, 9, 6]} intensity={2.4} color="#e8f7ff" />
      <pointLight position={[4, 5, 1]} intensity={25} distance={12} color="#4ac9d4" />
      <mesh position={[0,-.12,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[13.8,7.5]} /><meshStandardMaterial color="#102b39" metalness={.15} roughness={.84} /></mesh>
      <gridHelper args={[13,13,'#275567','#173746']} position={[0,-.105,0]} />
      <ProcessPipe points={routes[0]} playing={playing} speed={speed} flowRatio={normalizedFlow(reactor, 42)} />
      <ProcessPipe points={routes[1]} playing={playing} speed={speed} />
      <ProcessPipe points={routes[2]} playing={playing} speed={speed} />
      <ProcessPipe points={routes[3]} color="#75bac1" playing={playing} speed={speed} flowRatio={normalizedFlow(separator, 24)} />
      <ProcessPipe points={routes[4]} color="#70dbba" playing={playing} speed={speed} flowRatio={normalizedFlow(stripper, 22)} />
      <ProcessPipe points={routes[5]} color="#bb9e6b" radius={.04} playing={playing} speed={speed} />
      <ProcessPipe points={routes[6]} color="#bb9e6b" radius={.04} playing={playing} speed={speed} />
      {reactor && <Reactor asset={reactor} selected={selectedId === reactor.asset_id} onClick={() => select(reactor)} playing={playing} speed={speed} />}
      <Condenser />
      {separator && <Separator asset={separator} selected={selectedId === separator.asset_id} onClick={() => select(separator)} />}
      {stripper && <Stripper asset={stripper} selected={selectedId === stripper.asset_id} onClick={() => select(stripper)} />}
      <Compressor playing={playing} speed={speed} />
      <UnitLabel position={[-5.7, 1.5, .25]} name="FEED" detail="" context />
      <UnitLabel position={[5.6, .8, .2]} name="PRODUCT" detail="" context />
      <OrbitControls makeDefault target={[0,1.7,0]} enablePan={false} minZoom={12} maxZoom={90} minPolarAngle={.4} maxPolarAngle={1.43} />
      </Suspense>
    </Canvas>
    <div className="scene-overlay"><span>{playing ? '▶ PROCESS PLAYBACK' : 'Ⅱ PROCESS PAUSED'}</span><span><i className="pipe-main" /> Process flow <i className="pipe-recycle" /> Recycle</span></div>
    <p className="scene-caption">Levels follow dataset samples. Moving markers and rotating parts illustrate the process route; their speed is visual. Select a vessel for readings.</p>
  </div>
}
