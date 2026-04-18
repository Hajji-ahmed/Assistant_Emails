// Subscribe to an SSE job stream.
// onEvent(event): called for each progress event.
// onEnd(status): called once when the stream ends with "finished" or "failed".
function streamJob(jobId, onEvent, onEnd) {
    const es = new EventSource(`/api/jobs/${jobId}/stream`);
    let finalStatus = 'terminé';
    es.onmessage = (msg) => {
        try {
            const data = JSON.parse(msg.data);
            if (data.type === 'done') finalStatus = 'terminé';
            if (data.type === 'error') finalStatus = 'échec';
            if (data.type === 'quota') finalStatus = 'quota atteint';
            if (data.type === 'cancelled') finalStatus = 'annulé';
            onEvent(data);
        } catch (e) { /* ignore keepalive */ }
    };
    es.addEventListener('end', () => {
        es.close();
        if (onEnd) onEnd(finalStatus);
    });
    es.onerror = () => {
        // EventSource reconnects automatically; if the job is already done,
        // the server closed the connection — check status explicitly.
        fetch('/api/jobs/current').then(r => r.json()).then(data => {
            if (!data || !data.job || data.status !== 'running') {
                es.close();
                if (onEnd) onEnd(finalStatus);
            }
        }).catch(() => {});
    };
}
