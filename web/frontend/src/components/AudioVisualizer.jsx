import React, { useEffect, useRef } from 'react';

const AudioVisualizer = ({ stream }) => {
    const canvasRef = useRef(null);
    const requestRef = useRef(null);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const sourceRef = useRef(null);

    useEffect(() => {
        if (!stream) return;

        // Init Audio Context
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        audioContextRef.current = audioCtx;

        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256; // Controls bar count and smoothness
        analyserRef.current = analyser;

        const source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);
        sourceRef.current = source;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
            requestRef.current = requestAnimationFrame(draw);

            analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height); // Wipe canvas

            // Optional: Semi-transparent fill for trail effect
            // ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
            // ctx.fillRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.5;
            let barHeight;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                barHeight = dataArray[i];

                // Gradient Color based on height
                const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
                gradient.addColorStop(0, '#7000ff'); // Primary (Purple)
                gradient.addColorStop(1, '#00d4ff'); // Accent (Cyan)

                ctx.fillStyle = gradient;

                // Draw rounded rect (simplified as rect for now)
                ctx.fillRect(x, canvas.height - barHeight / 1.5, barWidth, barHeight / 1.5);

                x += barWidth + 2;
            }
        };

        draw();

        return () => {
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
            if (audioContextRef.current) audioContextRef.current.close();
        };
    }, [stream]);

    return (
        <div className="w-full h-24 flex items-center justify-center p-2 rounded-xl bg-black/20 backdrop-blur-sm border border-white/5">
            <canvas
                ref={canvasRef}
                width={300}
                height={80}
                className="w-full h-full"
            />
        </div>
    );
};

export default AudioVisualizer;
