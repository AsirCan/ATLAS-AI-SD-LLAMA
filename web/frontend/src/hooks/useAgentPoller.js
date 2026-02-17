import { useEffect } from 'react';
import { api } from '../api';

export function useAgentPoller({
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
}) {
    useEffect(() => {
        let interval;
        const shouldPollAgent =
            isAgentRunning ||
            agentStatus === 'cancelling' ||
            (appMode === 'studio' && studioStep === 'generating_agent');

        const tick = async () => {
            try {
                const p = await api.checkAgentProgress();

                if (p?.status) setAgentStatus(p.status);
                if (p?.current_task) setAgentStatusText(p.current_task);
                if (typeof p?.percent === 'number') setAgentPercent(p.percent);
                if (p?.stage) setAgentStage(p.stage);
                if (p?.logs && Array.isArray(p.logs)) setAgentLogs(p.logs);
                if (p?.cancel_requested) setAgentCancelRequested(true);

                if (appMode === 'studio' && p?.status === 'running') {
                    setStudioStep('generating_agent');
                }
            } catch {
                // ignore polling errors
            }
        };

        if (shouldPollAgent) {
            tick();
            interval = setInterval(tick, 1000);
        }

        return () => clearInterval(interval);
    }, [appMode, studioStep, isAgentRunning, agentStatus]);
}
