import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, Terminal } from 'lucide-react';

const SOURCE_STYLES = {
    NewsAgent: {
        badge: 'bg-cyan-500/20 text-cyan-100',
        text: 'text-cyan-100',
    },
    RiskAgent: {
        badge: 'bg-amber-500/20 text-amber-100',
        text: 'text-amber-100',
    },
    VisualDirectorAgent: {
        badge: 'bg-fuchsia-500/20 text-fuchsia-100',
        text: 'text-fuchsia-100',
    },
    CaptionAgent: {
        badge: 'bg-emerald-500/20 text-emerald-100',
        text: 'text-emerald-100',
    },
    SchedulerAgent: {
        badge: 'bg-indigo-500/20 text-indigo-100',
        text: 'text-indigo-100',
    },
    Orchestrator: {
        badge: 'bg-sky-500/20 text-sky-100',
        text: 'text-sky-100',
    },
    default: {
        badge: 'bg-white/10 text-gray-100',
        text: 'text-gray-200',
    },
};

const BOTTOM_EPSILON = 20;

function parseLogLine(line = '') {
    const raw = String(line || '');
    const timestampMatch = raw.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*/);
    const timestamp = timestampMatch ? timestampMatch[1] : null;
    const afterTime = timestampMatch ? raw.slice(timestampMatch[0].length) : raw;

    const sourceMatch = afterTime.match(/^\[([^\]]+)\]\s*/);
    const source = sourceMatch ? sourceMatch[1] : null;
    const message = sourceMatch ? afterTime.slice(sourceMatch[0].length) : afterTime;

    const upper = raw.toUpperCase();
    const isError = upper.includes('ERROR') || upper.includes('GUARD FAILURE') || upper.includes('FAILED');

    return { timestamp, source, message, isError };
}

const LogTerminal = ({ logs = [], className = '' }) => {
    const viewportRef = useRef(null);
    const [followTail, setFollowTail] = useState(true);
    const [hasUnseen, setHasUnseen] = useState(false);

    const parsedLogs = useMemo(() => logs.map(parseLogLine), [logs]);

    useEffect(() => {
        const el = viewportRef.current;
        if (!el) return;

        const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        const nearBottom = distanceToBottom <= BOTTOM_EPSILON;

        if (followTail || nearBottom) {
            el.scrollTop = el.scrollHeight;
            setHasUnseen(false);
        } else if (parsedLogs.length > 0) {
            setHasUnseen(true);
        }
    }, [parsedLogs, followTail]);

    const handleScroll = () => {
        const el = viewportRef.current;
        if (!el) return;

        const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        const nearBottom = distanceToBottom <= BOTTOM_EPSILON;
        setFollowTail(nearBottom);
        if (nearBottom) setHasUnseen(false);
    };

    const jumpToBottom = () => {
        const el = viewportRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
        setFollowTail(true);
        setHasUnseen(false);
    };

    return (
        <div className={`w-full max-w-none mx-auto rounded-2xl overflow-hidden border border-cyan-400/20 bg-[#06090f]/95 shadow-[0_18px_60px_rgba(0,0,0,0.45)] ${className}`}>
            <div className="px-4 md:px-5 py-3 flex items-center justify-between border-b border-white/10 bg-gradient-to-r from-[#0b1220]/95 to-[#0e1a2e]/85">
                <div className="flex items-center gap-2 text-slate-200">
                    <Terminal size={16} className="text-cyan-300" />
                    <span className="text-sm md:text-base font-semibold tracking-wide">ATLAS_AGENT_MDL</span>
                    <span className="text-[10px] md:text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-200 border border-cyan-400/30">LIVE</span>
                </div>
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-rose-400/70" />
                    <div className="w-2.5 h-2.5 rounded-full bg-amber-300/70" />
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400/70" />
                </div>
            </div>

            <div
                ref={viewportRef}
                onScroll={handleScroll}
                onWheelCapture={(e) => e.stopPropagation()}
                onTouchMoveCapture={(e) => e.stopPropagation()}
                className="relative p-3 md:p-5 h-[52vh] min-h-[360px] max-h-[640px] overflow-y-auto overscroll-contain scrollbar-thin scrollbar-thumb-cyan-400/35 scrollbar-track-transparent font-mono"
            >
                <div className="text-slate-400 text-xs md:text-sm mb-3 leading-relaxed">
                    C:\Users\Atlas{`>`} agent.exe --start
                </div>

                <div className="space-y-0.5">
                    {parsedLogs.map((entry, index) => {
                        const sourceStyle = SOURCE_STYLES[entry.source] || SOURCE_STYLES.default;
                        const messageClass = entry.isError ? 'text-rose-300 font-semibold' : sourceStyle.text;
                        return (
                            <div key={index} className="flex items-start gap-2 md:gap-3 py-1.5 border-b border-white/5 last:border-b-0 text-[13px] md:text-[15px] leading-6">
                                <span className="text-cyan-300/80 min-w-[78px]">{entry.timestamp ? `[${entry.timestamp}]` : '[--:--:--]'}</span>
                                <span
                                    className={`mt-0.5 inline-flex items-center px-2 h-5 rounded text-[10px] md:text-[11px] uppercase tracking-wide whitespace-nowrap ${entry.isError ? 'bg-rose-500/20 text-rose-200' : sourceStyle.badge
                                        }`}
                                >
                                    {entry.source || 'System'}
                                </span>
                                <span className={`${messageClass} whitespace-pre-wrap break-all`}>{entry.message || entry.source || ''}</span>
                            </div>
                        );
                    })}
                </div>

                <div className="flex gap-2 items-center mt-2 text-emerald-300 text-sm">
                    <span>{`>`}</span>
                    <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse" />
                </div>
            </div>

            {!followTail && hasUnseen && (
                <div className="px-3 py-2 border-t border-white/10 bg-[#0b1220]/85">
                    <button
                        onClick={jumpToBottom}
                        className="w-full inline-flex items-center justify-center gap-2 text-sm py-2 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-200 border border-cyan-400/30 transition-colors"
                    >
                        <ArrowDown size={14} />
                        Yeni log var, en alta in
                    </button>
                </div>
            )}
        </div>
    );
};

export default LogTerminal;
