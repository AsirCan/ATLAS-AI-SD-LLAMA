import { useState, useRef } from 'react';
import { api } from '../api';

export function useRecorder({ addMessage, addToGallery, setIsProcessing, handleTTS }) {
    const [isRecording, setIsRecording] = useState(false);
    const [audioStream, setAudioStream] = useState(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setAudioStream(stream);
            mediaRecorderRef.current = new MediaRecorder(stream);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };

            mediaRecorderRef.current.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
                setIsProcessing(true);

                stream.getTracks().forEach(track => track.stop());
                setAudioStream(null);

                try {
                    const res = await api.stt(audioBlob);
                    if (res.text) {
                        addMessage('user', res.text);

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

    return { isRecording, audioStream, startRecording, stopRecording };
}
