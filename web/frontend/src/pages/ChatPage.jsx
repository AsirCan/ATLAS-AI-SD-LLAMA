import { Sparkles, Zap, Lightbulb, FileText, User, StopCircle, Volume2, Mic, Palette, Send } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { useRecorder } from '../hooks/useRecorder';
import AudioVisualizer from '../components/AudioVisualizer';
import DrawModal from '../components/DrawModal';

export default function ChatPage() {
    const {
        messages, input, setInput, isProcessing, setIsProcessing, scrollRef,
        addMessage, handleSend, handleSuggestion, handleKeyDown, hasConversation,
        handleTTS, playingMsgIndex, ttsLoading, handleDrawOpen, addToGallery,
    } = useAppContext();

    const { isRecording, audioStream, startRecording, stopRecording } = useRecorder({
        addMessage,
        addToGallery,
        setIsProcessing,
        handleTTS,
    });

    const quickSuggestions = [
        { icon: Zap, label: 'Günlük içerik konsepti üret (haber tabanlı)', prompt: 'Bugünün gündeminden Instagram için tek görsel konsepti öner.' },
        { icon: Lightbulb, label: '10\'lu carousel için tema ve varyasyonlar', prompt: 'Instagram carousel için tek tema seç ve 10 farklı görsel varyasyonu öner.' },
        { icon: FileText, label: 'Kısa video senaryosu (3 haber özeti)', prompt: '3 haber için kısa, tempolu video senaryosu üret.' },
        { icon: Sparkles, label: 'Instagram için güçlü caption + hashtag', prompt: 'Instagram için kısa, vurucu caption ve hashtag öner.' },
    ];

    return (
        <div className="flex-1 flex flex-col h-full relative z-10 overflow-hidden">
            <div className="flex-1 flex flex-col h-full">
                {/* Section Header */}
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-primary/80">
                    <Sparkles size={14} className="text-primary" />
                    CHAT ASSISTANT
                </div>
                <h1 className="text-3xl md:text-4xl font-bold mt-2 dark:text-white text-gray-900">AI Chat</h1>
                <p className="text-sm md:text-base dark:text-gray-400 text-gray-500 mt-1">Ask anything and get intelligent responses instantly</p>

                {/* Main Chat Body */}
                <div className={`flex-1 mt-10 ${hasConversation ? 'overflow-y-auto' : 'flex items-center justify-center'}`}>
                    {!hasConversation ? (
                        <div className="w-full max-w-3xl mx-auto flex flex-col items-center text-center gap-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
                                {quickSuggestions.map((s, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSuggestion(s.prompt)}
                                        className="group flex items-start gap-3 text-left p-4 rounded-xl dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10 bg-white border-gray-200 hover:bg-gray-50 transition-all"
                                    >
                                        <s.icon size={18} className="mt-0.5 text-primary shrink-0 group-hover:scale-110 transition-transform" />
                                        <span className="text-sm dark:text-gray-300 text-gray-600 leading-relaxed">{s.label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-6 px-2 max-w-3xl mx-auto w-full">
                            {messages.map((msg, idx) => (
                                <div key={idx} className={`flex gap-4 message-appear ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                    <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user'
                                        ? 'bg-gradient-to-br from-primary/80 to-accent/80 text-white'
                                        : 'dark:bg-white/10 dark:border-white/10 dark:text-gray-200 bg-white border-gray-200 text-gray-700'
                                        }`}>
                                        {msg.role === 'user' ? <User size={16} /> : <Sparkles size={16} />}
                                    </div>

                                    <div className={`flex flex-col max-w-[80%] space-y-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                        <div className={`px-4 py-3 rounded-2xl relative group shadow-sm ${msg.role === 'user'
                                            ? 'bg-gradient-to-br from-primary/80 to-accent/80 text-white rounded-tr-sm'
                                            : 'dark:bg-white/5 dark:border-white/10 dark:text-gray-100 bg-white border-gray-200 text-gray-800 rounded-tl-sm'
                                            }`}>
                                            <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                                            {msg.role === 'ai' && (
                                                <button
                                                    onClick={() => handleTTS(msg.content, idx)}
                                                    disabled={ttsLoading}
                                                    className={`absolute -right-8 top-1/2 -translate-y-1/2 p-2 text-gray-500 dark:hover:text-white hover:text-gray-900 transition-all scale-90 hover:scale-100 ${playingMsgIndex === idx ? 'opacity-100 text-pink-500' : 'opacity-0 group-hover:opacity-100'} ${ttsLoading ? 'cursor-wait opacity-50' : ''}`}
                                                    title={playingMsgIndex === idx ? "Durdur" : "Seslendir"}
                                                >
                                                    {playingMsgIndex === idx ? <StopCircle size={18} className="animate-pulse" /> : <Volume2 size={14} />}
                                                </button>
                                            )}
                                        </div>

                                        {msg.image && (
                                            <div className="rounded-xl overflow-hidden border dark:border-white/10 border-gray-200 shadow-lg max-w-sm transition-transform hover:scale-[1.02] cursor-pointer relative">
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

                            {isProcessing && (
                                <div className="flex gap-4 message-appear">
                                    <div className="w-9 h-9 rounded-full dark:bg-white/10 dark:border-white/10 dark:text-gray-200 bg-white border-gray-200 text-gray-700 flex items-center justify-center">
                                        <Sparkles size={16} />
                                    </div>
                                    <div className="dark:bg-white/5 dark:border-white/10 bg-white border-gray-200 px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-2">
                                        <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                        <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                        <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                    </div>
                                </div>
                            )}
                            <div ref={scrollRef} />
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="pt-6 pb-2">
                    <div className="relative w-full max-w-3xl mx-auto">
                        {isRecording && audioStream && (
                            <div className="absolute -top-32 left-0 w-full px-6 z-10 pointer-events-none">
                                <AudioVisualizer stream={audioStream} />
                            </div>
                        )}

                        <div className="flex items-center gap-3 dark:bg-white/5 dark:border-white/10 bg-white border-gray-200 rounded-2xl px-4 py-3 backdrop-blur-xl shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
                            <button
                                onMouseDown={startRecording}
                                onMouseUp={stopRecording}
                                onMouseLeave={stopRecording}
                                onTouchStart={startRecording}
                                onTouchEnd={stopRecording}
                                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 relative overflow-hidden ${isRecording
                                    ? 'mic-pulse'
                                    : 'dark:bg-white/5 bg-gray-100 dark:text-gray-400 text-gray-500 dark:hover:text-primary hover:text-primary dark:hover:bg-white/10 hover:bg-gray-200'
                                    }`}
                                title="Hold to talk"
                            >
                                <Mic size={18} className={`${isRecording ? 'animate-bounce' : ''}`} />
                            </button>

                            <button
                                onClick={handleDrawOpen}
                                className="w-10 h-10 rounded-xl dark:bg-white/5 bg-gray-100 dark:text-gray-400 text-gray-500 dark:hover:text-accent hover:text-accent dark:hover:bg-white/10 hover:bg-gray-200 transition-all flex items-center justify-center"
                                title="Draw image"
                            >
                                <Palette size={18} />
                            </button>

                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Type your message..."
                                className="flex-1 bg-transparent dark:text-white text-gray-800 dark:placeholder-gray-500 placeholder-gray-400 focus:outline-none h-full py-2 text-base px-1"
                                disabled={isRecording}
                            />

                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isProcessing}
                                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${input.trim()
                                    ? 'bg-primary text-white hover:bg-primary/90'
                                    : 'dark:bg-white/5 bg-gray-100 text-gray-600 cursor-not-allowed'
                                    }`}
                            >
                                <Send size={18} />
                            </button>
                        </div>
                        <div className="text-center mt-3 text-xs text-gray-500">
                            Press Enter to send or click the send button
                        </div>
                    </div>
                </div>
            </div>

            {/* Drawing Modal */}
            <DrawModal />
        </div>
    );
}
