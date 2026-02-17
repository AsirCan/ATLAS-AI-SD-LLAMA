import React from 'react';
import { Sparkles, Instagram, Film, Image as ImageIcon, Terminal, Hexagon } from 'lucide-react';

const Sidebar = ({ currentMode, setMode, onOpenGallery, isGalleryOpen, lockNavigation = false }) => {

    const navItems = [
        { id: 'chat', icon: Sparkles, label: 'Chat', color: 'text-primary' },
        { id: 'studio', icon: Instagram, label: 'Studio', color: 'text-pink-500' },
        { id: 'video', icon: Film, label: 'Video', color: 'text-red-500' },
    ];

    return (
        <div className="h-full w-20 md:w-24 dark:bg-dark-900/80 bg-white/80 backdrop-blur-xl border-r dark:border-white/5 border-gray-200 flex flex-col items-center py-8 z-50 transition-all duration-300">
            {/* Logo Removed (Moved to Header) */}

            {/* Navigation */}
            <nav className="flex-1 flex flex-col items-center gap-6 w-full">
                {navItems.map((item) => {
                    const isActive = currentMode === item.id;
                    const Icon = item.icon;

                    return (
                        <button
                            key={item.id}
                            onClick={() => setMode(item.id)}
                            disabled={lockNavigation}
                            className={`relative group w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${isActive
                                ? 'dark:bg-white/10 bg-gray-100 dark:text-white text-primary shadow-inner dark:shadow-white/5'
                                : 'text-gray-500 dark:hover:text-white hover:text-primary dark:hover:bg-white/5 hover:bg-gray-50'
                                } ${lockNavigation ? 'opacity-40 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent' : ''}`}
                            title={item.label}
                        >
                            <Icon
                                size={24}
                                className={`transition-all duration-300 ${isActive ? item.color : ''} ${lockNavigation ? '' : 'group-hover:scale-110'}`}
                                strokeWidth={isActive ? 2.5 : 2}
                            />

                            {/* Active Indicator */}
                            {isActive && (
                                <div className="absolute -left-4 w-1 h-8 bg-gradient-to-b from-primary to-accent rounded-r-full"></div>
                            )}

                            {/* Tooltip */}
                            <div className="absolute left-14 px-3 py-1 dark:bg-dark-800 bg-white dark:text-white text-gray-800 text-xs font-bold rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap dark:border border border-white/10 border-gray-200 pointer-events-none z-50 shadow-xl">
                                {lockNavigation ? 'İşlem devam ediyor (kilitli)' : item.label}
                            </div>
                        </button>
                    );
                })}

                <div className="w-8 h-px dark:bg-white/5 bg-gray-200 my-2"></div>

                {/* Gallery Button */}
                <button
                    onClick={onOpenGallery}
                    disabled={lockNavigation}
                    className={`relative group w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 ${isGalleryOpen
                        ? 'dark:bg-white/10 bg-gray-100 dark:text-white text-primary shadow-inner dark:shadow-white/5'
                        : 'text-gray-500 hover:text-accent hover:bg-accent/10'
                        } ${lockNavigation ? 'opacity-40 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent' : ''}`}
                    title="Galeri"
                >
                    <ImageIcon size={24} className={`transition-all duration-300 ${isGalleryOpen ? 'text-accent' : ''} ${lockNavigation ? '' : 'group-hover:scale-110'}`} strokeWidth={isGalleryOpen ? 2.5 : 2} />

                    {/* Active Indicator for Gallery */}
                    {isGalleryOpen && (
                        <div className="absolute -left-4 w-1 h-8 bg-gradient-to-b from-accent to-blue-500 rounded-r-full"></div>
                    )}
                    <div className="absolute left-14 px-3 py-1 dark:bg-dark-800 bg-white dark:text-white text-gray-800 text-xs font-bold rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap dark:border border border-white/10 border-gray-200 pointer-events-none z-50 shadow-xl">
                        {lockNavigation ? 'İşlem devam ediyor (kilitli)' : 'Galeri'}
                    </div>
                </button>
            </nav>

            {/* Bottom Section */}
            <div className="mt-auto flex flex-col items-center gap-4 text-xs text-gray-600 font-mono">
                <div className="group relative">
                    <Terminal size={18} className="hover:text-primary transition-colors cursor-help" />
                    <div className="absolute left-14 bottom-0 px-3 py-1 dark:bg-dark-800 bg-white dark:text-white text-gray-800 text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap dark:border border border-white/10 border-gray-200 pointer-events-none z-50 shadow-xl">
                        v3.0.0
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Sidebar;
