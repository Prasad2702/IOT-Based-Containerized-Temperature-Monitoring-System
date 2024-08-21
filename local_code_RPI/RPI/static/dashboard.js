document.addEventListener("DOMContentLoaded", function() {
    var temperatureChartCtx = document.getElementById('temperatureChart').getContext('2d');
    var humidityChartCtx = document.getElementById('humidityChart').getContext('2d');

    var temperatureChart = new Chart(temperatureChartCtx, {
        type: 'bar',
        data: {
            labels: ['Current Temperature'],
            datasets: [{
                label: 'Temperature (°C)',
                data: [0],
                backgroundColor: ['#ff6384'],
                borderColor: ['#fff'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(tooltipItem) {
                            return tooltipItem.label + ': ' + tooltipItem.raw + ' °C';
                        }
                    }
                }
            }
        }
    });

    var humidityChart = new Chart(humidityChartCtx, {
        type: 'bar',
        data: {
            labels: ['Current Humidity'],
            datasets: [{
                label: 'Humidity (%)',
                data: [0],
                backgroundColor: ['#36a2eb'],
                borderColor: ['#fff'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(tooltipItem) {
                            return tooltipItem.label + ': ' + tooltipItem.raw + ' %';
                        }
                    }
                }
            }
        }
    });

    function updateWeather() {
        fetch('/data')  // Default to 1 hour interval
            .then(response => response.json())
            .then(data => {
                const { temperature, humidity, time, sensorData } = data;

                // Update current values
                document.getElementById('currentTemperature').textContent = temperature.length > 0 ? temperature[temperature.length - 1] : 'N/A';
                document.getElementById('currentHumidity').textContent = humidity.length > 0 ? humidity[humidity.length - 1] : 'N/A';
                document.getElementById('lastUpdated').textContent = time.length > 0 ? time[time.length - 1] : 'N/A';

                // Update charts
                temperatureChart.data.datasets[0].data[0] = temperature.length > 0 ? temperature[temperature.length - 1] : 0;
                humidityChart.data.datasets[0].data[0] = humidity.length > 0 ? humidity[humidity.length - 1] : 0;
                temperatureChart.update();
                humidityChart.update();

                // Update weather cards
                updateWeatherCard('temperatureCard', 'temperature', temperature.length > 0 ? temperature[temperature.length - 1] : 0);
                updateWeatherCard('humidityCard', 'humidity', humidity.length > 0 ? humidity[humidity.length - 1] : 0);

                // Update sensor data table
                updateTable(sensorData);
            })
            .catch(error => console.error('Error fetching sensor data:', error));
    }

    function updateWeatherCard(cardId, type, value) {
        const card = document.getElementById(cardId);
        const icon = card.querySelector('.icon');

        if (type === 'temperature') {
            if (value > 25) {
                icon.innerHTML = '<i class="fas fa-sun"></i>'; // Hot temperature
                card.style.backgroundColor = '#ffebcd'; // Light color for hot
            } else if (value < 10) {
                icon.innerHTML = '<i class="fas fa-snowflake"></i>'; // Cold temperature
                card.style.backgroundColor = '#e0ffff'; // Light color for cold
            } else {
                icon.innerHTML = '<i class="fas fa-cloud-sun"></i>'; // Moderate temperature
                card.style.backgroundColor = '#f0f8ff'; // Light color for moderate
            }
        } else if (type === 'humidity') {
            if (value > 70) {
                icon.innerHTML = '<i class="fas fa-tint"></i>'; // High humidity
                card.style.backgroundColor = '#e0ffff'; // Light color for high humidity
            } else if (value < 30) {
                icon.innerHTML = '<i class="fas fa-cloud"></i>'; // Low humidity
                card.style.backgroundColor = '#f5f5dc'; // Light color for low humidity
            } else {
                icon.innerHTML = '<i class="fas fa-cloud-sun-rain"></i>'; // Moderate humidity
                card.style.backgroundColor = '#f5f5f5'; // Light color for moderate humidity
            }
        }
    }


    function updateTable(sensorData) {
        const tableBody = document.getElementById('dataTableBody');
document.getElementByClassName('table-record').style.display = 'block';
        tableBody.innerHTML = '';

        sensorData.forEach(data => {
            const row = `
                <tr>
                    <td>${data.timestamp}</td>
                    <td>${data.humidity}</td>
                    <td>${data.temperature}</td>
                </tr>
            `;
            tableBody.insertAdjacentHTML('beforeend', row);
        });
    }


    function getData(timeInterval) {
        fetch(`/data?interval=${timeInterval}`)
            .then(response => response.json())
            .then(sensorData => {
                updateTable(sensorData);
            })
            .catch(error => console.error(`Error fetching ${timeInterval} data:`, error));
    }

    setInterval(updateWeather, 60000); // Update every minute
    updateWeather();
});
