import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        this.setState({ error, errorInfo });
        console.error("Uncaught error:", error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    render() {
        if (this.state.hasError) {
            return (
                <div style={styles.overlay}>
                    <div style={styles.card}>
                        {/* Icon */}
                        <div style={styles.iconContainer}>
                            <span style={styles.icon}>⚠️</span>
                        </div>

                        {/* Title */}
                        <h1 style={styles.title}>Bir Hata Oluştu</h1>

                        {/* Error message */}
                        <p style={styles.message}>
                            {this.state.error
                                ? this.state.error.toString()
                                : 'Bilinmeyen bir hata meydana geldi.'}
                        </p>

                        {/* Retry button */}
                        <button
                            onClick={this.handleRetry}
                            style={styles.retryButton}
                            onMouseEnter={(e) => {
                                e.target.style.background =
                                    'linear-gradient(135deg, #8b00ff, #00b8d4)';
                                e.target.style.transform = 'scale(1.05)';
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.background =
                                    'linear-gradient(135deg, #7000ff, #00d4ff)';
                                e.target.style.transform = 'scale(1)';
                            }}
                        >
                            🔄 Yeniden Dene
                        </button>

                        {/* Collapsible details */}
                        {this.state.errorInfo && (
                            <details style={styles.details}>
                                <summary style={styles.summary}>
                                    Hata Detayları
                                </summary>
                                <pre style={styles.stack}>
                                    {this.state.errorInfo.componentStack}
                                </pre>
                            </details>
                        )}
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

const styles = {
    overlay: {
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(11, 11, 21, 0.95)',
        backdropFilter: 'blur(12px)',
        fontFamily: "'Inter', system-ui, sans-serif",
    },
    card: {
        maxWidth: '520px',
        width: '90%',
        padding: '40px',
        borderRadius: '24px',
        background: 'rgba(255, 255, 255, 0.04)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow:
            '0 8px 32px rgba(0, 0, 0, 0.5), 0 0 60px rgba(112, 0, 255, 0.1)',
        textAlign: 'center',
    },
    iconContainer: {
        marginBottom: '16px',
    },
    icon: {
        fontSize: '48px',
    },
    title: {
        margin: '0 0 12px 0',
        fontSize: '22px',
        fontWeight: 700,
        color: '#ffffff',
        letterSpacing: '-0.02em',
    },
    message: {
        margin: '0 0 24px 0',
        fontSize: '14px',
        color: 'rgba(255, 255, 255, 0.6)',
        lineHeight: 1.6,
        wordBreak: 'break-word',
    },
    retryButton: {
        padding: '12px 32px',
        fontSize: '15px',
        fontWeight: 600,
        color: '#ffffff',
        background: 'linear-gradient(135deg, #7000ff, #00d4ff)',
        border: 'none',
        borderRadius: '14px',
        cursor: 'pointer',
        transition: 'all 0.25s ease',
        boxShadow: '0 4px 20px rgba(112, 0, 255, 0.35)',
    },
    details: {
        marginTop: '24px',
        textAlign: 'left',
    },
    summary: {
        cursor: 'pointer',
        fontSize: '13px',
        color: 'rgba(255, 255, 255, 0.45)',
        marginBottom: '8px',
        userSelect: 'none',
    },
    stack: {
        maxHeight: '200px',
        overflow: 'auto',
        padding: '12px',
        borderRadius: '12px',
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        fontSize: '11px',
        color: 'rgba(255, 255, 255, 0.5)',
        whiteSpace: 'pre-wrap',
        lineHeight: 1.5,
    },
};

export default ErrorBoundary;
