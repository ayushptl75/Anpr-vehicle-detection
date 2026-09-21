document.addEventListener('DOMContentLoaded', () => {
    console.log('Smart Society ANPR Dashboard Initialized');
    initGateStatusPolling();
});

function initGateStatusPolling() {
    const entryPlateEl = document.getElementById('entry-plate');
    const exitPlateEl = document.getElementById('exit-plate');

    if (!entryPlateEl && !exitPlateEl) return;

    async function pollStatus() {
        try {
            const res = await fetch('/api/gate-status');
            if (!res.ok) return;
            const data = await res.json();

            // ==================== ENTRY GATE UI UPDATES ====================
            if (entryPlateEl) {
                const entryCam = data.entry_camera_status || {};
                const lastEntry = data.last_entry || {};

                // 1. Camera Status
                const camStatEl = document.getElementById('entry-cam-status');
                const camBadgeEl = document.getElementById('entry-cam-badge');
                const camStat = entryCam.camera_status || 'CONNECTED';
                const isCamOk = camStat.includes('CONNECTED');
                if (camStatEl) {
                    camStatEl.textContent = isCamOk ? 'CONNECTED' : 'DISCONNECTED';
                    camStatEl.className = isCamOk ? 'badge badge-success' : 'badge badge-danger';
                }
                if (camBadgeEl) {
                    camBadgeEl.textContent = isCamOk ? '● CONNECTED' : '● DISCONNECTED';
                    camBadgeEl.className = isCamOk ? 'badge badge-success' : 'badge badge-danger';
                }

                // 2. Vehicle Detection
                const vehicleStatEl = document.getElementById('entry-vehicle-status');
                if (vehicleStatEl) {
                    const vStat = entryCam.vehicle_detected || 'NOT DETECTED';
                    const isDetected = vStat.includes('DETECTED') && !vStat.includes('NOT');
                    vehicleStatEl.textContent = isDetected ? vStat : 'NOT DETECTED';
                    vehicleStatEl.className = isDetected ? 'badge badge-success' : 'badge badge-secondary';
                }

                // 3. License Plate
                const plateText = entryCam.plate_number !== 'Searching...' ? entryCam.plate_number : (lastEntry.plate_number || 'Searching...');
                entryPlateEl.textContent = plateText;

                // 4. OCR Confidence
                const entryConfEl = document.getElementById('entry-confidence');
                if (entryConfEl) {
                    const confVal = entryCam.ocr_confidence || lastEntry.ocr_confidence;
                    entryConfEl.textContent = confVal ? (Math.round(confVal * 100) + '%') : '---';
                }

                // 5. Registration Status
                const entryRegEl = document.getElementById('entry-reg-status');
                if (entryRegEl) {
                    const regStat = entryCam.auth_status !== 'WAITING' ? entryCam.auth_status : (lastEntry.auth_status || 'WAITING');
                    entryRegEl.textContent = regStat;
                    entryRegEl.className = regStat === 'REGISTERED' ? 'badge badge-success' : (regStat === 'NOT REGISTERED' ? 'badge badge-danger' : 'badge badge-secondary');
                }

                // 6. Access Decision
                const entryDecEl = document.getElementById('entry-access-decision');
                if (entryDecEl) {
                    const decStat = entryCam.access_decision !== 'PENDING' ? entryCam.access_decision : (lastEntry.access_decision || 'PENDING');
                    const cleanDec = decStat.includes('ALLOWED') ? 'ALLOWED' : (decStat.includes('DENIED') ? 'DENIED' : 'PENDING');
                    entryDecEl.textContent = cleanDec;
                    entryDecEl.className = cleanDec === 'ALLOWED' ? 'badge badge-success' : (cleanDec === 'DENIED' ? 'badge badge-danger' : 'badge badge-secondary');
                }

                // 7. Gate Status
                const entryGateStatusEl = document.getElementById('entry-gate-status');
                if (entryGateStatusEl) {
                    const isOpen = data.entry_gate_status === 'OPEN';
                    entryGateStatusEl.textContent = isOpen ? 'OPEN' : 'CLOSED';
                    entryGateStatusEl.className = isOpen ? 'badge badge-success' : 'badge badge-danger';
                }
            }

            // ==================== EXIT GATE UI UPDATES ====================
            if (exitPlateEl) {
                const exitCam = data.exit_camera_status || {};
                const lastExit = data.last_exit || {};

                // 1. Camera Status
                const camStatEl = document.getElementById('exit-cam-status');
                const camBadgeEl = document.getElementById('exit-cam-badge');
                const camStat = exitCam.camera_status || 'CONNECTED';
                const isCamOk = camStat.includes('CONNECTED');
                if (camStatEl) {
                    camStatEl.textContent = isCamOk ? 'CONNECTED' : 'DISCONNECTED';
                    camStatEl.className = isCamOk ? 'badge badge-success' : 'badge badge-danger';
                }
                if (camBadgeEl) {
                    camBadgeEl.textContent = isCamOk ? '● CONNECTED' : '● DISCONNECTED';
                    camBadgeEl.className = isCamOk ? 'badge badge-success' : 'badge badge-danger';
                }

                // 2. Vehicle Detection
                const vehicleStatEl = document.getElementById('exit-vehicle-status');
                if (vehicleStatEl) {
                    const vStat = exitCam.vehicle_detected || 'NOT DETECTED';
                    const isDetected = vStat.includes('DETECTED') && !vStat.includes('NOT');
                    vehicleStatEl.textContent = isDetected ? vStat : 'NOT DETECTED';
                    vehicleStatEl.className = isDetected ? 'badge badge-success' : 'badge badge-secondary';
                }

                // 3. License Plate
                const plateText = exitCam.plate_number !== 'Searching...' ? exitCam.plate_number : (lastExit.plate_number || 'Searching...');
                exitPlateEl.textContent = plateText;

                // 4. OCR Confidence
                const exitConfEl = document.getElementById('exit-confidence');
                if (exitConfEl) {
                    const confVal = exitCam.ocr_confidence || lastExit.ocr_confidence;
                    exitConfEl.textContent = confVal ? (Math.round(confVal * 100) + '%') : '---';
                }

                // 5. Registration Status
                const exitRegEl = document.getElementById('exit-reg-status');
                if (exitRegEl) {
                    const regStat = exitCam.auth_status !== 'WAITING' ? exitCam.auth_status : (lastExit.auth_status || 'WAITING');
                    exitRegEl.textContent = regStat;
                    exitRegEl.className = regStat === 'REGISTERED' ? 'badge badge-success' : (regStat === 'NOT REGISTERED' ? 'badge badge-danger' : 'badge badge-secondary');
                }

                // 6. Access Decision
                const exitDecEl = document.getElementById('exit-access-decision');
                if (exitDecEl) {
                    const decStat = exitCam.access_decision !== 'PENDING' ? exitCam.access_decision : (lastExit.access_decision || 'PENDING');
                    const cleanDec = decStat.includes('ALLOWED') ? 'ALLOWED' : (decStat.includes('DENIED') ? 'DENIED' : 'PENDING');
                    exitDecEl.textContent = cleanDec;
                    exitDecEl.className = cleanDec === 'ALLOWED' ? 'badge badge-success' : (cleanDec === 'DENIED' ? 'badge badge-danger' : 'badge badge-secondary');
                }

                // 7. Gate Status
                const exitGateStatusEl = document.getElementById('exit-gate-status');
                if (exitGateStatusEl) {
                    const isOpen = data.exit_gate_status === 'OPEN';
                    exitGateStatusEl.textContent = isOpen ? 'OPEN' : 'CLOSED';
                    exitGateStatusEl.className = isOpen ? 'badge badge-success' : 'badge badge-danger';
                }
            }

        } catch (err) {
            console.error('Failed to poll gate status:', err);
        }
    }

    pollStatus();
    setInterval(pollStatus, 1000);
}
