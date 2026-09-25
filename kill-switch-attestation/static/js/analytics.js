/*
static/js/analytics.js
*/

window.render_analytics = async function(container) {
    container.innerHTML = `<h2>Analytics</h2><p>Loading...</p>`;
    
    try {
        const [summary, killbench] = await Promise.all([
            apiCall('/api/analytics/summary'),
            apiCall('/api/analytics/killbench-comparison')
        ]);
        
        container.innerHTML = `
            <h2>Analytics</h2>
            <div class="panel">
                <h3>KILLBENCH Comparison</h3>
                <p><strong>Status:</strong> ${killbench.status}</p>
                <p>${killbench.message}</p>
            </div>
            <div class="panel">
                <h3>Total Shutdowns</h3>
                <p style="font-size: 24px; font-weight: bold; color: var(--accent);">${summary.total_shutdowns}</p>
            </div>
            <div class="panel">
                <canvas id="leakChart"></canvas>
            </div>
        `;
        
        if (summary.total_shutdowns > 0) {
            const ctx = document.getElementById('leakChart').getContext('2d');
            const labels = Object.keys(summary.strategy_stats);
            const inFlightData = labels.map(l => summary.strategy_stats[l].in_flight_leaks);
            
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Total In-Flight Failures (Leaks)',
                        data: inFlightData,
                        backgroundColor: 'rgba(239, 68, 68, 0.8)',
                        borderColor: '#ef4444',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'top', labels: { color: '#e0e0e0' } },
                        title: { display: true, text: 'In-Flight Failures by Strategy', color: '#e0e0e0', font: { size: 16 } }
                    },
                    scales: {
                        y: { 
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#a1a1aa' }
                        },
                        x: { 
                            grid: { display: false },
                            ticks: { color: '#a1a1aa' }
                        }
                    }
                }
            });
        }
        
    } catch(e) {
        container.innerHTML = `<h2>Analytics</h2><p>Failed to load analytics data.</p>`;
    }
};
