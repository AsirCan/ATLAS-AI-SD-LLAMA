import { Palette, X } from 'lucide-react';
import { useAppContext } from '../context/AppContext';

export default function DrawModal() {
    const { showDrawModal, setShowDrawModal, drawPrompt, setDrawPrompt, handleDrawSubmit } = useAppContext();

    if (!showDrawModal) return null;

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
            <div className="dark:bg-dark-800 bg-white border dark:border-white/10 border-gray-200 rounded-3xl p-6 w-full max-w-md shadow-2xl scale-in">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-xl font-bold flex items-center gap-2 dark:text-white text-gray-900">
                        <Palette className="text-pink-500" />
                        Resim Çiz
                    </h3>
                    <button onClick={() => setShowDrawModal(false)} className="text-gray-400 dark:hover:text-white hover:text-gray-900">
                        <X size={24} />
                    </button>
                </div>
                <div className="space-y-4">
                    <p className="dark:text-gray-400 text-gray-500 text-sm">Hayalindeki görseli tarif et, yapay zeka senin için çizsin.</p>
                    <textarea
                        className="w-full dark:bg-dark-900/50 bg-gray-50 border dark:border-white/10 border-gray-300 rounded-xl p-4 dark:text-white text-gray-900 focus:border-pink-500 focus:outline-none min-h-[120px] resize-none"
                        placeholder="Örn: Uzayda süzülen kırmızı bir spor araba, cyberpunk tarzı..."
                        value={drawPrompt}
                        onChange={(e) => setDrawPrompt(e.target.value)}
                        autoFocus
                    ></textarea>
                    <button
                        onClick={handleDrawSubmit}
                        disabled={!drawPrompt.trim()}
                        className={`w-full py-3 rounded-xl font-bold text-lg transition-all ${drawPrompt.trim()
                            ? 'bg-gradient-to-r from-pink-600 to-purple-600 text-white hover:shadow-lg hover:shadow-pink-500/25'
                            : 'dark:bg-white/5 bg-gray-100 text-gray-500 cursor-not-allowed'
                            }`}
                    >
                        Çizimi Başlat
                    </button>
                </div>
            </div>
        </div>
    );
}
