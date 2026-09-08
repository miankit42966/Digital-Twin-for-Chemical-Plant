import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export default class SceneErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PlantScene 3D rendering error caught by boundary:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div
          className="scene-fallback"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: '400px',
            background: '#152530',
            color: '#eaf3f7',
            padding: '24px',
            textAlign: 'center',
            borderRadius: '6px',
            border: '1px solid #284550',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: '#63b5d4' }}>
            3D Plant Scene Fallback
          </h3>
          <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#90a9b2', maxWidth: '420px', lineHeight: 1.5 }}>
            The 3D WebGL renderer encountered an error. Telemetry stream, asset telemetry, and alarm systems continue operating normally.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined })}
            style={{
              padding: '8px 16px',
              backgroundColor: '#1b3f52',
              color: '#eff9fb',
              border: '1px solid #3996ba',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            Retry 3D Scene
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
