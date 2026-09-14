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

            // Entry Gate Status Update
            if (entryPlateEl && data.last_entry) {
                const entry = data.last_entry;
                entryPlateEl.textContent = entry.plate_number || 'SCANNING...';
                
                const entryConfEl = document.getElementById('entry-confidence');
                if (entryConfEl) {
                    entryConfEl.textContent = entry.ocr_confidence ? (Math.round(entry.ocr_confidence * 100) + '%') : '---';
                }

                const entryRegEl = document.getElementById('entry-reg-status');
                if (entryRegEl) {
                    entryRegEl.textContent = entry.auth_status || 'NOT REGISTERED';
                    entryRegEl.className = entry.auth_status === 'REGISTERED' ? 'badge badge-success' : 'badge badge-danger';
                }

                const entryDecEl = document.getElementById('entry-access-decision');
                if (entryDecEl) {
                    entryDecEl.textContent = entry.access_decision || 'PENDING';
                    entryDecEl.className = entry.access_decision === 'ACCESS ALLOWED' ? 'badge badge-success' : 'badge badge-danger';
                }
            }

            const entryGateStatusEl = document.getElementById('entry-gate-status');
            if (entryGateStatusEl) {
                const isOpen = data.entry_gate_status === 'OPEN';
                entryGateStatusEl.textContent = isOpen ? 'GATE OPEN' : 'GATE CLOSED';
                entryGateStatusEl.className = isOpen ? 'badge badge-success' : 'badge badge-danger';
            }

            // Exit Gate Status Update
            if (exitPlateEl && data.last_exit) {
                const exit = data.last_exit;
                exitPlateEl.textContent = exit.plate_number || 'SCANNING...';

                const exitConfEl = document.getElementById('exit-confidence');
                if (exitConfEl) {
                    exitConfEl.textContent = exit.ocr_confidence ? (Math.round(exit.ocr_confidence * 100) + '%') : '---';
                }

                const exitRegEl = document.getElementById('exit-reg-status');
                if (exitRegEl) {
                    exitRegEl.textContent = exit.auth_status || 'NOT REGISTERED';
                    exitRegEl.className = exit.auth_status === 'REGISTERED' ? 'badge badge-success' : 'badge badge-danger';
                }

                const exitDecEl = document.getElementById('exit-access-decision');
                if (exitDecEl) {
                    exitDecEl.textContent = exit.access_decision || 'PENDING';
                    exitDecEl.className = exit.access_decision === 'ACCESS ALLOWED' ? 'badge badge-success' : 'badge badge-danger';
                }
            }

            const exitGateStatusEl = document.getElementById('exit-gate-status');
            if (exitGateStatusEl) {
                const isOpen = data.exit_gate_status === 'OPEN';
                exitGateStatusEl.textContent = isOpen ? 'GATE OPEN' : 'GATE CLOSED';
                exitGateStatusEl.className = isOpen ? 'badge badge-success' : 'badge badge-danger';
            }

        } catch (err) {
            console.error('Failed to poll gate status:', err);
        }
    }

    pollStatus();
    setInterval(pollStatus, 1000);
}
