document.addEventListener('DOMContentLoaded', function() {
    const sageGreen = '#8BA888';
    const sageGreenLight = '#E8F1E8';

    // Shared chart options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                align: 'end',
                rtl: true,
                labels: {
                    usePointStyle: true,
                    padding: 20,
                    font: {
                        family: 'masmak'
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0,0,0,0.05)'
                },
                ticks: {
                    font: {
                        family: 'masmak'
                    }
                }
            },
            x: {
                grid: {
                    display: false
                },
                ticks: {
                    font: {
                        family: 'masmak'
                    }
                }
            }
        }
    };

    // Revenue Chart
    const revenueChart = document.getElementById('revenueChart');
    if (revenueChart) {
        const labels = JSON.parse(revenueChart.dataset.labels);
        const values = JSON.parse(revenueChart.dataset.values);

        new Chart(revenueChart, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'الإيرادات',
                    data: values,
                    borderColor: sageGreen,
                    backgroundColor: sageGreenLight,
                    fill: true,
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                plugins: {
                    ...commonOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.parsed.y} ج.م `;
                            }
                        }
                    }
                }
            }
        });
    }

    // Orders Chart
    const ordersChart = document.getElementById('ordersChart');
    if (ordersChart) {
        const labels = JSON.parse(ordersChart.dataset.labels);
        const values = JSON.parse(ordersChart.dataset.values);

        new Chart(ordersChart, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'الطلبات',
                    data: values,
                    backgroundColor: sageGreen,
                    borderRadius: 6
                }]
            },
            options: commonOptions
        });
    }

    // Toggle period buttons
    document.querySelectorAll('[data-period]').forEach(button => {
        button.addEventListener('click', function() {
            const period = this.dataset.period;
            const chartId = this.dataset.chart;
            const container = this.closest('.chart-container');

            // Update active state
            container.querySelectorAll('[data-period]').forEach(btn => {
                btn.classList.remove('bg-sage-green-100', 'text-sage-green-600');
                btn.classList.add('bg-gray-100', 'text-gray-600');
            });
            this.classList.remove('bg-gray-100', 'text-gray-600');
            this.classList.add('bg-sage-green-100', 'text-sage-green-600');

            // Show loader
            document.getElementById(`${chartId}-loader`).classList.remove('hidden');

            // Fetch new data (to be implemented in Flask)
            fetch(`/admin/chart-data?chart=${chartId}&period=${period}`)
                .then(response => response.json())
                .then(data => {
                    const chart = Chart.getChart(chartId);
                    if (chart) {
                        chart.data.labels = data.labels;
                        chart.data.datasets[0].data = data.values;
                        chart.update();
                    }
                })
                .finally(() => {
                    document.getElementById(`${chartId}-loader`).classList.add('hidden');
                });
        });
    });
});