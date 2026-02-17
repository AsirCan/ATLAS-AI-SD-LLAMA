import React, { useState, useEffect } from 'react';
import { Clock, Cpu, Activity } from 'lucide-react';

export const ClockWidget = () => {
    const [time, setTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="flex items-center gap-3 dark:bg-white/5 bg-gray-100 border dark:border-white/5 border-gray-200 px-4 py-2 rounded-xl backdrop-blur-md dark:hover:bg-white/10 hover:bg-gray-200 transition-colors cursor-default">
            <Clock size={16} className="text-secondary" />
            <div className="flex flex-col leading-none">
                <span className="text-sm font-bold tracking-widest font-mono dark:text-white text-gray-800">
                    {time.toLocaleTimeString('tr-TR')}
                </span>
                <span className="text-xs text-gray-500 font-medium">
                    {time.toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' })}
                </span>
            </div>
        </div>
    );
};

export const SystemWidget = () => {
    // Mock data for visual effect
    const [cpu, setCpu] = useState(24);
    const [ram, setRam] = useState(42);

    useEffect(() => {
        const interval = setInterval(() => {
            setCpu(prev => Math.min(99, Math.max(10, prev + (Math.random() - 0.5) * 10)));
            setRam(prev => Math.min(99, Math.max(30, prev + (Math.random() - 0.5) * 5)));
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex items-center gap-4 dark:bg-white/5 bg-gray-100 border dark:border-white/5 border-gray-200 px-4 py-2 rounded-xl backdrop-blur-md dark:hover:bg-white/10 hover:bg-gray-200 transition-colors cursor-default group">
            <div className="flex items-center gap-2">
                <Cpu size={16} className="text-pink-500 group-hover:animate-pulse" />
                <div className="flex flex-col leading-none">
                    <span className="text-xs text-gray-500 font-bold">CPU</span>
                    <span className="text-sm font-mono dark:text-gray-300 text-gray-700">%{Math.round(cpu)}</span>
                </div>
            </div>
            <div className="w-px h-6 dark:bg-white/10 bg-gray-300"></div>
            <div className="flex items-center gap-2">
                <Activity size={16} className="text-green-500 group-hover:animate-pulse" />
                <div className="flex flex-col leading-none">
                    <span className="text-xs text-gray-500 font-bold">RAM</span>
                    <span className="text-sm font-mono dark:text-gray-300 text-gray-700">%{Math.round(ram)}</span>
                </div>
            </div>
        </div>
    );
};
