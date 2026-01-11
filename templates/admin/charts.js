function formatCurrency(value) {
    return value.toLocaleString() + ' ج.م';
}

function initializeChart(id, type, displayCallback) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;

    const labels = JSON.parse(canvas.dataset.labels || '[]');
    const values = JSON.parse(canvas.dataset.values || '[]');

    const isRevenue = id === 'revenueChart';
    const color = isRevenue ? {
        bg: 'rgba(59, 130, 246, 0.8)',
        border: 'rgb(59, 130, 246)'
    } : {
        bg: 'rgba(16, 185, 129, 0.1)',
        border: 'rgb(16, 185, 129)'
    };

    const config = {
        type: type,
        data: {
            labels: labels,
            datasets: [{
                label: isRevenue ? 'الإيرادات' : 'الطلبات',
                data: values,
                backgroundColor: color.bg,
                borderColor: color.border,
                ...(type === 'bar' ? {
                    borderWidth: 1,
                    borderRadius: 5,
                    barThickness: 15,
                    maxBarThickness: 20
                } : {
                    tension: 0.4,
                    fill: true,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: color.border,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return displayCallback(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        ...(isRevenue ? {
                            callback: formatCurrency,
                            maxTicksLimit: 5
                        } : {
                            stepSize: 1,
                            maxTicksLimit: 5
                        })
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        maxRotation: 0,
                        minRotation: 0
                    }
                }
            }
        }
    };

    return new Chart(canvas.getContext('2d'), config);
}

// Initialize Charts
window.onload = function() {
    try {
        // Initialize Revenue Chart
        initializeChart('revenueChart', 'bar', value => formatCurrency(value));

        // Initialize Orders Chart
        initializeChart('ordersChart', 'line', value => value + ' طلب');
    } catch (error) {
        console.error('Error initializing charts:', error);
    }
};