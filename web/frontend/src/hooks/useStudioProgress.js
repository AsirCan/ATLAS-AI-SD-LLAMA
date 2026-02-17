import { useState, useEffect } from 'react';
import { api } from '../api';

export function useStudioProgress(studioStep) {
    const [progress, setProgress] = useState(0);

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

    return { progress };
}
