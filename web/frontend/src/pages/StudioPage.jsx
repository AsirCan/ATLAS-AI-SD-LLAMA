import { Camera, Sparkles, RefreshCw, Instagram, Terminal, Upload, Image as ImageIcon } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import InstaConfigModal from '../components/InstaConfigModal';
import LogTerminal from '../components/LogTerminal';

export default function StudioPage() {
    const {
        studioStep, setStudioStep, studioLoading, setStudioLoading,
        generatedNews, setGeneratedNews, isStudioFlow, progress,
        videoStatusText, setVideoStatusText,
        handleGenerateNews, handleInstaUpload,
        setShowInstaLogin, isAgentRunning,
        agentStatusText, agentLogs, agentPercent, agentStage,
        agentCancelRequested, setAgentCancelRequested,
        addToGallery, setAgentStatus, setAgentStatusText: setAgentStatusTextCtx,
    } = useAppContext();

    return (
        <div
            className={`flex-1 p-8 flex flex-col items-center overflow-y-auto ${studioStep === 'generating_agent'
                ? 'justify-start pt-4 pb-8'
                : 'justify-center'
                }`}
        >
            {/* Idle State */}
            {(!isStudioFlow || studioStep === 'idle') && (
                <div className="text-center space-y-6 max-w-lg">
                    <div className="w-24 h-24 bg-gradient-to-tr from-pink-500 to-purple-600 rounded-3xl flex items-center justify-center mx-auto shadow-2xl shadow-pink-500/30">
                        <Camera className="w-12 h-12 text-white" />
                    </div>
                    <h2 className="text-3xl font-bold">Instagram Studio</h2>
                    <p className="text-gray-500 dark:text-gray-400">
                        İster tek görsel, ister 10'lu kaydırmalı (carousel) içerik üret.
                    </p>

                    <div className="flex flex-col gap-4 w-full">
                        <button
                            onClick={() => setShowInstaLogin(true)}
                            disabled={studioLoading || isAgentRunning}
                            className="w-full py-3 rounded-xl border border-gray-300 dark:border-white/10 dark:bg-dark-900 bg-gray-800 text-white hover:bg-gray-700 dark:hover:bg-dark-800 transition-colors font-bold"
                            title="Şifreyi Windows Credential Manager'a kaydeder"
                        >
                            Instagram Giriş (Kaydet)
                        </button>

                        <button
                            onClick={handleGenerateNews}
                            disabled={studioLoading || isAgentRunning}
                            className="bg-white text-dark-900 w-full py-4 rounded-xl font-bold text-lg hover:bg-gray-100 transition-transform active:scale-95 flex items-center justify-center gap-3"
                        >
                            {studioLoading ? <RefreshCw className="animate-spin" /> : <Sparkles />}
                            Günlük Tek İçerik
                        </button>

                        <button
                            onClick={async () => {
                                setStudioLoading(true);
                                setStudioStep('generating_carousel');
                                setGeneratedNews(null);
                                setVideoStatusText('Carousel hazırlanıyor...');

                                try {
                                    const res = await api.generateCarousel();
                                    if (!res?.success) {
                                        alert('Islem baslatilamadi: ' + (res?.error || 'Bilinmeyen hata'));
                                        setStudioStep('idle');
                                        setStudioLoading(false);
                                        return;
                                    }
                                    const interval = setInterval(async () => {
                                        const p = await api.checkCarouselProgress();
                                        if (p.current_task) setVideoStatusText(p.current_task);
                                        if (p.status === 'done') {
                                            clearInterval(interval);
                                            setGeneratedNews(p.result);
                                            if (p.result.images && Array.isArray(p.result.images)) {
                                                p.result.images.forEach(img => addToGallery(img.url, img.prompt));
                                            }
                                            setStudioStep('done_carousel');
                                            setStudioLoading(false);
                                        } else if (p.status === 'error') {
                                            clearInterval(interval);
                                            alert('Carousel Hatası: ' + p.error);
                                            setStudioStep('idle');
                                            setStudioLoading(false);
                                        }
                                    }, 3000);
                                } catch (err) {
                                    alert('Bağlantı Hatası');
                                    setStudioStep('idle');
                                    setStudioLoading(false);
                                }
                            }}
                            disabled={studioLoading || isAgentRunning}
                            className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white w-full py-4 rounded-xl font-bold text-lg hover:shadow-lg transition-transform active:scale-95 flex items-center justify-center gap-3"
                        >
                            {studioLoading ? <RefreshCw className="animate-spin" /> : <Instagram />}
                            10'lu Carousel Oluştur
                        </button>

                        <button
                            onClick={async () => {
                                const isLive = window.confirm("Canlı Modda (Instagram'a Yükle) çalıştırılsın mı?\n\nTamam = Evet (Live)\nİptal = Hayır (Sadece Test/Dry Run)");
                                setStudioLoading(true);
                                setStudioStep('generating_agent');
                                setGeneratedNews(null);
                                setAgentCancelRequested(false);
                                setAgentStatusTextCtx('Ajan başlatılıyor...');
                                try {
                                    const res = await api.runAutonomousAgent(isLive);
                                    if (!res.success) {
                                        alert("Hata: " + res.error);
                                        setStudioLoading(false);
                                        setStudioStep('idle');
                                        return;
                                    }
                                } catch (err) {
                                    alert('Bağlantı Hatası');
                                    setStudioStep('idle');
                                    setStudioLoading(false);
                                } finally {
                                    setStudioLoading(false);
                                }
                            }}
                            disabled={studioLoading || isAgentRunning}
                            className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white w-full py-4 rounded-xl font-bold text-lg hover:shadow-lg transition-transform active:scale-95 flex items-center justify-center gap-3"
                        >
                            {studioLoading ? <RefreshCw className="animate-spin" /> : <Terminal />}
                            Otonom Ajan Başlat
                        </button>
                    </div>
                </div>
            )}

            {/* Instagram Config Modal */}
            <InstaConfigModal />

            {/* Generating Single */}
            {studioStep === 'generating' && (
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 border-4 border-pink-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                    <p className="text-xl font-medium animate-pulse">Yapay zeka çalışıyor...</p>
                    <p className="text-sm text-gray-500">Haberler taranıyor • Prompt yazılıyor • Görsel çiziliyor</p>
                    <div className="w-64 h-2 dark:bg-gray-800 bg-gray-200 rounded-full mt-4 overflow-hidden border dark:border-white/10 border-gray-300 mx-auto">
                        <div className="h-full bg-gradient-to-r from-pink-600 to-purple-600 transition-all duration-300 ease-out" style={{ width: `${progress}%` }}></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2 font-mono">{progress}%</p>
                </div>
            )}

            {/* Generating Carousel */}
            {studioStep === 'generating_carousel' && (
                <div className="text-center space-y-6">
                    <div className="w-20 h-20 relative mx-auto">
                        <div className="absolute inset-0 border-4 border-indigo-500/30 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                        <ImageIcon className="absolute inset-0 m-auto text-indigo-500 animate-pulse" size={32} />
                    </div>
                    <div className="space-y-2">
                        <p className="text-2xl font-bold animate-pulse dark:text-white text-gray-900">{videoStatusText || "Carousel Hazırlanıyor..."}</p>
                        <p className="text-sm dark:text-gray-400 text-gray-500">10 farklı görsel oluşturuluyor. Bu işlem birkaç dakika sürebilir.</p>
                    </div>
                </div>
            )}

            {/* Agent Progress */}
            {studioStep === 'generating_agent' && (
                <div className="w-full max-w-[1200px] flex flex-col items-center space-y-6">
                    <div className="w-full space-y-4 z-20 rounded-2xl border dark:border-white/10 border-gray-200 dark:bg-[#070b16]/70 bg-white/80 backdrop-blur-md p-4 md:p-5 shadow-2xl">
                        <div className="text-center space-y-2">
                            <p className="text-2xl font-bold dark:text-white text-gray-900">Yapay Zeka Ajanı Çalışıyor</p>
                            <p className="text-sm dark:text-gray-400 text-gray-500">{agentStatusText || "Durum alınıyor..."}</p>
                        </div>

                        <div className="flex items-center justify-center gap-3">
                            <button
                                onClick={async () => {
                                    const ok = window.confirm("Ajanı iptal etmek istiyor musun?\n\nNot: Eğer şu an görsel çiziyorsa, güvenli durdurma adım bitince gerçekleşir.");
                                    if (!ok) return;
                                    setAgentCancelRequested(true);
                                    await api.cancelAgent();
                                }}
                                disabled={!isAgentRunning || agentCancelRequested}
                                className={`px-4 py-2 rounded-xl font-bold border transition-all ${agentCancelRequested
                                    ? 'dark:bg-gray-800 bg-gray-200 dark:text-gray-400 text-gray-500 dark:border-white/10 border-gray-300 cursor-not-allowed'
                                    : 'bg-red-600 hover:bg-red-700 text-white border-red-500/30'
                                    }`}
                                title="Ajanı güvenli şekilde durdur"
                            >
                                {agentCancelRequested ? 'İptal İstendi' : 'İptal Et'}
                            </button>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full h-2 dark:bg-gray-800 bg-gray-200 rounded-full overflow-hidden border dark:border-white/10 border-gray-300">
                            <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-300 ease-out" style={{ width: `${Math.max(0, Math.min(100, agentPercent))}%` }}></div>
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500 font-mono">
                            <span>stage: {agentStage}</span>
                            <span>{agentPercent}%</span>
                        </div>

                        {/* Step List */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                            {[
                                { id: 'services_check', label: 'Servisler (Ollama/SD)' },
                                { id: 'init', label: 'Ajanlar hazırlanıyor' },
                                { id: 'news', label: 'Haber toplama' },
                                { id: 'risk', label: 'Risk analizi' },
                                { id: 'visual', label: 'Görsel üretimi' },
                                { id: 'caption', label: 'Caption üretimi' },
                                { id: 'schedule', label: 'Zamanlama' },
                                { id: 'publish', label: 'Yayınlama/Dry Run' },
                            ].map(step => {
                                const active = agentStage === step.id || (agentStage === 'running' && ['news', 'risk', 'visual', 'caption', 'schedule', 'publish'].includes(step.id));
                                const done = agentPercent >= 100 || ['done'].includes(agentStage);
                                return (
                                    <div
                                        key={step.id}
                                        className={`px-3 py-2 rounded-xl border ${active
                                            ? 'bg-emerald-500/10 border-emerald-500/30 dark:text-emerald-200 text-emerald-700'
                                            : 'dark:bg-dark-900/40 bg-gray-100 dark:border-white/10 border-gray-200 dark:text-gray-400 text-gray-500'
                                            }`}
                                    >
                                        <span className="font-mono text-xs opacity-70">{step.id}</span>
                                        <div className="font-semibold">{step.label}{done && agentStage === 'done' ? '' : ''}</div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <LogTerminal logs={agentLogs} className="w-full" />
                </div>
            )}

            {/* Carousel Done View */}
            {(studioStep === 'done_carousel' || studioStep === 'uploading_carousel' || studioStep === 'uploaded_carousel') && generatedNews && generatedNews.images && (
                <div className="w-full h-full flex flex-col gap-6">
                    <div className="flex-1 overflow-x-auto overflow-y-hidden flex gap-4 p-4 items-center scrollbar-thin scrollbar-thumb-white/20 pb-8">
                        {generatedNews.images.map((img, idx) => (
                            <div key={idx} className="flex flex-col gap-4 min-w-[300px] md:min-w-[400px] flex-shrink-0 snap-center">
                                <div className="w-full aspect-square relative group rounded-2xl overflow-hidden shadow-2xl border dark:border-white/10 border-gray-200 dark:bg-dark-800 bg-gray-50">
                                    <img src={img.url} alt={`Slide ${idx + 1}`} className="w-full h-full object-cover" />
                                    <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded-full backdrop-blur-md font-mono border border-white/10 z-10">
                                        {idx + 1}/10
                                    </div>
                                    <div className="absolute inset-0 bg-black/90 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center p-6 text-center cursor-help">
                                        <p className="text-[10px] text-purple-400 font-mono tracking-widest mb-2 uppercase">Stable Diffusion Prompt</p>
                                        <p className="text-sm text-gray-300 font-medium leading-relaxed line-clamp-[10]">{img.prompt}</p>
                                    </div>
                                </div>
                                <div className="text-center px-4">
                                    <p className="text-white font-bold tracking-widest text-lg uppercase bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent">
                                        {img.title || `SLIDE ${idx + 1}`}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="dark:bg-dark-900 bg-white p-6 rounded-2xl border dark:border-white/10 border-gray-200 shadow-xl flex gap-6 items-start mx-auto w-full max-w-4xl">
                        <div className="flex-1">
                            <h3 className="text-sm dark:text-gray-400 text-gray-500 uppercase tracking-wider mb-2 font-bold">Carousel Açıklaması</h3>
                            <p className="text-base leading-relaxed whitespace-pre-wrap font-medium dark:text-gray-200 text-gray-700">
                                {generatedNews.caption}
                            </p>
                        </div>

                        <div className="flex flex-col gap-2 shrink-0">
                            <button
                                onClick={() => { setStudioStep('idle'); setGeneratedNews(null); }}
                                className="px-6 py-3 rounded-xl border dark:border-white/10 border-gray-200 dark:bg-dark-800 bg-gray-100 dark:hover:bg-dark-700 hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                            >
                                <RefreshCw size={18} />
                                Yeni Yap
                            </button>

                            <button
                                onClick={handleInstaUpload}
                                disabled={studioLoading || studioStep === 'uploaded_carousel'}
                                className={`px-6 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${studioStep === 'uploaded_carousel'
                                    ? 'bg-green-500 text-white'
                                    : 'bg-gradient-to-r from-pink-500 to-purple-600 hover:shadow-lg hover:shadow-pink-500/25 text-white'
                                    }`}
                                title="Instagram'a Yükle"
                            >
                                {studioLoading ? <RefreshCw className="animate-spin" /> : (studioStep === 'uploaded_carousel' ? 'Yüklendi' : 'Instagram\'a Yükle')}
                                {studioStep !== 'uploaded_carousel' && <Upload size={18} />}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Single Image Review */}
            {generatedNews && (studioStep === 'review' || studioStep === 'uploading' || studioStep === 'done') && (
                <div className="w-full max-w-6xl grid md:grid-cols-2 gap-8 items-stretch animate-fade-in relative z-10">
                    <div className="flex flex-col h-full">
                        <div className="relative group rounded-2xl overflow-hidden shadow-2xl border dark:border-white/10 border-gray-200 h-full">
                            <img src={generatedNews.image_url} alt="Generated" className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <a href={generatedNews.image_url} target="_blank" className="text-white underline font-bold px-6 py-3 bg-black/50 rounded-xl backdrop-blur-md border border-white/10 hover:bg-white/10 transition-colors">Tam Boyut Gör</a>
                            </div>
                            {generatedNews.duration && (
                                <div className="absolute top-4 right-4 bg-black/60 text-white text-xs px-3 py-1.5 rounded-full backdrop-blur-md font-mono border border-white/10 z-20">
                                    ⏱️ {generatedNews.duration}s
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div className="dark:bg-dark-900 bg-white p-6 rounded-2xl border dark:border-white/10 border-gray-200 relative z-10 shadow-xl">
                            <h3 className="text-sm dark:text-gray-400 text-gray-500 uppercase tracking-wider mb-2 font-bold">Instagram için Oluşturulan Açıklama</h3>
                            <p className="text-lg leading-relaxed whitespace-pre-wrap font-medium dark:text-gray-200 text-gray-700">
                                {generatedNews.caption}
                            </p>
                        </div>

                        <div className="dark:bg-dark-900 bg-gray-50 p-4 rounded-xl border dark:border-white/5 border-gray-200 text-sm text-gray-500 relative z-10">
                            <p><strong className="dark:text-gray-400 text-gray-600">Kaynak Haberler:</strong></p>
                            <p className="italic mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap scrollbar-thin scrollbar-thumb-white/10">{generatedNews.news_summary}</p>
                        </div>

                        <div className="dark:bg-dark-900 bg-gray-50 p-4 rounded-xl border dark:border-white/5 border-gray-200 text-sm text-gray-500 shadow-inner relative z-10">
                            <p><strong className="text-purple-400 flex items-center gap-2"><Sparkles size={12} /> LLM Prompt:</strong></p>
                            <p className="italic mt-1 max-h-32 overflow-y-auto font-mono text-xs whitespace-pre-wrap scrollbar-thin scrollbar-thumb-white/10 dark:text-gray-400 text-gray-500">
                                {generatedNews.prompt}
                            </p>
                        </div>

                        <div className="flex gap-4">
                            <button
                                onClick={handleGenerateNews}
                                disabled={studioLoading || isAgentRunning}
                                className="flex-1 py-3 rounded-xl border dark:border-white/10 border-gray-200 dark:bg-dark-900 bg-gray-100 dark:hover:bg-dark-800 hover:bg-gray-200 transition-colors flex items-center justify-center gap-2 relative z-20"
                            >
                                <RefreshCw size={18} />
                                Yeniden Dene
                            </button>
                            <button
                                onClick={handleInstaUpload}
                                disabled={studioLoading || studioStep === 'done'}
                                className={`flex-1 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${studioStep === 'done'
                                    ? 'bg-green-500 text-white'
                                    : 'bg-gradient-to-r from-pink-500 to-purple-600 hover:shadow-lg hover:shadow-pink-500/25'
                                    }`}
                            >
                                {studioLoading ? <RefreshCw className="animate-spin" /> : (studioStep === 'done' ? 'Yüklendi' : 'Instagram\'a Yükle')}
                                {studioStep !== 'done' && <Upload size={18} />}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
