import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        this.setState({ error, errorInfo });
        console.error("Uncaught error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: 'red', backgroundColor: '#fff', zIndex: 9999, position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', overflow: 'auto' }}>
                    <h1>🛑 Bir Hata Oluştu</h1>
                    <h2 style={{ color: '#333' }}>{this.state.error && this.state.error.toString()}</h2>
                    <details style={{ whiteSpace: 'pre-wrap', marginTop: '10px', color: '#666' }}>
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                    </details>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
