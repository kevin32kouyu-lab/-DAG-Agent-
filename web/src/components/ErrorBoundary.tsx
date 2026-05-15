import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-6 m-6 text-center">
            <p className="text-red-400 font-medium">页面渲染出错</p>
            <pre className="text-xs text-red-300/60 mt-2 font-mono whitespace-pre-wrap">
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-3 px-3 py-1.5 bg-red-800/30 border border-red-700/50 rounded text-sm text-red-300 transition-all active:scale-95"
            >
              重试
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
