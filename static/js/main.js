document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initTabs();
    initFormHandlers();
    
    // Initial fetch and auto-refresh loop
    fetchDashboardStatus();
    fetchRegisteredVehicles();
    fetchDayLogs();
    
    setInterval(fetchDashboardStatus, 2000);
});

function initClock() {
    const clockEl = document.getElementById('live-clock');
    if (clockEl) {
        setInterval(() => {
            const now = new Date();
            clockEl.textContent = now.toLocaleTimeString();
        }, 1000);
    }
}

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.style.display = 'none');

            btn.classList.add('active');
            const targetPane = document.getElementById(btn.dataset.tab);
            if (targetPane) {
                targetPane.style.display = 'block';
            }
        });
    });
}

async function fetchDashboardStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // Update Vehicles Inside Counter
        document.getElementById('count-vehicles-inside').textContent = data.vehicles_inside;

        // Update Entry Gate Indicator
        const entryGateEl = document.getElementById('entry-gate-status');
        if (data.entry_gate === 'OPEN') {
            entryGateEl.className = 'gate-indicator gate-open';
            entryGateEl.textContent = '● ENTRY GATE: OPEN';
        } else {
            entryGateEl.className = 'gate-indicator gate-closed';
            entryGateEl.textContent = '● ENTRY GATE: CLOSED';
        }

        // Update Exit Gate Indicator
        const exitGateEl = document.getElementById('exit-gate-status');
        if (data.exit_gate === 'OPEN') {
            exitGateEl.className = 'gate-indicator gate-open';
            exitGateEl.textContent = '● EXIT GATE: OPEN';
        } else {
            exitGateEl.className = 'gate-indicator gate-closed';
            exitGateEl.textContent = '● EXIT GATE: CLOSED';
        }

        // Update Recent Decision Box
        if (data.last_entry) {
            updateDecisionBox(data.last_entry, 'ENTRY');
        } else if (data.last_exit) {
            updateDecisionBox(data.last_exit, 'EXIT');
        }

        // Update Access Logs Table
        renderAccessLogsTable(data.recent_logs);

    } catch (err) {
        console.error('Error fetching status:', err);
    }
}

function updateDecisionBox(eventData, type) {
    const plateImg = document.getElementById('decision-plate-img');
    const plateText = document.getElementById('decision-plate-text');
    const ownerText = document.getElementById('decision-owner-name');
    const badge = document.getElementById('decision-badge');

    if (eventData.plate_image_path || eventData.entry_image_path || eventData.exit_image_path) {
        plateImg.src = eventData.plate_image_path || eventData.entry_image_path || eventData.exit_image_path;
    }
    plateText.textContent = eventData.plate_number || '---';
    ownerText.textContent = eventData.owner_name || (type === 'EXIT' ? 'EXIT VEHICLE' : 'UNREGISTERED');

    if (eventData.gate_decision === 'GRANTED') {
        badge.className = 'gate-indicator gate-open';
        badge.textContent = 'ACCESS GRANTED (GATE OPEN)';
    } else {
        badge.className = 'gate-indicator gate-closed';
        badge.textContent = 'ACCESS DENIED (GATE CLOSED)';
    }
}

function renderAccessLogsTable(logs) {
    const tbody = document.getElementById('access-logs-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94a3b8;">No access logs recorded today</td></tr>';
        return;
    }

    logs.forEach(log => {
        const tr = document.createElement('tr');
        const decisionClass = log.gate_decision === 'GRANTED' ? 'gate-open' : 'gate-closed';
        
        tr.innerHTML = `
            <td>#${log.id}</td>
            <td style="font-weight:700; font-family:monospace; color:#facc15;">${log.plate_number}</td>
            <td>${log.entry_time || '---'}</td>
            <td>${log.exit_time || '---'}</td>
            <td><span class="gate-indicator ${decisionClass}">${log.gate_decision}</span></td>
            <td>
                ${log.plate_image_path ? `<a href="${log.plate_image_path}" target="_blank" style="color:#38bdf8;">View Crop</a>` : ''}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function triggerEntryScan() {
    try {
        const res = await fetch('/api/scan/entry', { method: 'POST' });
        const data = await res.json();
        alert(`Entry Scan Completed: Plate [${data.plate_number || 'N/A'}] - Decision: ${data.gate_decision || 'PROCESSED'}`);
        fetchDashboardStatus();
    } catch (err) {
        alert('Failed to trigger Entry Scan: ' + err.message);
    }
}

async function triggerExitScan() {
    try {
        const res = await fetch('/api/scan/exit', { method: 'POST' });
        const data = await res.json();
        alert(`Exit Scan Completed: Plate [${data.plate_number || 'N/A'}] - Decision: ${data.gate_decision || 'PROCESSED'}`);
        fetchDashboardStatus();
    } catch (err) {
        alert('Failed to trigger Exit Scan: ' + err.message);
    }
}

// Registered Vehicles Management
async function fetchRegisteredVehicles() {
    try {
        const res = await fetch('/api/registered');
        const list = await res.json();
        const tbody = document.getElementById('registered-vehicles-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!list || list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#94a3b8;">No registered vehicles</td></tr>';
            return;
        }

        list.forEach(v => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${v.id}</td>
                <td style="font-weight:700; font-family:monospace; color:#38bdf8;">${v.plate_number}</td>
                <td>${v.owner_name}</td>
                <td>${v.vehicle_type || 'Car'}</td>
                <td>
                    <button class="btn btn-danger" onclick="deleteVehicle(${v.id})" style="padding:0.2rem 0.5rem; font-size:0.75rem;">Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Error loading registered vehicles:', err);
    }
}

function initFormHandlers() {
    const form = document.getElementById('add-vehicle-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const plate_number = document.getElementById('reg-plate').value;
            const owner_name = document.getElementById('reg-owner').value;
            const vehicle_type = document.getElementById('reg-type').value;

            try {
                const res = await fetch('/api/registered/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ plate_number, owner_name, vehicle_type })
                });
                const data = await res.json();
                if (data.success) {
                    form.reset();
                    fetchRegisteredVehicles();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (err) {
                alert('Submission failed: ' + err.message);
            }
        });
    }
}

async function deleteVehicle(id) {
    if (!confirm('Are you sure you want to remove this registered vehicle?')) return;
    try {
        const res = await fetch(`/api/registered/delete/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            fetchRegisteredVehicles();
        }
    } catch (err) {
        alert('Delete failed: ' + err.message);
    }
}

async function fetchDayLogs() {
    try {
        const res = await fetch('/api/logs/today');
        const logs = await res.json();
        const tbody = document.getElementById('day-logs-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${log.id}</td>
                <td style="font-weight:700; font-family:monospace; color:#facc15;">${log.plate_number}</td>
                <td>${log.entry_time || '---'}</td>
                <td>${log.exit_time || '---'}</td>
                <td>${log.status}</td>
                <td><span class="gate-indicator ${log.gate_decision === 'GRANTED' ? 'gate-open' : 'gate-closed'}">${log.gate_decision}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Error loading day logs:', err);
    }
}
