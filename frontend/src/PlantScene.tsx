import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { CatmullRomCurve3, Color, DoubleSide, MathUtils, ShaderMaterial, Vector3, type Group, type Mesh, type OrthographicCamera } from 'three'
import type { Asset } from './types'

type Point = [number, number, number]
type Props = { assets: Asset[]; selectedId: string | null; select: (asset: Asset) => void; playing: boolean; speed: number; highlightUnitId?: string | null }
type FlowPhase = 'liquid' | 'mixed' | 'vapor'
type FlowSource = 'reactor' | 'separator' | 'stripper' | 'context'
type PipeRoute = { id: string; points: Point[]; color: string; phase: FlowPhase; direction: 1 | -1; radius: number; flowSource: FlowSource }

const NOZZLES: Record<string, Point> = {
  reactorFeed: [-5.08, .95, .25], reactorEffluent: [-4.1, 2.78, .25], reactorRecycle: [-4.1, 1.05, 1.23],
  condenserIn: [-2.54, 2.32, -.7], condenserOut: [-.96, 2.32, -.7],
  separatorIn: [-.56, 1.2, -.25], separatorVapor: [.6, 1.98, -.25], separatorLiquid: [.6, .42, -.25],
  stripperFeed: [3.28, 2.25, .2], stripperProduct: [4.82, .3, .2],
  compressorSuction: [-1.4, 1.68, 2.1], compressorDischarge: [-2.1, .94, 2.1],
}

const PIPE_ROUTES: PipeRoute[] = [
  { id: 'feed', points: [[-5.75,.95,.25],[-5.28,.95,.25],NOZZLES.reactorFeed], color: '#d4ae73', phase: 'liquid', direction: 1, radius: .06, flowSource: 'reactor' },
  { id: 'reactorEffluent', points: [NOZZLES.reactorEffluent,[-4.1,2.96,.25],[-2.54,2.96,-.7],[-2.54,2.56,-.7],NOZZLES.condenserIn], color: '#58c6d3', phase: 'mixed', direction: 1, radius: .062, flowSource: 'reactor' },
  { id: 'condensedStream', points: [NOZZLES.condenserOut,[-.74,2.32,-.7],[-.74,1.2,-.25],NOZZLES.separatorIn], color: '#58c6d3', phase: 'liquid', direction: 1, radius: .062, flowSource: 'context' },
  { id: 'separatorLiquid', points: [NOZZLES.separatorLiquid,[.6,.25,-.25],[3.06,.25,.2],[3.06,2.25,.2],NOZZLES.stripperFeed], color: '#75bac1', phase: 'liquid', direction: 1, radius: .064, flowSource: 'separator' },
  { id: 'product', points: [NOZZLES.stripperProduct,[5.08,.3,.2],[5.55,.3,.2]], color: '#70dbba', phase: 'liquid', direction: 1, radius: .062, flowSource: 'stripper' },
  { id: 'separatorVapor', points: [NOZZLES.separatorVapor,[.6,2.2,-.25],[.6,2.2,2.1],[-1.4,2.2,2.1],[-1.4,1.86,2.1],NOZZLES.compressorSuction], color: '#bb9e6b', phase: 'vapor', direction: 1, radius: .045, flowSource: 'context' },
  { id: 'compressorRecycle', points: [NOZZLES.compressorDischarge,[-2.28,.94,2.1],[-3.82,.94,2.1],[-4.1,1.05,1.46],NOZZLES.reactorRecycle], color: '#bb9e6b', phase: 'vapor', direction: 1, radius: .045, flowSource: 'context' },
]

const CONDENSER_FLOW: Point[] = [[-.79,0,0],[-.46,.18,0],[-.16,-.17,0],[.16,.18,0],[.46,-.17,0],[.79,0,0]]
const STRIPPER_LIQUID_FLOW: Point[] = [[-.72,2.25,0],[-.25,2.18,0],[.34,1.92,0],[-.34,1.55,0],[.34,1.18,0],[-.3,.8,0],[.12,.38,0]]
const STRIPPER_VAPOR_FLOW: Point[] = [[0,.32,.08],[-.18,.86,.08],[.18,1.42,.08],[-.15,2.02,.08],[0,2.82,.08]]

const FLOW_VERTEX_SHADER = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const FLOW_FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uFlow;
  uniform float uPhase;
  varying vec2 vUv;
  void main() {
    float broad = 0.5 + 0.5 * sin((vUv.x * 6.0 - uTime * 1.35) * 6.2831853);
    float ripple = 0.5 + 0.5 * sin((vUv.x * 15.0 - uTime * 2.1 + vUv.y * 1.8) * 6.2831853);
    float softWave = smoothstep(0.2, 0.9, broad) * 0.22 + ripple * 0.08;
    float vaporDrift = (0.5 + 0.5 * sin((vUv.x * 8.0 - uTime * 1.1 + vUv.y * 3.0) * 6.2831853)) * 0.12;
    vec3 highlight = mix(vec3(0.7, 1.0, 1.0), vec3(1.0, 0.9, 0.62), uPhase);
    vec3 color = uColor * (0.78 + softWave) + highlight * mix(softWave, vaporDrift, uPhase);
    float alpha = mix(0.94, 0.56, uPhase) * mix(0.48, 1.0, step(0.01, uFlow));
    gl_FragColor = vec4(color, alpha);
  }
`

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

function ContinuousFlow({ curve, radius, color, phase, direction, playing, speed, flowRatio }: { curve: CatmullRomCurve3; radius: number; color: string; phase: FlowPhase; direction: 1 | -1; playing: boolean; speed: number; flowRatio: number }) {
  const material = useMemo(() => new ShaderMaterial({
    uniforms: { uColor: { value: new Color(color) }, uTime: { value: 0 }, uFlow: { value: flowRatio }, uPhase: { value: phase === 'vapor' ? 1 : phase === 'mixed' ? .34 : 0 } },
    vertexShader: FLOW_VERTEX_SHADER, fragmentShader: FLOW_FRAGMENT_SHADER, transparent: true, depthWrite: false, depthTest: false, toneMapped: false,
  }), [color, phase])
  useEffect(() => () => material.dispose(), [material])
  useEffect(() => { material.uniforms.uFlow.value = flowRatio }, [flowRatio, material])
  useFrame((_, delta) => {
    if (playing && flowRatio > 0) material.uniforms.uTime.value += direction * Math.min(delta, .08) * speed * Math.max(.15, flowRatio)
  })
  return <mesh renderOrder={3}><tubeGeometry args={[curve, 56, radius, 12, false]} /><primitive object={material} attach="material" /></mesh>
}

function InternalFlow({ points, color, phase, playing, speed, radius = .06 }: { points: Point[]; color: string; phase: FlowPhase; playing: boolean; speed: number; radius?: number }) {
  const curve = useMemo(() => new CatmullRomCurve3(points.map(point => new Vector3(...point)), false, 'centripetal'), [points])
  return <ContinuousFlow curve={curve} radius={radius} color={color} phase={phase} direction={1} playing={playing} speed={speed} flowRatio={1} />
}

function ProcessPipe({ route, playing, speed, flowRatio }: { route: PipeRoute; playing: boolean; speed: number; flowRatio: number }) {
  const curve = useMemo(() => new CatmullRomCurve3(route.points.map(point => new Vector3(...point)), false, 'centripetal'), [route.points])
  return <group>
    <mesh renderOrder={1}><tubeGeometry args={[curve, 56, route.radius * 1.68, 12, false]} /><meshPhysicalMaterial color="#b7e9ee" metalness={.04} roughness={.08} transmission={.24} transparent opacity={.28} side={DoubleSide} depthWrite={false} /></mesh>
    <ContinuousFlow curve={curve} radius={route.radius * 1.08} color={route.color} phase={route.phase} direction={route.direction} playing={playing} speed={speed} flowRatio={flowRatio} />
  </group>
}

function Nozzle({ position, rotation = [0,0,0], color = '#85b9c5', radius = .09, length = .22 }: { position: Point; rotation?: Point; color?: string; radius?: number; length?: number }) {
  return <group position={position} rotation={rotation}>
    <mesh><cylinderGeometry args={[radius, radius, length, 18]} /><meshStandardMaterial color={color} metalness={.42} roughness={.22} transparent opacity={.76} /></mesh>
    <mesh position={[0, length / 2, 0]}><torusGeometry args={[radius * 1.18, radius * .18, 8, 20]} /><meshStandardMaterial color="#b9dbe1" metalness={.55} transparent opacity={.8} /></mesh>
  </group>
}

function GlassPlatform({ position, width, depth }: { position: Point; width: number; depth: number }) {
  return <group position={position}>
    <mesh position={[0, -.055, 0]}><boxGeometry args={[width, .11, depth]} /><meshStandardMaterial color="#1d6f80" emissive="#0b5867" emissiveIntensity={.45} transparent opacity={.34} depthWrite={false} /></mesh>
    <mesh position={[0, .008, 0]}><boxGeometry args={[width, .015, depth]} /><meshBasicMaterial color="#72e6ea" transparent opacity={.72} /></mesh>
    <mesh position={[0, -.045, 0]}><boxGeometry args={[width, .1, depth]} /><meshBasicMaterial color="#53dbe2" wireframe transparent opacity={.5} /></mesh>
  </group>
}

function EquipmentCallout({ asset, position, warning = false }: { asset: Asset; position: Point; warning?: boolean }) {
  return <Html position={position} transform sprite distanceFactor={9} zIndexRange={[3, 0]}>
    <section className="scene-callout" aria-label={`${asset.asset_name} measured readings`}>
      <strong>{asset.asset_id}</strong>
      <span>{asset.asset_name.toUpperCase()}</span>
      {warning && <em className="scene-forecast-warning">PREDICTED ≤1 H</em>}
      <dl><div><dt>T</dt><dd>{asset.temperature_c.toFixed(1)} °C</dd></div><div><dt>P</dt><dd>{asset.pressure_bar.toFixed(2)} bar</dd></div>{!['CD-201', 'CP-201'].includes(asset.asset_id) && <div><dt>L</dt><dd>{asset.level_percent.toFixed(1)}%</dd></div>}</dl>
    </section>
  </Html>
}

function ForecastHalo({ position, radius }: { position: Point; radius: number }) {
  return <group position={position}>
    <mesh rotation={[-Math.PI / 2, 0, 0]} renderOrder={5}><torusGeometry args={[radius, .06, 10, 64]} /><meshStandardMaterial color="#ffcc78" emissive="#ff9d2f" emissiveIntensity={1.8} toneMapped={false} /></mesh>
    <pointLight position={[0, .85, 0]} color="#ffb35a" intensity={10} distance={3.2} />
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
    <meshStandardMaterial color="#43c2c7" emissive="#1b858c" emissiveIntensity={.3} transparent opacity={.62} depthWrite={false} />
  </mesh>
}

function Agitator({ playing, speed }: { playing: boolean; speed: number }) {
  const rotor = useRef<Group>(null)
  useFrame((_, delta) => { if (playing && rotor.current) rotor.current.rotation.y += Math.min(delta, .1) * speed * 1.8 })
  return <group><mesh position={[0, 1.35, 0]}><cylinderGeometry args={[.035, .035, 1.9, 10]} /><meshStandardMaterial color="#bad6de" transparent opacity={.7} /></mesh><group ref={rotor} position={[0, 1, 0]}>{[0, Math.PI / 3, 2 * Math.PI / 3].map(angle => <mesh key={angle} rotation={[0, angle, 0]}><boxGeometry args={[1.1, .06, .12]} /><meshStandardMaterial color="#d6edf0" metalness={.6} roughness={.3} transparent opacity={.68} /></mesh>)}</group></group>
}

function UnitLabel({ position, name, detail, context = false }: { position: Point; name: string; detail: string; context?: boolean }) {
  return <Html position={position} transform sprite distanceFactor={9} zIndexRange={[2, 0]}>
    <div className={`scene-unit-label ${context ? 'is-context' : ''}`}><strong>{name}</strong>{detail && <span>{detail}</span>}</div>
  </Html>
}

function LevelGauge({ percent, position }: { percent: number; position: Point }) {
  return <group position={position}>
    <mesh position={[0, .65, 0]}><boxGeometry args={[.18, 1.3, .12]} /><meshStandardMaterial color="#0c2631" metalness={.4} roughness={.35} transparent opacity={.56} /></mesh>
    <group position={[0, 0, .075]}><SmoothLiquid percent={percent} maxHeight={1.28} base={.01} width={.12} depth={.025} /></group>
    <mesh position={[0, .65, .08]}><boxGeometry args={[.22, 1.34, .03]} /><meshStandardMaterial color="#84b9c9" transparent opacity={.23} /></mesh>
  </group>
}

function Reactor({ asset, selected, onClick, playing, speed }: { asset: Asset; selected: boolean; onClick: () => void; playing: boolean; speed: number }) {
  return <group position={[-4.1, 0, .25]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <Nozzle position={[-.9,.95,0]} rotation={[0,0,Math.PI / 2]} color="#d4ae73" length={.16} />
    <Nozzle position={[0,2.69,0]} color="#58c6d3" length={.18} />
    <Nozzle position={[0,1.05,.9]} rotation={[Math.PI / 2,0,0]} color="#bb9e6b" length={.16} />
    <mesh position={[0, 1.25, 0]}><cylinderGeometry args={[.82, .82, 2.35, 40]} /><meshStandardMaterial color="#7a9aaa" metalness={.5} roughness={.3} transparent opacity={.47} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={2.05} base={.2} radius={.72} />
    <Agitator playing={playing} speed={speed} />
    <mesh position={[0, 2.42, 0]} scale={[1,.28,1]}><sphereGeometry args={[.82, 32, 16]} /><meshStandardMaterial color="#acc1cb" metalness={.55} roughness={.28} transparent opacity={.58} /></mesh>
    <mesh position={[0, .08, 0]} scale={[1,.22,1]}><sphereGeometry args={[.82, 32, 16]} /><meshStandardMaterial color="#9cb5bf" metalness={.45} transparent opacity={.58} /></mesh>
    <mesh position={[0, .04, 0]}><cylinderGeometry args={[.95, .95, .1, 40]} /><meshStandardMaterial color={selected ? '#84e3e9' : '#668796'} emissive={selected ? '#26aebb' : '#000000'} emissiveIntensity={.25} transparent opacity={.62} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[.96, .4, .25]} />
  </group>
}

function Condenser({ asset, selected, onClick, playing, speed }: { asset?: Asset; selected: boolean; onClick?: () => void; playing: boolean; speed: number }) {
  return <group position={[-1.75, 2.32, -.7]} onClick={event => { if (onClick) { event.stopPropagation(); onClick() } }} onPointerOver={() => { if (asset) document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <Nozzle position={[-.74,0,0]} rotation={[0,0,Math.PI / 2]} color="#58c6d3" length={.1} radius={.075} />
    <Nozzle position={[.74,0,0]} rotation={[0,0,-Math.PI / 2]} color="#58c6d3" length={.1} radius={.075} />
    <mesh rotation={[0, 0, Math.PI / 2]} renderOrder={1}><cylinderGeometry args={[.4, .4, 1.35, 40, 1, true]} /><meshPhysicalMaterial color={selected ? '#8ff4ee' : '#a9d7df'} emissive={selected ? '#248b91' : '#000000'} emissiveIntensity={.3} metalness={.05} roughness={.08} transmission={.32} transparent opacity={.28} side={DoubleSide} depthWrite={false} /></mesh>
    <mesh position={[-.69,0,0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.42,.42,.055,32]} /><meshStandardMaterial color="#89aeb9" metalness={.5} transparent opacity={.5} /></mesh>
    <mesh position={[.69,0,0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.42,.42,.055,32]} /><meshStandardMaterial color="#89aeb9" metalness={.5} transparent opacity={.5} /></mesh>
    {[-.45, -.15, .15, .45].map(x => <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[.41, .028, 8, 32]} /><meshStandardMaterial color="#b4d8df" metalness={.45} transparent opacity={.58} /></mesh>)}
    {[-.19,0,.19].map(y => <mesh key={y} position={[0,y,0]} rotation={[0,0,Math.PI / 2]}><cylinderGeometry args={[.034,.034,1.27,12]} /><meshBasicMaterial color="#62dce6" transparent opacity={.7} /></mesh>)}
    <InternalFlow points={CONDENSER_FLOW} color="#62dce6" phase="liquid" playing={playing} speed={speed} radius={.066} />
    <UnitLabel position={[0, 1.25, 0]} name="CONDENSER" detail={asset ? asset.asset_id : 'Process context'} context={!asset} />
  </group>
}

function Separator({ asset, selected, onClick }: { asset: Asset; selected: boolean; onClick: () => void }) {
  return <group position={[.6, .55, -.25]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <Nozzle position={[-1.105,.65,0]} rotation={[0,0,Math.PI / 2]} color="#58c6d3" length={.09} />
    <Nozzle position={[0,1.38,0]} color="#bb9e6b" length={.1} radius={.08} />
    <Nozzle position={[0,-.08,0]} rotation={[0,0,Math.PI]} color="#75bac1" length={.1} />
    <mesh position={[0, .65, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.65, .65, 2.05, 36]} /><meshStandardMaterial color="#7897a7" metalness={.5} roughness={.32} transparent opacity={.65} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={.85} base={.15} width={1.75} depth={.85} />
    <mesh position={[-.65, .06, 0]}><boxGeometry args={[.13, .4, .45]} /><meshStandardMaterial color="#7d9aa6" transparent opacity={.6} /></mesh>
    <mesh position={[.65, .06, 0]}><boxGeometry args={[.13, .4, .45]} /><meshStandardMaterial color="#7d9aa6" transparent opacity={.6} /></mesh>
    <mesh position={[0, -.04, 0]}><boxGeometry args={[2.25, .11, 1.42]} /><meshStandardMaterial color={selected ? '#83e0e9' : '#698995'} emissive={selected ? '#31a5b1' : '#000000'} emissiveIntensity={.2} transparent opacity={.58} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[1.2, .12, .22]} />
  </group>
}

function Stripper({ asset, selected, onClick, playing, speed }: { asset: Asset; selected: boolean; onClick: () => void; playing: boolean; speed: number }) {
  return <group position={[4, 0, .2]} onClick={event => { event.stopPropagation(); onClick() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <Nozzle position={[-.64,2.25,0]} rotation={[0,0,Math.PI / 2]} color="#75bac1" length={.16} />
    <Nozzle position={[.73,.3,0]} rotation={[0,0,-Math.PI / 2]} color="#70dbba" length={.18} />
    <mesh position={[0, 1.55, 0]} renderOrder={1}><cylinderGeometry args={[.54, .67, 2.95, 40, 1, true]} /><meshPhysicalMaterial color="#b8d7dd" metalness={.08} roughness={.1} transmission={.28} transparent opacity={.2} side={DoubleSide} depthWrite={false} /></mesh>
    <SmoothLiquid percent={asset.level_percent} maxHeight={.78} base={.14} radius={.52} />
    {[.7, 1.35, 2, 2.65].map((y, index) => <group key={y} position={[0,y,0]}>
      <mesh><cylinderGeometry args={[.5,.5,.045,32]} /><meshStandardMaterial color="#91d6dc" emissive="#237a83" emissiveIntensity={.35} transparent opacity={.48} depthWrite={false} /></mesh>
      <mesh position={[index % 2 ? -.39 : .39,-.16,0]}><cylinderGeometry args={[.045,.045,.34,10]} /><meshBasicMaterial color="#9fe9ee" transparent opacity={.62} /></mesh>
      <mesh><torusGeometry args={[.62,.048,8,36]} /><meshStandardMaterial color="#b4d2d8" metalness={.45} transparent opacity={.58} /></mesh>
    </group>)}
    <InternalFlow points={STRIPPER_LIQUID_FLOW} color="#78f3ee" phase="liquid" playing={playing} speed={speed} radius={.068} />
    <InternalFlow points={STRIPPER_VAPOR_FLOW} color="#e8b967" phase="vapor" playing={playing} speed={speed * .8} radius={.052} />
    <mesh position={[0, .02, 0]}><cylinderGeometry args={[.78, .78, .1, 36]} /><meshStandardMaterial color={selected ? '#83e0e9' : '#698995'} emissive={selected ? '#31a5b1' : '#000000'} emissiveIntensity={.2} transparent opacity={.58} /></mesh>
    <LevelGauge percent={asset.level_percent} position={[.82, .35, .1]} />
  </group>
}

function Compressor({ asset, selected, onClick, playing, speed }: { asset?: Asset; selected: boolean; onClick?: () => void; playing: boolean; speed: number }) {
  const rotor = useRef<Group>(null)
  useFrame((_, delta) => { if (playing && rotor.current) rotor.current.rotation.z -= Math.min(delta, .1) * speed * 3 })
  return <group position={[-1.4, .42, 2.1]} onClick={event => { if (onClick) { event.stopPropagation(); onClick() } }} onPointerOver={() => { if (asset) document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = '' }}>
    <Nozzle position={[0,1.21,0]} color="#bb9e6b" length={.1} radius={.075} />
    <Nozzle position={[-.67,.52,0]} rotation={[0,0,Math.PI / 2]} color="#bb9e6b" length={.06} radius={.075} />
    <mesh position={[0,.52,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[.48,.18,14,40]} /><meshStandardMaterial color="#6f96a6" metalness={.65} roughness={.3} transparent opacity={.72} /></mesh>
    <mesh position={[0,.52,-.12]}><circleGeometry args={[.34,32]} /><meshStandardMaterial color="#32687d" emissive="#164458" emissiveIntensity={.2} transparent opacity={.64} /></mesh>
    <group ref={rotor} position={[0,.52,.19]}>{[0, Math.PI / 3, 2 * Math.PI / 3].map(angle => <mesh key={angle} rotation={[0,0,angle]}><boxGeometry args={[.65,.055,.03]} /><meshStandardMaterial color="#b0d5dd" transparent opacity={.72} /></mesh>)}</group>
    <mesh position={[0,.02,0]}><boxGeometry args={[1.25,.16,.85]} /><meshStandardMaterial color={selected ? '#84e3e9' : '#77929f'} emissive={selected ? '#268e98' : '#000000'} emissiveIntensity={.3} metalness={.55} transparent opacity={.64} /></mesh>
    <UnitLabel position={[0, 1.9, 0]} name="COMPRESSOR" detail={asset ? asset.asset_id : 'Recycle context'} context={!asset} />
  </group>
}

export default function PlantScene({ assets, selectedId, select, playing, speed, highlightUnitId = null }: Props) {
  const reactor = byId(assets, 'RX-201')
  const condenser = byId(assets, 'CD-201')
  const separator = byId(assets, 'SP-201')
  const stripper = byId(assets, 'ST-301')
  const compressor = byId(assets, 'CP-201')
  const normalizedFlow = (asset: Asset | undefined, reference: number) => (asset?.flow_value ?? 0) > 0 ? Math.max(.15, Math.min(2.5, asset!.flow_value! / reference)) : 0
  const flowBySource: Record<FlowSource, number> = {
    reactor: normalizedFlow(reactor, 42), separator: normalizedFlow(separator, 24), stripper: normalizedFlow(stripper, 22), context: 1,
  }
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
      <GlassPlatform position={[-4.1, -.02, .25]} width={2.85} depth={2.25} />
      <GlassPlatform position={[.6, -.02, -.25]} width={2.85} depth={1.85} />
      <GlassPlatform position={[4, -.02, .2]} width={2.35} depth={2.0} />
      <GlassPlatform position={[-1.4, -.02, 2.1]} width={1.85} depth={1.35} />
      {highlightUnitId === 'RX-201' && <ForecastHalo position={[-4.1, .11, .25]} radius={1.16} />}
      {highlightUnitId === 'CD-201' && <ForecastHalo position={[-1.75, .11, -.7]} radius={.78} />}
      {highlightUnitId === 'SP-201' && <ForecastHalo position={[.6, .11, -.25]} radius={1.25} />}
      {highlightUnitId === 'ST-301' && <ForecastHalo position={[4, .11, .2]} radius={.97} />}
      {highlightUnitId === 'CP-201' && <ForecastHalo position={[-1.4, .11, 2.1]} radius={.72} />}
      {PIPE_ROUTES.map(route => <ProcessPipe key={route.id} route={route} playing={playing} speed={speed} flowRatio={flowBySource[route.flowSource]} />)}
      {reactor && <Reactor asset={reactor} selected={selectedId === reactor.asset_id} onClick={() => select(reactor)} playing={playing} speed={speed} />}
      <Condenser asset={condenser} selected={selectedId === 'CD-201'} onClick={condenser ? () => select(condenser) : undefined} playing={playing} speed={speed} />
      {separator && <Separator asset={separator} selected={selectedId === separator.asset_id} onClick={() => select(separator)} />}
      {stripper && <Stripper asset={stripper} selected={selectedId === stripper.asset_id} onClick={() => select(stripper)} playing={playing} speed={speed} />}
      <Compressor asset={compressor} selected={selectedId === 'CP-201'} onClick={compressor ? () => select(compressor) : undefined} playing={playing} speed={speed} />
      {reactor && <EquipmentCallout asset={reactor} position={[-5.55, 2.4, .25]} warning={highlightUnitId === reactor.asset_id} />}
      {condenser && <EquipmentCallout asset={condenser} position={[-1.75, 3.4, -.7]} warning={highlightUnitId === condenser.asset_id} />}
      {separator && <EquipmentCallout asset={separator} position={[1.65, 2.38, -.25]} warning={highlightUnitId === separator.asset_id} />}
      {stripper && <EquipmentCallout asset={stripper} position={[5.3, 3.05, .2]} warning={highlightUnitId === stripper.asset_id} />}
      {compressor && <EquipmentCallout asset={compressor} position={[-.45, 2.1, 2.1]} warning={highlightUnitId === compressor.asset_id} />}
      <UnitLabel position={[-5.7, 1.5, .25]} name="FEED" detail="" context />
      <UnitLabel position={[5.6, .8, .2]} name="PRODUCT" detail="" context />
      <OrbitControls makeDefault target={[0,1.7,0]} enablePan={false} minZoom={12} maxZoom={90} minPolarAngle={.4} maxPolarAngle={1.43} />
      </Suspense>
    </Canvas>
    <div className="scene-overlay"><span>{playing ? '▶ PROCESS PLAYBACK' : 'Ⅱ PROCESS PAUSED'}</span><span><i className="pipe-main" /> Process flow <i className="pipe-recycle" /> Recycle</span></div>
    <p className="scene-caption">Continuous cyan and green streams show liquid routes; soft amber streams show vapor and recycle routes. Motion is illustrative; measured levels follow the selected dataset sample.</p>
  </div>
}
