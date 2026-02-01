import React, { useEffect, useRef } from 'react';
import { Terminal } from 'lucide-react';

const LogTerminal = ({ logs = [], className = '' }) => {
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className={`w-full max-w-2xl mx-auto bg-black rounded-lg overflow-hidden border border-gray-800 shadow-2xl font-mono text-sm ${className}`}>
            {/* Terminal Header */}
            <div className="bg-gray-900 px-4 py-2 flex items-center justify-between border-b border-gray-800">
                <div className="flex items-center gap-2 text-gray-400">
                    <Terminal size={14} />
                    <span className="text-xs font-bold tracking-wider">ATLAS_AGENT_MDL</span>
                </div>
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/50"></div>
                </div>
            </div>

            {/* Terminal Content */}
            <div className="p-4 h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent space-y-1">
                <div className="text-gray-500 mb-2">
                    Microsoft Windows [Version 10.0.19045.5487]<br />
                    (c) Microsoft Corporation. All rights reserved.<br />
                    <br />
                    C:\Users\Atlas{'>'} agent.exe --start
                </div>

                {logs.map((log, index) => {
                    let colorClass = "text-green-400/90";
                    if (log.includes("[RiskAgent]")) colorClass = "text-orange-400";
                    if (log.includes("GUARD FAILURE") || log.includes("ERROR")) colorClass = "text-red-500 font-bold";
                    if (log.includes("[VisualDirectorAgent]")) colorClass = "text-purple-400";
                    if (log.includes("[NewsAgent]")) colorClass = "text-blue-400";
                    if (log.includes("[InstagramPublisher]")) colorClass = "text-pink-400";

                    return (
                        <div key={index} className="flex gap-2 animate-fade-in-up font-mono text-xs md:text-sm">
                            <span className={`${colorClass} break-all whitespace-pre-wrap`}>{log}</span>
                        </div>
                    );
                })}

                <div className="flex gap-2 items-center animate-pulse mt-2">
                    <span className="text-green-500">➜</span>
                    <span className="w-2 h-4 bg-green-500"></span>
                </div>

                <div ref={bottomRef} />
            </div>
        </div>
    );
};

export default LogTerminal;
