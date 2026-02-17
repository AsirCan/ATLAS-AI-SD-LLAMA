import { Film, RefreshCw } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';

export default function VideoPage() {
    const {
        studioStep, setStudioStep, studioLoading, setStudioLoading,
        generatedNews, setGeneratedNews, isVideoFlow,
        videoStatusText, setVideoStatusText, videoPercent, setVideoPercent,
        isAgentRunning,
    } = useAppContext();

    return (
        <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-6 overflow-y-auto">
            {/* Idle */}
            {!isVideoFlow && (
                <>
                    <div className="w-24 h-24 bg-gradient-to-tr from-red-600 to-orange-600 rounded-3xl flex items-center justify-center mx-auto shadow-2xl shadow-red-500/30">
                        <Film className="w-12 h-12 text-white" />
                    </div>
                    <h2 className="text-3xl font-bold">Gündem Özeti Videosu</h2>
                    <p className="dark:text-gray-400 text-gray-500 max-w-md mx-auto">
                        Otomatik olarak 3 haber seçilir, kare görseller üretilir ve İngilizce haber anlatımıyla video oluşturulur.
                    </p>
                    <div className="p-6 dark:bg-dark-900 bg-white rounded-xl border dark:border-white/10 border-gray-200 max-w-lg mx-auto w-full relative z-10 shadow-2xl space-y-4">
                        <div className="flex items-center gap-2 text-sm dark:text-gray-400 text-gray-500 justify-center">
                            <span>• 3 Haber</span>
                            <span>• English Voice</span>
                            <span>• 30-40 Saniye</span>
                        </div>
                        <button
                            onClick={async () => {
                                setStudioLoading(true);
                                setStudioStep('generating_video');
                                setGeneratedNews(null);
                                setVideoStatusText('Haber videosu hazırlanıyor...');
                                setVideoPercent(2);
                                try {
                                    const res = await api.generateNewsVideo();
                                    if (!res.success) {
                                        alert('Hata: ' + res.error);
                                        setStudioStep('idle');
                                        setVideoPercent(0);
                                        setStudioLoading(false);
                                        return;
                                    }
                                    const interval = setInterval(async () => {
                                        const p = await api.checkNewsVideoProgress();
                                        if (p.current_task) setVideoStatusText(p.current_task);
                                        if (typeof p.percent === 'number') setVideoPercent(Math.max(0, Math.min(100, p.percent)));
                                        if (p.status === 'done') {
                                            clearInterval(interval);
                                            setGeneratedNews({ video_url: p.result });
                                            setStudioStep('done_video');
                                            setVideoPercent(100);
                                            setStudioLoading(false);
                                        } else if (p.status === 'error') {
                                            clearInterval(interval);
                                            alert('Video Hatası: ' + p.error);
                                            setStudioStep('idle');
                                            setVideoPercent(0);
                                            setStudioLoading(false);
                                        }
                                    }, 2000);
                                } catch (err) {
                                    alert('Bağlantı Hatası');
                                    setStudioStep('idle');
                                    setVideoPercent(0);
                                    setStudioLoading(false);
                                }
                            }}
                            disabled={studioLoading || isAgentRunning}
                            className="w-full py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold transition-colors flex items-center justify-center gap-2"
                        >
                            {studioLoading ? <RefreshCw className="animate-spin" /> : <Film />}
                            Video Oluştur
                        </button>
                    </div>
                </>
            )}

            {/* Generating */}
            {studioStep === 'generating_video' && (
                <div className="text-center space-y-6">
                    <div className="w-20 h-20 relative mx-auto">
                        <div className="absolute inset-0 border-4 border-red-500/30 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-red-500 border-t-transparent rounded-full animate-spin"></div>
                        <Film className="absolute inset-0 m-auto text-red-500 animate-pulse" size={32} />
                    </div>
                    <div className="space-y-2">
                        <p className="text-2xl font-bold animate-pulse dark:text-white text-gray-900">{videoStatusText || "Haber Videosu Hazırlanıyor..."}</p>
                        <p className="text-sm dark:text-gray-400 text-gray-500">Bu işlem yapay zeka modelleri (LLM, SD, TTS) kullandığı için 1-2 dakika sürebilir.</p>
                    </div>
                    <div className="w-64 mx-auto dark:bg-dark-800 bg-gray-200 rounded-full h-2 overflow-hidden border dark:border-white/10 border-gray-300">
                        <div className="h-full bg-gradient-to-r from-red-600 to-orange-500 transition-all duration-500" style={{ width: `${Math.max(2, videoPercent)}%` }} />
                    </div>
                    <p className="text-xs dark:text-gray-400 text-gray-500">{Math.max(0, Math.min(100, Math.round(videoPercent)))}%</p>
                </div>
            )}

            {/* Done */}
            {studioStep === 'done_video' && generatedNews && (
                <div className="w-full max-w-md mx-auto space-y-4 animate-fade-in relative z-10">
                    <div className="dark:bg-dark-900 bg-white rounded-2xl p-2 border dark:border-white/10 border-gray-200 shadow-2xl">
                        <video
                            src={generatedNews.video_url}
                            controls
                            autoPlay
                            className="w-full rounded-xl aspect-square object-contain bg-black"
                        ></video>
                    </div>
                    <button
                        onClick={() => {
                            setStudioStep('idle');
                            setGeneratedNews(null);
                        }}
                        className="dark:text-gray-400 text-gray-500 dark:hover:text-white hover:text-gray-900 underline text-sm"
                    >
                        Yeni Video Oluştur
                    </button>
                </div>
            )}
        </div>
    );
}
