import { useState } from 'react';
import { api } from '../api';

export function useTTS() {
    const [currentAudio, setCurrentAudio] = useState(null);
    const [playingMsgIndex, setPlayingMsgIndex] = useState(null);
    const [ttsLoading, setTtsLoading] = useState(false);

    const handleTTS = async (text, index) => {
        if (!text) return;

        // Toggle: clicking same message stops it
        if (playingMsgIndex === index) {
            if (currentAudio) {
                currentAudio.pause();
                currentAudio.currentTime = 0;
            }
            setCurrentAudio(null);
            setPlayingMsgIndex(null);
            return;
        }

        if (ttsLoading) return;

        // Stop currently playing audio
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            setCurrentAudio(null);
            setPlayingMsgIndex(null);
        }

        try {
            setTtsLoading(true);
            const blob = await api.tts(text);
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);

            audio.onended = () => {
                setPlayingMsgIndex(null);
                setCurrentAudio(null);
            };

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

    return { handleTTS, playingMsgIndex, ttsLoading };
}
