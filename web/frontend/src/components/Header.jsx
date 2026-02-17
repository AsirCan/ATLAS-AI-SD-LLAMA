import { Hexagon, Sun, Moon } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { ClockWidget, SystemWidget } from './Widgets';

export default function Header() {
    const { theme, toggleTheme } = useAppContext();

    return (
        <header className="w-full h-20 flex items-center justify-between px-6 z-50 dark:bg-dark-900/80 bg-white/80 backdrop-blur-3xl dark:border-white/5 border-gray-200 border-b shrink-0 relative transition-colors duration-300">
            {/* Logo & Brand */}
            <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-all duration-300">
                    <Hexagon className="w-5 h-5 text-white" />
                </div>
                <div className="text-2xl font-bold tracking-widest dark:text-white/90 text-gray-800 font-mono flex items-center gap-3">
                    <div className="w-1 h-6 dark:bg-white/10 bg-gray-300 rounded-full"></div>
                    ATLAS AI
                </div>
            </div>

            {/* Widgets */}
            <div className="flex items-center gap-4">
                <button
                    onClick={toggleTheme}
                    className="p-2 rounded-xl dark:bg-white/5 bg-gray-100 dark:text-gray-400 text-gray-600 dark:hover:text-white hover:text-primary transition-all hover:scale-105 active:scale-95"
                    title={theme === 'dark' ? 'Aydınlık Mod' : 'Karanlık Mod'}
                >
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>
                <div className="hidden md:block w-px h-8 dark:bg-white/10 bg-gray-200"></div>
                <ClockWidget />
                <SystemWidget />
            </div>
        </header>
    );
}
