"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  name?: string;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`ErrorBoundary (${this.props.name ?? "unknown"}):`, error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded border border-red-800 bg-red-950/30 p-6 text-center">
          <p className="text-sm text-red-300">
            <span className="font-semibold">{this.props.name ?? "Component"}</span> crashed
          </p>
          <p className="text-xs text-red-400 max-w-md font-mono">
            {this.state.error.message}
          </p>
          <button
            onClick={this.handleRetry}
            className="rounded bg-red-800 hover:bg-red-700 px-3 py-1 text-xs text-white transition-colors"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
