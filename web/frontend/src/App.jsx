import React, { useState, useRef, useEffect } from 'react';
import { Mic, Send, Image as ImageIcon, StopCircle, RefreshCw, Volume2, Sparkles, User, Terminal, Instagram, Camera, Upload, Palette, X, Film, Hexagon, Sun, Moon } from 'lucide-react';
import { api } from './api';
import AudioVisualizer from './components/AudioVisualizer';
import GallerySidebar from './components/GallerySidebar';
import Sidebar from './components/Sidebar';
import { ClockWidget, SystemWidget } from './components/Widgets';
import InteractiveBackground from './components/InteractiveBackground';
import LogTerminal from './components/LogTerminal';
import './index.css';

function App() {
    const [messages, setMessages] = useState([
        { role: 'ai', content: 'Merhaba! Ben Atlas. Size nasıl yardımcı olabilirim? Bugün neler üretmek istersiniz?' }
    ]);
    const [input, setInput] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const scrollRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const [audioChunks, setAudioChunks] = useState([]);

    // News/Studio/Video Mode State
    const [appMode, setAppMode] = useState('chat'); // 'chat', 'studio', 'video'
    const [generatedNews, setGeneratedNews] = useState(null); // { image_url, caption, image_path }
    const [studioLoading, setStudioLoading] = useState(false);
    const [studioStep, setStudioStep] = useState('idle'); // idle, generating, review, uploading, done
    const [progress, setProgress] = useState(0);
    const [videoStatusText, setVideoStatusText] = useState('');
    const [agentLogs, setAgentLogs] = useState([]);
    const [agentPercent, setAgentPercent] = useState(0);
    const [agentStage, setAgentStage] = useState('idle');
    const [agentStatus, setAgentStatus] = useState('idle'); // idle | running | done | error
    const [agentCancelRequested, setAgentCancelRequested] = useState(false);
    const [showInstaLogin, setShowInstaLogin] = useState(false);
    const [instaUser, setInstaUser] = useState('');
    const [instaPass, setInstaPass] = useState('');

    const isAgentRunning = agentStatus === 'running';
    const setAppModeSafe = (nextMode) => {
        if (isAgentRunning) return;
        setAppMode(nextMode);
    };

    // Reset state when mode changes
    useEffect(() => {
        setStudioStep('idle');
        setGeneratedNews(null);
        setVideoStatusText('');
        setStudioLoading(false);

        // Don't wipe agent UI state while agent is still running in background.
        if (!isAgentRunning) {
            setAgentLogs([]);
            setAgentPercent(0);
            setAgentStage('idle');
            setAgentStatus('idle');
            setAgentCancelRequested(false);
        }
    }, [appMode, isAgentRunning]);

    // Keep agent progress visible even after navigation
    useEffect(() => {
        let interval;

        const tick = async () => {
            try {
                const p = await api.checkAgentProgress();

                if (p?.status) setAgentStatus(p.status);
                if (p?.current_task) setVideoStatusText(p.current_task);
                if (typeof p?.percent === 'number') setAgentPercent(p.percent);
                if (p?.stage) setAgentStage(p.stage);
                if (p?.logs && Array.isArray(p.logs)) setAgentLogs(p.logs);
                if (p?.cancel_requested) setAgentCancelRequested(true);

                // If user comes back to Studio while the agent is still running,
                // automatically restore the agent progress screen.
                if (appMode === 'studio' && p?.status === 'running') {
                    setStudioStep('generating_agent');
                }
            } catch {
                // ignore polling errors; UI will keep last known state
            }
        };

        // Always fetch once on entry to Studio (or while running)
        if (appMode === 'studio' || isAgentRunning) {
            tick();
            interval = setInterval(tick, 1000);
        }

        return () => clearInterval(interval);
    }, [appMode, isAgentRunning]);

    // Drawing Modal State
    const [showDrawModal, setShowDrawModal] = useState(false);
    const [drawPrompt, setDrawPrompt] = useState('');

    // Gallery State
    const [galleryOpen, setGalleryOpen] = useState(false);
    const [galleryImages, setGalleryImages] = useState([]);

    const addToGallery = (url, prompt) => {
        setGalleryImages(prev => [{ url, prompt }, ...prev]);
    };

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const [theme, setTheme] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('theme') || 'dark';
        }
        return 'dark';
    });

    useEffect(() => {
        const root = window.document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };



    useEffect(() => {
        let interval;
        if (studioStep === 'generating') {
            interval = setInterval(async () => {
                const p = await api.checkProgress();
                if (p && p.progress) {
                    setProgress(Math.round(p.progress * 100));
                }
            }, 1000);
        } else {
            setProgress(0);
        }
        return () => clearInterval(interval);
    }, [studioStep]);

    const addMessage = (role, content, image = null, duration = null) => {
        setMessages(prev => [...prev, { role, content, image, duration }]);
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const text = input;
        setInput('');
        addMessage('user', text);
        setIsProcessing(true);

        try {
            const lowerText = text.toLowerCase();
            if (lowerText.includes('çiz') || lowerText.includes('oluştur') || lowerText.includes('resim')) {
                const res = await api.generateImage(text);
                if (res.success) {
                    addMessage('ai', `"${res.original}" için görseliniz hazır:`, res.image_url, res.duration);
                    addToGallery(res.image_url, res.original);
                } else {
                    addMessage('ai', 'Üzgünüm, resim oluştururken bir hata oldu.');
                }
            } else {
                const res = await api.chat(text);
                addMessage('ai', res.response);
            }
        } catch (error) {
            addMessage('ai', 'Bir bağlantı hatası oluştu. Lütfen backend sunucusunun açık olduğundan emin olun.');
        } finally {
            setIsProcessing(false);
        }
    };

    const [audioStream, setAudioStream] = useState(null);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setAudioStream(stream); // Pass to Visualizer
            mediaRecorderRef.current = new MediaRecorder(stream);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };

            mediaRecorderRef.current.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
                setIsProcessing(true);

                // Cleanup stream tracks
                stream.getTracks().forEach(track => track.stop());
                setAudioStream(null);

                try {
                    const res = await api.stt(audioBlob);
                    if (res.text) {
                        // setInput(res.text); // User requested not to show text in input
                        addMessage('user', res.text);

                        // Check for image generation keyword even in voice
                        const lowerText = res.text.toLowerCase();
                        if (lowerText.includes('çiz') || lowerText.includes('oluştur') || lowerText.includes('resim')) {
                            const imgRes = await api.generateImage(res.text);
                            if (imgRes.success) {
                                addMessage('ai', `"${imgRes.original}" için görseliniz hazır:`, imgRes.image_url, imgRes.duration);
                                addToGallery(imgRes.image_url, imgRes.original);
                            } else {
                                addMessage('ai', 'Resim oluşturma başarısız oldu.');
                            }
                        } else {
                            const chatRes = await api.chat(res.text);
                            addMessage('ai', chatRes.response);
                            handleTTS(chatRes.response, 'voice_auto');
                        }
                    } else {
                        // Silence
                    }
                } catch (err) {
                    console.error(err);
                } finally {
                    setIsProcessing(false);
                }
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error('Mic Access Error:', err);
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                alert('Mikrofon izni reddedildi. Lütfen tarayıcı adres çubuğundaki kilit simgesine tıklayıp mikrofona izin verin.');
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                alert('Mikrofon bulunamadı. Lütfen mikrofonunuzun takılı olduğundan emin olun.');
            } else {
                alert(`Mikrofon hatası: ${err.name} - ${err.message}`);
            }
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const [currentAudio, setCurrentAudio] = useState(null);
    const [playingMsgIndex, setPlayingMsgIndex] = useState(null);
    const [ttsLoading, setTtsLoading] = useState(false);

    const handleTTS = async (text, index) => {
        if (!text) return;

        // Toggle logic: If clicking the same message that is playing, stop it.
        if (playingMsgIndex === index) {
            if (currentAudio) {
                currentAudio.pause();
                currentAudio.currentTime = 0;
            }
            setCurrentAudio(null);
            setPlayingMsgIndex(null);
            return;
        }

        // Prevent spamming: If a request is already in flight, ignore new clicks
        if (ttsLoading) return;

        // Stop any currently playing audio (switching to new one)
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            setCurrentAudio(null);
            setPlayingMsgIndex(null);
        }

        try {
            setTtsLoading(true);
            // Set loading state for specific message if needed, but for now we rely on the fact 
            // that we haven't set the playing index yet, so it won't show stop icon until audio is ready.
            // Or we could use a separate 'loadingAudioIndex' state.

            const blob = await api.tts(text);
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);

            audio.onended = () => {
                setPlayingMsgIndex(null);
                setCurrentAudio(null);
            };

            // Handle errors during playback
            audio.onerror = () => {
                console.error("Audio playback error");
                setPlayingMsgIndex(null);
                setCurrentAudio(null);
            };

            await audio.play();
            setCurrentAudio(audio);
            setPlayingMsgIndex(index);

        } catch (err) {
            console.error("TTS Error", err);
            setPlayingMsgIndex(null);
            setCurrentAudio(null);
        } finally {
            setTtsLoading(false);
        }
    };

    // --- DRAWING HANDLER ---
    const handleDrawOpen = () => {
        setShowDrawModal(true);
    };

    const handleDrawSubmit = async () => {
        if (!drawPrompt.trim()) return;
        setShowDrawModal(false);
        const prompt = drawPrompt;
        setDrawPrompt('');

        addMessage('user', `🎨 Çizim isteği: ${prompt}`);
        setIsProcessing(true);

        try {
            const res = await api.generateImage(prompt);
            if (res.success) {
                addMessage('ai', `"${res.original}" için görseliniz hazır:`, res.image_url, res.duration);
                addToGallery(res.image_url, res.original);
            } else {
                addMessage('ai', 'Üzgünüm, çizim oluşturulurken bir hata oldu.');
            }
        } catch (err) {
            addMessage('ai', 'Hata: Backend bağlantısı kurulamadı.');
        } finally {
            setIsProcessing(false);
        }
    };

    const handleGenerateNews = async () => {
        setStudioLoading(true);
        setStudioStep('generating');
        setGeneratedNews(null);
        setProgress(0);
        try {
            const res = await api.generateNewsImage();
            if (res.success) {
                setGeneratedNews(res);
                addToGallery(res.image_url, res.prompt);
                setStudioStep('review');
            } else {
                alert('Hata: ' + res.error);
                setStudioStep('idle');
            }
        } catch (err) {
            console.error(err);
            alert('Bağlantı hatası: Stabil Diffusion veya Backend açık mı?');
            setStudioStep('idle');
        } finally {
            setStudioLoading(false);
        }
    };

    const handleInstaUpload = async () => {
        if (!generatedNews) return;
        setStudioLoading(true);
        try {
            // MODE 1: CAROUSEL
            if (generatedNews.images && Array.isArray(generatedNews.images)) {
                const paths = generatedNews.images.map(img => img.path);
                const res = await api.uploadCarouselToInstagram(paths, generatedNews.caption);
                if (res.success) {
                    alert('Carousel başarıyla Instagram\'a yüklendi! 🎉');
                    setStudioStep('done_carousel');
                    // setGeneratedNews(null); // Keep data for view
                } else {
                    alert('Yükleme Hatası: ' + res.message);
                }
            }
            // MODE 2: SINGLE IMAGE
            else if (generatedNews.image_path) {
                const res = await api.uploadToInstagram(generatedNews.image_path, generatedNews.caption);
                if (res.success) {
                    alert('Başarıyla Instagram\'a yüklendi!');
                    setStudioStep('done');
                    // setGeneratedNews(null); // Keep data for view
                } else {
                    alert('Yükleme Hatası: ' + res.message);
                }
            }
        } catch (err) {
            console.error(err);
            alert('Yükleme sırasında hata oluştu.');
        } finally {
            setStudioLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="h-screen w-full dark:bg-dark-900 bg-gray-50 dark:text-white text-gray-900 font-sans selection:bg-primary/30 overflow-hidden relative flex flex-col transition-colors duration-300">

            {/* Background Layers */}
            <div className="dark:block hidden bg-living-data"></div>
            <InteractiveBackground theme={theme} />

            {/* Top Header (Full Width) */}
            <header className="w-full h-20 flex items-center justify-between px-6 z-50 dark:bg-dark-900/80 bg-white/80 backdrop-blur-3xl dark:border-white/5 border-gray-200 border-b shrink-0 relative transition-colors duration-300">
                {/* Logo & Brand */}
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-all duration-300">
                        <Hexagon className="w-5 h-5 text-white" />
                    </div>
                    <div className="text-2xl font-bold tracking-widest dark:text-white/90 text-gray-800 font-mono flex items-center gap-3">
                        <div className="w-1 h-6 bg-white/10 rounded-full"></div>
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

            {/* Main Layout (Sidebar + Content) */}
            <div className="flex-1 flex relative z-10 overflow-hidden">

                {/* Sidebar */}
                <Sidebar
                    currentMode={appMode}
                    setMode={setAppModeSafe}
                    isGalleryOpen={galleryOpen}
                    onOpenGallery={() => setGalleryOpen(prev => !prev)}
                    lockNavigation={isAgentRunning}
                />

                {/* Content Area */}
                <div className="flex-1 flex flex-col relative h-full overflow-hidden">

                    {/* Content */}
                    <main className="flex-1 flex flex-col relative z-10 p-6 md:p-10 h-full">

                        {/* Mode Title (Optional Visual Anchor) */}
                        {/* <div className="mb-4">
                        <h2 className="text-2xl font-black text-white/10 uppercase tracking-widest">{appMode}</h2>
                     </div> */}

                        {appMode === 'studio' ? (
                            // --- STUDIO MODE UI ---
                            <div className="flex-1 p-8 flex flex-col items-center justify-center overflow-y-auto">
                                {!generatedNews && studioStep === 'idle' && (
                                    <div className="text-center space-y-6 max-w-lg">
                                        <div className="w-24 h-24 bg-gradient-to-tr from-pink-500 to-purple-600 rounded-3xl flex items-center justify-center mx-auto shadow-2xl shadow-pink-500/30">
                                            <Camera className="w-12 h-12 text-white" />
                                        </div>
                                        <h2 className="text-3xl font-bold">Instagram Studio</h2>
                                        <p className="text-gray-400">
                                            İster tek görsel, ister 10'lu kaydırmalı (carousel) içerik üret.
                                        </p>

                                        <div className="flex flex-col gap-4 w-full">
                                            <button
                                                onClick={() => setShowInstaLogin(true)}
                                                disabled={studioLoading || isAgentRunning}
                                                className="w-full py-3 rounded-xl border border-white/10 bg-dark-900 hover:bg-dark-800 transition-colors font-bold"
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

                                                    try {
                                                        const res = await api.generateCarousel();
                                                        // Poll for progress
                                                        const interval = setInterval(async () => {
                                                            const p = await api.checkCarouselProgress();

                                                            if (p.current_task) {
                                                                setVideoStatusText(p.current_task);
                                                            }

                                                            if (p.status === 'done') {
                                                                clearInterval(interval);
                                                                setGeneratedNews(p.result); // { images: [], caption }

                                                                // Add all images to gallery
                                                                if (p.result.images && Array.isArray(p.result.images)) {
                                                                    p.result.images.forEach(img => {
                                                                        addToGallery(img.url, img.prompt);
                                                                    });
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
                                                    // Ask for confirmation (Live or Test)
                                                    const isLive = window.confirm("Canlı Modda (Instagram'a Yükle) çalıştırılsın mı?\n\nTamam = Evet (Live)\nİptal = Hayır (Sadece Test/Dry Run)");

                                                    setStudioLoading(true);
                                                    setStudioStep('generating_agent'); // New step for simple generic progress
                                                    setGeneratedNews(null);
                                                    setAgentCancelRequested(false);

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
                                                        // Global poller handles progress updates; we only stop the "starting" spinner here.
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

                                {/* Instagram Login Modal */}
                                {showInstaLogin && (
                                    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
                                        <div className="bg-dark-800 border border-white/10 rounded-3xl p-6 w-full max-w-md shadow-2xl scale-in">
                                            <div className="flex justify-between items-center mb-4">
                                                <h3 className="text-xl font-bold">Instagram Giriş</h3>
                                                <button onClick={() => setShowInstaLogin(false)} className="text-gray-400 hover:text-white">
                                                    <X size={24} />
                                                </button>
                                            </div>
                                            <div className="space-y-3 text-left">
                                                <p className="text-sm text-gray-400">
                                                    Şifre projeye yazılmaz. Windows Credential Manager'a kaydedilir.
                                                </p>
                                                <input
                                                    className="w-full bg-dark-900/50 border border-white/10 rounded-xl p-3 text-white focus:border-emerald-500 focus:outline-none"
                                                    placeholder="Kullanıcı adı"
                                                    value={instaUser}
                                                    onChange={(e) => setInstaUser(e.target.value)}
                                                />
                                                <input
                                                    type="password"
                                                    className="w-full bg-dark-900/50 border border-white/10 rounded-xl p-3 text-white focus:border-emerald-500 focus:outline-none"
                                                    placeholder="Şifre"
                                                    value={instaPass}
                                                    onChange={(e) => setInstaPass(e.target.value)}
                                                />
                                                <div className="flex gap-3 pt-2">
                                                    <button
                                                        onClick={async () => {
                                                            if (!instaUser.trim() || !instaPass) return;
                                                            const res = await api.saveInstagramCredentials(instaUser.trim(), instaPass);
                                                            if (res?.success) {
                                                                // Also reset session so next upload forces fresh login
                                                                await api.resetInstagramSession();
                                                                setInstaPass('');
                                                                setShowInstaLogin(false);
                                                                alert('Kaydedildi. Oturum sıfırlandı. Bir sonraki upload taze login ile yapılacak.');
                                                            } else {
                                                                alert('Hata: ' + (res?.error || 'Kaydedilemedi'));
                                                            }
                                                        }}
                                                        className="flex-1 py-3 rounded-xl font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
                                                    >
                                                        Kaydet
                                                    </button>
                                                    <button
                                                        onClick={async () => {
                                                            const ok = window.confirm("Instagram oturum dosyası (insta_session.json) sıfırlansın mı?");
                                                            if (!ok) return;
                                                            const res = await api.resetInstagramSession();
                                                            alert(res?.success ? 'Oturum sıfırlandı.' : 'Sıfırlanamadı.');
                                                        }}
                                                        className="px-4 py-3 rounded-xl border border-white/10 bg-dark-900 hover:bg-dark-800 transition-colors text-white"
                                                    >
                                                        Oturumu Sıfırla
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {studioStep === 'generating' && (
                                    <div className="text-center space-y-4">
                                        <div className="w-16 h-16 border-4 border-pink-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                                        <p className="text-xl font-medium animate-pulse">Yapay zeka çalışıyor...</p>
                                        <p className="text-sm text-gray-500">Haberler taranıyor • Prompt yazılıyor • Görsel çiziliyor</p>

                                        {/* Progress Bar */}
                                        <div className="w-64 h-2 bg-gray-800 rounded-full mt-4 overflow-hidden border border-white/10 mx-auto">
                                            <div
                                                className="h-full bg-gradient-to-r from-pink-600 to-purple-600 transition-all duration-300 ease-out"
                                                style={{ width: `${progress}%` }}
                                            ></div>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-2 font-mono">{progress}%</p>
                                    </div>
                                )}

                                {studioStep === 'generating_carousel' && (
                                    <div className="text-center space-y-6">
                                        <div className="w-20 h-20 relative mx-auto">
                                            <div className="absolute inset-0 border-4 border-indigo-500/30 rounded-full"></div>
                                            <div className="absolute inset-0 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                                            <ImageIcon className="absolute inset-0 m-auto text-indigo-500 animate-pulse" size={32} />
                                        </div>

                                        <div className="space-y-2">
                                            <p className="text-2xl font-bold animate-pulse text-white">{videoStatusText || "Carousel Hazırlanıyor..."}</p>
                                            <p className="text-sm text-gray-400">10 farklı görsel oluşturuluyor. Bu işlem birkaç dakika sürebilir.</p>
                                        </div>
                                    </div>
                                )}

                                {studioStep === 'generating_agent' && (
                                    <div className="w-full flex flex-col items-center space-y-6">
                                        <div className="w-full max-w-2xl space-y-4">
                                            <div className="text-center space-y-2">
                                                <p className="text-2xl font-bold text-white">Yapay Zeka Ajanı Çalışıyor</p>
                                                <p className="text-sm text-gray-400">{videoStatusText || "Durum alınıyor..."}</p>
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
                                                        ? 'bg-gray-800 text-gray-400 border-white/10 cursor-not-allowed'
                                                        : 'bg-red-600 hover:bg-red-700 text-white border-red-500/30'
                                                        }`}
                                                    title="Ajanı güvenli şekilde durdur"
                                                >
                                                    {agentCancelRequested ? 'İptal İstendi' : 'İptal Et'}
                                                </button>
                                            </div>

                                            {/* Progress Bar */}
                                            <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden border border-white/10">
                                                <div
                                                    className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-300 ease-out"
                                                    style={{ width: `${Math.max(0, Math.min(100, agentPercent))}%` }}
                                                ></div>
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
                                                    const active = agentStage === step.id || (agentStage === 'running' && ['news','risk','visual','caption','schedule','publish'].includes(step.id));
                                                    const done = agentPercent >= 100 || ['done'].includes(agentStage);
                                                    return (
                                                        <div
                                                            key={step.id}
                                                            className={`px-3 py-2 rounded-xl border ${active
                                                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                                                                : 'bg-dark-900/40 border-white/10 text-gray-400'
                                                                }`}
                                                        >
                                                            <span className="font-mono text-xs opacity-70">{step.id}</span>
                                                            <div className="font-semibold">{step.label}{done && agentStage === 'done' ? '' : ''}</div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>

                                        <LogTerminal logs={agentLogs} />
                                    </div>
                                )}



                                {(studioStep === 'done_carousel' || studioStep === 'uploading_carousel') && generatedNews && generatedNews.images && (
                                    <div className="w-full h-full flex flex-col gap-6">
                                        {/* Carousel Gallery View */}
                                        <div className="flex-1 overflow-x-auto overflow-y-hidden flex gap-4 p-4 items-center scrollbar-thin scrollbar-thumb-white/20 pb-8">
                                            {generatedNews.images.map((img, idx) => (
                                                <div key={idx} className="flex flex-col gap-4 min-w-[300px] md:min-w-[400px] flex-shrink-0 snap-center">
                                                    {/* Image Wrapper */}
                                                    <div className="w-full aspect-square relative group rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-dark-800">
                                                        <img src={img.url} alt={`Slide ${idx + 1}`} className="w-full h-full object-cover" />

                                                        {/* Slide Number Badge */}
                                                        <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded-full backdrop-blur-md font-mono border border-white/10 z-10">
                                                            {idx + 1}/10
                                                        </div>

                                                        {/* Hover Overlay (Prompt Only) */}
                                                        <div className="absolute inset-0 bg-black/90 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center p-6 text-center cursor-help">
                                                            <p className="text-[10px] text-purple-400 font-mono tracking-widest mb-2 uppercase">Stable Diffusion Prompt</p>
                                                            <p className="text-sm text-gray-300 font-medium leading-relaxed line-clamp-[10]">{img.prompt}</p>
                                                        </div>
                                                    </div>

                                                    {/* Title Below Image */}
                                                    <div className="text-center px-4">
                                                        <p className="text-white font-bold tracking-widest text-lg uppercase bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent">
                                                            {img.title || `SLIDE ${idx + 1}`}
                                                        </p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="bg-dark-900 p-6 rounded-2xl border border-white/10 shadow-xl flex gap-6 items-start mx-auto w-full max-w-4xl">
                                            <div className="flex-1">
                                                <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-2 font-bold">Carousel Açıklaması</h3>
                                                <p className="text-base leading-relaxed whitespace-pre-wrap font-medium text-gray-200">
                                                    {generatedNews.caption}
                                                </p>
                                            </div>

                                            <div className="flex flex-col gap-2 shrink-0">
                                                <button
                                                    onClick={() => { setStudioStep('idle'); setGeneratedNews(null); }}
                                                    className="px-6 py-3 rounded-xl border border-white/10 bg-dark-800 hover:bg-dark-700 transition-colors flex items-center justify-center gap-2"
                                                >
                                                    <RefreshCw size={18} />
                                                    Yeni Yap
                                                </button>

                                                <button
                                                    onClick={handleInstaUpload}
                                                    disabled={studioLoading || studioStep === 'done'}
                                                    className={`px-6 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${studioStep === 'done'
                                                        ? 'bg-green-500 text-white'
                                                        : 'bg-gradient-to-r from-pink-500 to-purple-600 hover:shadow-lg hover:shadow-pink-500/25 text-white'
                                                        }`}
                                                    title="Instagram'a Yükle"
                                                >
                                                    {studioLoading ? <RefreshCw className="animate-spin" /> : (studioStep === 'done' ? 'Yüklendi' : 'Instagram\'a Yükle')}
                                                    {studioStep !== 'done' && <Upload size={18} />}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {generatedNews && (studioStep === 'review' || studioStep === 'done') && (
                                    <div className="w-full max-w-6xl grid md:grid-cols-2 gap-8 items-stretch animate-fade-in relative z-10">
                                        <div className="flex flex-col h-full">
                                            <div className="relative group rounded-2xl overflow-hidden shadow-2xl border border-white/10 h-full">
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
                                            <div className="bg-dark-900 p-6 rounded-2xl border border-white/10 relative z-10 shadow-xl">
                                                <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-2 font-bold">Instagram için Oluşturulan Açıklama</h3>
                                                <p className="text-lg leading-relaxed whitespace-pre-wrap font-medium text-gray-200">
                                                    {generatedNews.caption}
                                                </p>
                                            </div>

                                            <div className="bg-dark-900 p-4 rounded-xl border border-white/5 text-sm text-gray-500 relative z-10">
                                                <p><strong className="text-gray-400">Kaynak Haberler:</strong></p>
                                                <p className="italic mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap scrollbar-thin scrollbar-thumb-white/10">{generatedNews.news_summary}</p>
                                            </div>

                                            <div className="bg-dark-900 p-4 rounded-xl border border-white/5 text-sm text-gray-500 shadow-inner relative z-10">
                                                <p><strong className="text-purple-400 flex items-center gap-2"><Sparkles size={12} /> LLM Prompt:</strong></p>
                                                <p className="italic mt-1 max-h-32 overflow-y-auto font-mono text-xs whitespace-pre-wrap scrollbar-thin scrollbar-thumb-white/10 text-gray-400">
                                                    {generatedNews.prompt}
                                                </p>
                                            </div>

                                            <div className="flex gap-4">
                                                <button
                                                    onClick={handleGenerateNews}
                                                    disabled={studioLoading || isAgentRunning}
                                                    className="flex-1 py-3 rounded-xl border border-white/10 bg-dark-900 hover:bg-dark-800 transition-colors flex items-center justify-center gap-2 relative z-20"
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
                        ) : appMode === 'video' ? (
                            // --- VIDEO MODE UI ---
                            <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-6 overflow-y-auto">
                                {!generatedNews && studioStep === 'idle' && (
                                    <>
                                        <div className="w-24 h-24 bg-gradient-to-tr from-red-600 to-orange-600 rounded-3xl flex items-center justify-center mx-auto shadow-2xl shadow-red-500/30">
                                            <Film className="w-12 h-12 text-white" />
                                        </div>
                                        <h2 className="text-3xl font-bold">Gündem Özeti Videosu</h2>
                                        <p className="text-gray-400 max-w-md mx-auto">
                                            Otomatik olarak 3 adet haber seçilir, görselleri oluşturulur ve haber spikeri tonunda seslendirilerek video haline getirilir.
                                        </p>
                                        <div className="p-6 bg-dark-900 rounded-xl border border-white/10 max-w-lg mx-auto w-full relative z-10 shadow-2xl space-y-4">
                                            <div className="flex items-center gap-2 text-sm text-gray-400 justify-center">
                                                <span>• 3 Haber</span>
                                                <span>• Seslendirme</span>
                                                <span>• 30 Saniye</span>
                                            </div>
                                            <button
                                                onClick={async () => {
                                                    setStudioLoading(true);
                                                    setStudioStep('generating_video');
                                                    setGeneratedNews(null);
                                                    try {
                                                        const res = await api.generateNewsVideo(); // Now starts bg task
                                                        if (!res.success) {
                                                            alert('Hata: ' + res.error);
                                                            setStudioStep('idle');
                                                            setStudioLoading(false);
                                                            return;
                                                        }

                                                        // Poll for progress
                                                        const interval = setInterval(async () => {
                                                            const p = await api.checkNewsVideoProgress();

                                                            if (p.current_task) {
                                                                setVideoStatusText(p.current_task);
                                                            }

                                                            if (p.status === 'done') {
                                                                clearInterval(interval);
                                                                setGeneratedNews({ video_url: p.result });
                                                                setStudioStep('done_video');
                                                                setStudioLoading(false);
                                                            } else if (p.status === 'error') {
                                                                clearInterval(interval);
                                                                alert('Video Hatası: ' + p.error);
                                                                setStudioStep('idle');
                                                                setStudioLoading(false);
                                                            }
                                                        }, 2000);

                                                    } catch (err) {
                                                        alert('Bağlantı Hatası');
                                                        setStudioStep('idle');
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

                                {studioStep === 'generating_video' && (
                                    <div className="text-center space-y-6">
                                        <div className="w-20 h-20 relative mx-auto">
                                            <div className="absolute inset-0 border-4 border-red-500/30 rounded-full"></div>
                                            <div className="absolute inset-0 border-4 border-red-500 border-t-transparent rounded-full animate-spin"></div>
                                            <Film className="absolute inset-0 m-auto text-red-500 animate-pulse" size={32} />
                                        </div>

                                        <div className="space-y-2">
                                            <p className="text-2xl font-bold animate-pulse text-white">{videoStatusText || "Haber Videosu Hazırlanıyor..."}</p>
                                            <p className="text-sm text-gray-400">Bu işlem yapay zeka modelleri (LLM, SD, TTS) kullandığı için 1-2 dakika sürebilir.</p>
                                        </div>

                                        <div className="w-64 mx-auto bg-dark-800 rounded-full h-2 overflow-hidden border border-white/10">
                                            <div className="h-full bg-gradient-to-r from-red-600 to-orange-500 animate-pulse w-full origin-left scale-x-50"></div>
                                        </div>
                                    </div>
                                )}

                                {studioStep === 'done_video' && generatedNews && (
                                    <div className="w-full max-w-md mx-auto space-y-4 animate-fade-in relative z-10">
                                        <div className="bg-dark-900 rounded-2xl p-2 border border-white/10 shadow-2xl">
                                            <video
                                                src={generatedNews.video_url}
                                                controls
                                                autoPlay
                                                className="w-full rounded-xl aspect-[9/16] object-cover"
                                            ></video>
                                        </div>
                                        <button
                                            onClick={() => {
                                                setStudioStep('idle');
                                                setGeneratedNews(null);
                                            }}
                                            className="text-gray-400 hover:text-white underline text-sm"
                                        >
                                            Yeni Video Oluştur
                                        </button>
                                    </div>
                                )}
                            </div>
                        ) : (
                            // --- CHAT MODE UI (Panel Layout) ---
                            <div className="flex-1 flex flex-col h-full relative z-10 p-0 md:p-2 overflow-hidden">
                                <div className="w-full md:w-[500px] h-full flex flex-col dark:bg-dark-800/40 bg-white/60 backdrop-blur-2xl dark:border-white/10 border-gray-200/50 border md:rounded-3xl overflow-hidden relative shadow-2xl transition-all duration-300">

                                    {/* Messages List */}
                                    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin dark:scrollbar-thumb-white/10 scrollbar-thumb-gray-300">
                                        {messages.map((msg, idx) => (
                                            <div
                                                key={idx}
                                                className={`flex gap-4 message-appear ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                                            >
                                                {/* Avatar */}
                                                <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center ${msg.role === 'user'
                                                    ? 'bg-gradient-to-br from-gray-700 to-gray-600'
                                                    : 'bg-gradient-to-br from-primary to-indigo-600'
                                                    }`}>
                                                    {msg.role === 'user' ? <User size={18} /> : <Sparkles size={18} />}
                                                </div>

                                                {/* Message Bubble */}
                                                <div className={`flex flex-col max-w-[80%] space-y-2 ${msg.role === 'user' ? 'items-end' : 'items-start'
                                                    }`}>
                                                    <div className={`px-5 py-3.5 rounded-2xl relative group shadow-sm transition-colors ${msg.role === 'user'
                                                        ? 'bg-gradient-to-br from-white to-gray-50 text-dark-900 border border-transparent font-medium rounded-tr-sm shadow-md'
                                                        : 'dark:bg-white/10 bg-white dark:border-white/5 border-gray-200 border dark:text-gray-100 text-gray-800 rounded-tl-sm backdrop-blur-md shadow-sm'
                                                        }`}>
                                                        <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                                                        {/* Play TTS Button */}
                                                        {msg.role === 'ai' && (
                                                            <button
                                                                onClick={() => handleTTS(msg.content, idx)}
                                                                disabled={ttsLoading}
                                                                className={`absolute -right-8 top-1/2 -translate-y-1/2 p-2 text-gray-500 hover:text-white transition-all scale-90 hover:scale-100 ${playingMsgIndex === idx ? 'opacity-100 text-pink-500' : 'opacity-0 group-hover:opacity-100'} ${ttsLoading ? 'cursor-wait opacity-50' : ''}`}
                                                                title={playingMsgIndex === idx ? "Durdur" : "Seslendir"}
                                                            >
                                                                {playingMsgIndex === idx ? <StopCircle size={20} className="animate-pulse" /> : <Volume2 size={16} />}
                                                            </button>
                                                        )}
                                                    </div>

                                                    {/* Included Image */}
                                                    {msg.image && (
                                                        <div className="rounded-xl overflow-hidden border border-white/10 shadow-lg max-w-sm transition-transform hover:scale-[1.02] cursor-pointer relative">
                                                            <img src={msg.image} alt="Generated" className="w-full h-auto" />
                                                            {msg.duration && (
                                                                <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded-full backdrop-blur-md font-mono border border-white/10">
                                                                    {msg.duration}s
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}

                                        {/* Loading State */}
                                        {isProcessing && (
                                            <div className="flex gap-4 message-appear">
                                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-indigo-600 flex items-center justify-center">
                                                    <Sparkles size={18} />
                                                </div>
                                                <div className="bg-white/5 border border-white/5 px-5 py-3.5 rounded-2xl rounded-tl-sm flex items-center gap-2">
                                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                                </div>
                                            </div>
                                        )}
                                        <div ref={scrollRef} />
                                    </div>

                                    {/* Input Area (Pinned to Panel) */}
                                    <div className="p-4 dark:bg-dark-900/50 bg-white/40 dark:border-t border-white/5 border-gray-200/50 relative z-20">

                                        {/* Audio Visualizer Overlay */}
                                        {isRecording && audioStream && (
                                            <div className="absolute -top-32 left-0 w-full px-6 z-10 pointer-events-none">
                                                <AudioVisualizer stream={audioStream} />
                                            </div>
                                        )}

                                        <div className="relative flex items-center gap-3 dark:bg-dark-800/80 bg-white dark:border-white/10 border-gray-200 border rounded-2xl p-2 shadow-lg dark:shadow-inner dark:ring-1 dark:ring-white/5">

                                            <button
                                                onMouseDown={startRecording}
                                                onMouseUp={stopRecording}
                                                onMouseLeave={stopRecording}
                                                onTouchStart={startRecording}
                                                onTouchEnd={stopRecording}
                                                className={`p-3 rounded-xl transition-all duration-300 relative overflow-hidden group ${isRecording
                                                    ? 'mic-pulse'
                                                    : 'dark:bg-white/5 bg-gray-100 dark:text-gray-400 text-gray-500 hover:text-primary dark:hover:bg-white/10 hover:bg-primary/10 dark:border-white/5 border-transparent'
                                                    } active:scale-95`}
                                                title="Bas Konuş"
                                            >
                                                <div className="absolute inset-0 bg-gradient-to-br from-secondary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                                                <Mic size={22} className={`relative z-10 ${isRecording ? 'animate-bounce' : ''}`} />
                                            </button>

                                            <button
                                                onClick={handleDrawOpen}
                                                className="p-3 rounded-xl dark:bg-white/5 bg-gray-100 dark:text-gray-400 text-gray-500 hover:text-accent hover:bg-accent/10 dark:border-white/5 border-transparent transition-all hover:scale-110 hover:shadow-[0_0_15px_rgba(0,212,255,0.4)]"
                                                title="Resim Çiz"
                                            >
                                                <Palette size={22} />
                                            </button>

                                            <input
                                                type="text"
                                                value={input}
                                                onChange={(e) => setInput(e.target.value)}
                                                onKeyDown={handleKeyDown}
                                                placeholder="Bir şeyler yazın veya konuşun..."
                                                className="flex-1 bg-transparent dark:text-white text-gray-800 dark:placeholder-gray-500 placeholder-gray-400 focus:outline-none h-full py-2 text-lg px-2"
                                                disabled={isRecording}
                                            />

                                            <div className="pr-1">
                                                <button
                                                    onClick={handleSend}
                                                    disabled={!input.trim() || isProcessing}
                                                    className={`p-3 rounded-xl transition-all duration-300 ${input.trim()
                                                        ? 'bg-gradient-to-r from-primary to-accent text-white shadow-[0_0_20px_rgba(112,0,255,0.4)] hover:shadow-[0_0_30px_rgba(0,212,255,0.6)] transform hover:scale-110 active:scale-95'
                                                        : 'bg-white/5 text-gray-600 cursor-not-allowed'
                                                        }`}
                                                >
                                                    <Send size={20} />
                                                </button>
                                            </div>
                                        </div>
                                        <div className="text-center mt-3 text-[10px] text-gray-600 font-mono tracking-widest opacity-50 uppercase">
                                            Atlas OS
                                        </div>
                                    </div>
                                </div>

                                {/* DRAWING MODAL (Kept full screen) */}
                                {showDrawModal && (
                                    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
                                        <div className="bg-dark-800 border border-white/10 rounded-3xl p-6 w-full max-w-md shadow-2xl scale-in">
                                            <div className="flex justify-between items-center mb-4">
                                                <h3 className="text-xl font-bold flex items-center gap-2">
                                                    <Palette className="text-pink-500" />
                                                    Resim Çiz
                                                </h3>
                                                <button onClick={() => setShowDrawModal(false)} className="text-gray-400 hover:text-white">
                                                    <X size={24} />
                                                </button>
                                            </div>
                                            <div className="space-y-4">
                                                <p className="text-gray-400 text-sm">Hayalindeki görseli tarif et, yapay zeka senin için çizsin.</p>
                                                <textarea
                                                    className="w-full bg-dark-900/50 border border-white/10 rounded-xl p-4 text-white focus:border-pink-500 focus:outline-none min-h-[120px] resize-none"
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
                                                        : 'bg-white/5 text-gray-500 cursor-not-allowed'
                                                        }`}
                                                >
                                                    Çizimi Başlat
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </main>
                </div>
                {/* Gallery Sidebar */}
                <GallerySidebar
                    isOpen={galleryOpen}
                    onClose={() => setGalleryOpen(false)}
                    images={galleryImages}
                />
            </div >
        </div >
    );
}

export default App;
