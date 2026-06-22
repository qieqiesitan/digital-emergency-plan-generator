import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import Button from "@/mobile/components/ui/Button";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[ErrorBoundary] 移动端异常:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center min-h-dvh px-md bg-white text-center">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mb-md">
            <AlertTriangle size={32} className="text-danger" />
          </div>
          <h1 className="text-h2 text-neutral-900 mb-sm">页面出现异常</h1>
          <p className="text-body-sm text-neutral-600 mb-md max-w-xs">
            {this.state.error?.message ?? "发生了未知错误，请尝试刷新页面"}
          </p>
          <Button
            variant="primary"
            icon={<RefreshCw size={18} />}
            onClick={this.handleReset}
          >
            刷新页面
          </Button>
          <button
            className="mt-md text-caption text-neutral-400"
            onClick={() => window.location.reload()}
          >
            强制重新加载
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
