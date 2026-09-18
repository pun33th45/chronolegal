import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-6">
          <div className="max-w-sm text-center">
            <div className="w-12 h-12 rounded-xl bg-destructive/10 flex items-center justify-center text-destructive mx-auto mb-4">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h1 className="text-base font-semibold text-foreground">Something went wrong</h1>
            <p className="text-sm text-muted-foreground mt-1">
              An unexpected error occurred. Reloading the page usually resolves it.
            </p>
            <Button className="mt-5" onClick={() => window.location.reload()}>
              Reload
            </Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
