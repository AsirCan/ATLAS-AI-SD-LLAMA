import { createContext, useContext, useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { useTheme } from '../hooks/useTheme';
import { useTTS } from '../hooks/useTTS';
import { useStudioProgress } from '../hooks/useStudioProgress';
import { useAgentPoller } from '../hooks/useAgentPoller';

const AppContext = createContext(null);

export function useAppContext() {
    const ctx = useContext(AppContext);
    if (!ctx) throw new Error('useAppContext must be used within AppProvider');
    return ctx;
}

export function AppProvider({ children }) {
    // Theme
    const { theme, toggleTheme } = useTheme();

    // Messages
    const [messages, setMessages] = useState([
        { role: 'ai', content: 'Merhaba! Ben Atlas. Size nasıl yardımcı olabilirim? Bugün neler üretmek istersiniz?' }
    ]);
    const [input, setInput] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const scrollRef = useRef(null);

    // App Mode
    const [appMode, setAppMode] = useState('chat');

    // Studio State
    const [generatedNews, setGeneratedNews] = useState(null);
    const [studioLoading, setStudioLoading] = useState(false);
    const [studioStep, setStudioStep] = useState('idle');
    const [videoStatusText, setVideoStatusText] = useState('');
    const [videoPercent, setVideoPercent] = useState(0);

    // Agent State
    const [agentStatusText, setAgentStatusText] = useState('');
    const [agentLogs, setAgentLogs] = useState([]);
    const [agentPercent, setAgentPercent] = useState(0);
    const [agentStage, setAgentStage] = useState('idle');
    const [agentStatus, setAgentStatus] = useState('idle');
    const [agentCancelRequested, setAgentCancelRequested] = useState(false);

    // Instagram Config
    const [showInstaLogin, setShowInstaLogin] = useState(false);
    const [instaUser, setInstaUser] = useState('');
    const [instaPass, setInstaPass] = useState('');
    const [instaAuthTab, setInstaAuthTab] = useState('graph');
    const [envCopied, setEnvCopied] = useState(false);
    const [graphConfig, setGraphConfig] = useState({
        fb_app_id: '',
        fb_app_secret: '',
        fb_page_id: '',
        ig_user_id: '',
        fb_access_token: '',
        public_base_url: '',
        ig_graph_version: 'v24.0',
    });
    const [graphStatus, setGraphStatus] = useState({ graph_ready: false, filled_count: 0, required_count: 6 });
    const [graphTokenStatus, setGraphTokenStatus] = useState({
        configured: false,
        is_valid: false,
        needs_refresh: false,
        expires_in_seconds: null,
        message: '',
    });
    const [imgbbApiKey, setImgbbApiKey] = useState('');
    const [imgbbConfigured, setImgbbConfigured] = useState(false);

    // Draw Modal
    const [showDrawModal, setShowDrawModal] = useState(false);
    const [drawPrompt, setDrawPrompt] = useState('');

    // Gallery
    const [galleryOpen, setGalleryOpen] = useState(false);
    const [galleryImages, setGalleryImages] = useState([]);

    // Computed
    const isAgentRunning = agentStatus === 'running';
    const hasConversation = messages.some((msg) => msg.role === 'user');
    const isStudioFlow = [
        'idle', 'generating', 'review', 'uploading', 'done',
        'generating_carousel', 'done_carousel', 'uploaded_carousel',
        'uploading_carousel', 'generating_agent',
    ].includes(studioStep);
    const isVideoFlow = studioStep === 'generating_video' || studioStep === 'done_video';

    // Helpers
    const setAppModeSafe = (nextMode) => {
        if (nextMode === appMode) return;
        if (isAgentRunning) return;
        setAppMode(nextMode);
    };

    const addMessage = (role, content, image = null, duration = null) => {
        setMessages(prev => [...prev, { role, content, image, duration }]);
    };

    const addToGallery = (url, prompt) => {
        setGalleryImages(prev => [{ url, prompt }, ...prev]);
    };

    // TTS
    const { handleTTS, playingMsgIndex, ttsLoading } = useTTS();

    // Studio Progress
    const { progress } = useStudioProgress(studioStep);

    // Agent Poller
    useAgentPoller({
        appMode,
        studioStep,
        isAgentRunning,
        agentStatus,
        setAgentStatus,
        setAgentStatusText,
        setAgentPercent,
        setAgentStage,
        setAgentLogs,
        setAgentCancelRequested,
        setStudioStep,
    });

    // Auto-scroll messages
    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Refresh insta config on modal open
    useEffect(() => {
        if (showInstaLogin) {
            refreshGraphStatus();
            refreshGraphTokenStatus();
            refreshImgBBConfig();
        }
    }, [showInstaLogin]);

    // --- Instagram Config Helpers ---
    const graphEnvTemplate = [
        'FB_APP_ID=', 'FB_APP_SECRET=', 'FB_PAGE_ID=',
        'IG_USER_ID=', 'FB_ACCESS_TOKEN=', 'PUBLIC_BASE_URL=',
        'IMGBB_API_KEY=', 'IG_GRAPH_VERSION=v24.0',
    ].join('\n');

    const copyGraphEnvTemplate = async () => {
        try {
            await navigator.clipboard.writeText(graphEnvTemplate);
            setEnvCopied(true);
            setTimeout(() => setEnvCopied(false), 1800);
        } catch {
            alert('.env sablonu kopyalanamadi. Elle kopyalayabilirsin.');
        }
    };

    const closeInstaModal = () => {
        setShowInstaLogin(false);
        setInstaPass('');
        setEnvCopied(false);
    };

    const refreshGraphStatus = async () => {
        const res = await api.getInstagramGraphConfigStatus();
        if (res?.success) {
            setGraphStatus({
                graph_ready: !!res.graph_ready,
                filled_count: res.filled_count || 0,
                required_count: res.required_count || 6,
            });
            setGraphConfig(prev => ({
                ...prev,
                public_base_url: res.public_base_url || prev.public_base_url,
            }));
        }
    };

    const refreshGraphTokenStatus = async () => {
        const res = await api.getInstagramTokenStatus();
        if (!res) return;
        if (res.success === false) {
            setGraphTokenStatus({
                configured: true, is_valid: false, needs_refresh: true,
                expires_in_seconds: null,
                message: res.message || res.error || 'Token kontrolu basarisiz.',
            });
            return;
        }
        setGraphTokenStatus({
            configured: !!res.configured,
            is_valid: !!res.is_valid,
            needs_refresh: !!res.needs_refresh,
            expires_in_seconds: typeof res.expires_in_seconds === 'number' ? res.expires_in_seconds : null,
            message: res.message || '',
        });
    };

    const refreshImgBBConfig = async () => {
        const res = await api.getImgBBConfig();
        if (res?.success) {
            const key = (res.imgbb_api_key || '').trim();
            setImgbbApiKey(key);
            setImgbbConfigured(!!key);
        }
    };

    const formatExpiresIn = (seconds) => {
        if (typeof seconds !== 'number') return 'Bilinmiyor';
        if (seconds <= 0) return 'Doldu';
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        return `${days}g ${hours}s`;
    };

    const tokenStatusText = () => {
        if (!graphTokenStatus.configured) return 'Token kontrolu icin alanlar eksik';
        if (!graphTokenStatus.is_valid) return graphTokenStatus.message || 'Gecersiz token';
        if (typeof graphTokenStatus.expires_in_seconds !== 'number') return 'Gecerli • Sure bilgisi Meta tarafinda donmedi';
        if (graphTokenStatus.expires_in_seconds <= 0) return 'Gecerli ama sure dolmus gorunuyor (yeni token al)';
        return `Gecerli • Kalan: ${formatExpiresIn(graphTokenStatus.expires_in_seconds)}`;
    };

    const saveGraphConfig = async () => {
        const res = await api.saveInstagramGraphConfig(graphConfig);
        if (res?.success) {
            await refreshGraphStatus();
            await refreshGraphTokenStatus();
            alert('Graph ayarlari kaydedildi. Backend yeniden baslatmayi unutma.');
        } else {
            alert('Graph ayarlari kaydedilemedi: ' + (res?.error || 'Bilinmeyen hata'));
        }
    };

    const saveImgBBConfig = async () => {
        const res = await api.saveImgBBConfig(imgbbApiKey.trim());
        if (res?.success) {
            await refreshImgBBConfig();
            alert('ImgBB API key .env dosyasina kaydedildi.');
        } else {
            alert('ImgBB ayari kaydedilemedi: ' + (res?.error || 'Bilinmeyen hata'));
        }
    };

    const formatInstagramUploadError = (rawMessage) => {
        const msg = String(rawMessage || '');
        const lower = msg.toLowerCase();

        if (lower.includes('only photo or video can be accepted as media type')) {
            return [msg, '', 'Öneri:', '- Tunnel terminalini açık tut (cloudflared kapanmasın).',
                '- PUBLIC_BASE_URL güncel olsun.', '- Baglanti Merkezi > ImgBB Fallback alanina API key gir ve kaydet.',
                '- Tekrar dene (sistem fallback ile tekrar dener).'].join('\n');
        }
        if (lower.includes('unsupported post request') || (lower.includes('code') && lower.includes('100'))) {
            return [msg, '', 'Öneri:', '- IG_USER_ID / FB_PAGE_ID değerlerini tekrar kontrol et.',
                '- Graph alanlarını UI\'dan yeniden kaydet.'].join('\n');
        }
        if (lower.includes('login_required')) {
            return [msg, '', 'Öneri:', '- Graph API modunu kullan.',
                '- Legacy kullanıyorsan Session Sıfırla ile tekrar login yap.'].join('\n');
        }
        return msg;
    };

    // --- Chat Handlers ---
    const sendMessage = async (text) => {
        if (!text || !text.trim() || isProcessing) return;
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

    const handleSend = async () => {
        if (!input.trim() || isProcessing) return;
        const text = input;
        setInput('');
        await sendMessage(text);
    };

    const handleSuggestion = (text) => {
        if (isProcessing) return;
        setInput('');
        sendMessage(text);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // --- Studio Handlers ---
    const handleGenerateNews = async () => {
        setStudioLoading(true);
        setStudioStep('generating');
        setGeneratedNews(null);
        setProgress_external(0);
        setVideoStatusText('Günlük içerik hazırlanıyor...');
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

    // Note: progress from useStudioProgress is read-only, we don't need setProgress
    // The hook resets automatically when studioStep changes
    const setProgress_external = () => { }; // no-op, progress is managed by hook

    const handleInstaUpload = async () => {
        if (!generatedNews) return;
        setStudioLoading(true);
        const isCarouselMode = !!(generatedNews.images && Array.isArray(generatedNews.images));
        try {
            if (isCarouselMode) {
                setStudioStep('uploading_carousel');
                const paths = generatedNews.images.map(img => img.path);
                const res = await api.uploadCarouselToInstagram(paths, generatedNews.caption);
                if (res.success) {
                    alert('Carousel basariyla Instagram\'a yuklendi!');
                    setStudioStep('uploaded_carousel');
                } else {
                    alert('Yukleme Hatasi:\n' + formatInstagramUploadError(res.message));
                    setStudioStep('done_carousel');
                }
            } else if (generatedNews.image_path) {
                setStudioStep('uploading');
                const res = await api.uploadToInstagram(generatedNews.image_path, generatedNews.caption);
                if (res.success) {
                    alert('Basariyla Instagram\'a yuklendi!');
                    setStudioStep('done');
                } else {
                    alert('Yukleme Hatasi:\n' + formatInstagramUploadError(res.message));
                    setStudioStep('review');
                }
            }
        } catch (err) {
            console.error(err);
            alert('Yukleme sirasinda hata olustu.');
            setStudioStep(isCarouselMode ? 'done_carousel' : 'review');
        } finally {
            setStudioLoading(false);
        }
    };

    // --- Draw Handlers ---
    const handleDrawOpen = () => setShowDrawModal(true);

    const handleDrawSubmit = async () => {
        if (!drawPrompt.trim()) return;
        setShowDrawModal(false);
        const prompt = drawPrompt;
        setDrawPrompt('');
        addMessage('user', `Çizim isteği: ${prompt}`);
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

    const value = {
        // Theme
        theme, toggleTheme,
        // Messages / Chat
        messages, input, setInput, isProcessing, setIsProcessing, scrollRef,
        addMessage, sendMessage, handleSend, handleSuggestion, handleKeyDown,
        hasConversation,
        // App Mode
        appMode, setAppModeSafe,
        // Studio
        generatedNews, setGeneratedNews, studioLoading, setStudioLoading,
        studioStep, setStudioStep, progress, videoStatusText, setVideoStatusText,
        videoPercent, setVideoPercent, isStudioFlow, isVideoFlow,
        handleGenerateNews, handleInstaUpload,
        // Agent
        agentStatusText, agentLogs, agentPercent, agentStage, agentStatus,
        agentCancelRequested, setAgentCancelRequested, isAgentRunning,
        setAgentStatus, setAgentStatusText, setAgentPercent, setAgentStage,
        setAgentLogs,
        // Instagram Config
        showInstaLogin, setShowInstaLogin, instaUser, setInstaUser,
        instaPass, setInstaPass, instaAuthTab, setInstaAuthTab,
        envCopied, graphConfig, setGraphConfig, graphStatus, graphTokenStatus,
        imgbbApiKey, setImgbbApiKey, imgbbConfigured,
        graphEnvTemplate, copyGraphEnvTemplate, closeInstaModal,
        refreshGraphStatus, refreshGraphTokenStatus, refreshImgBBConfig,
        tokenStatusText, saveGraphConfig, saveImgBBConfig,
        formatInstagramUploadError,
        // Gallery
        galleryOpen, setGalleryOpen, galleryImages, addToGallery,
        // Draw
        showDrawModal, setShowDrawModal, drawPrompt, setDrawPrompt,
        handleDrawOpen, handleDrawSubmit,
        // TTS
        handleTTS, playingMsgIndex, ttsLoading,
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
