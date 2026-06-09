import { Component, type ReactNode } from 'react'

/**
 * Catches render errors in a subtree so one broken view (e.g. an unexpected data
 * shape) shows a message instead of blank-screening the whole app. Place around
 * each route element so the nav stays usable and other views are unaffected.
 */
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, maxWidth: 720, margin: '0 auto' }}>
          <h2 style={{ color: '#b91c1c', marginBottom: 8 }}>This view hit an error</h2>
          <p style={{ color: '#475569', fontSize: 14 }}>
            {this.state.error.message || 'Unexpected render error.'}
          </p>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 8 }}>
            Other tabs still work — switch views or reload the page.
          </p>
        </div>
      )
    }
    return this.props.children
  }
}
