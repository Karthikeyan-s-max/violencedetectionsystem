javascript
// API calls for backend integration
const API_BASE = 'http://localhost:5000/api';

// Login
async function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const role = document.querySelector('input[name="role"]:checked').value;
    
    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role })
        });
        
        const data = await response.json();
        if (data.success) {
            if (data.role === 'admin') {
                window.location.href = '/admin_dashboard.html';
            } else {
                window.location.href = '/user_dashboard.html';
            }
        } else {
            alert('Login failed: ' + data.error);
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Connection error');
    }
}

// Upload Video
async function uploadVideo(formData) {
    try {
        const response = await fetch(`${API_BASE}/upload-video`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            return data;
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Upload error:', error);
    }
}

// Run Detection
async function runDetection(filepath, model, threshold) {
    try {
        const response = await fetch(`${API_BASE}/detect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filepath: filepath,
                model: model,
                threshold: parseFloat(threshold)
            })
        });
        
        const data = await response.json();
        if (data.success) {
            displayDetectionResults(data.results);
        } else {
            alert('Detection failed: ' + data.error);
        }
    } catch (error) {
        console.error('Detection error:', error);
    }
}

// Display Results
function displayDetectionResults(results) {
    const statsDiv = document.getElementById('statistics');
    statsDiv.innerHTML = `
        <h3>Detection Results</h3>
        <p>Total Events: ${results.violence_count}</p>
        <p>Average Confidence: ${(results.average_confidence * 100).toFixed(2)}%</p>
        <p>Model Used: ${results.model_used}</p>
    `;
    
    const feedDiv = document.getElementById('detection-feed');
    feedDiv.innerHTML = '<h3>Detection Events</h3>';
    results.detections.forEach(det => {
        feedDiv.innerHTML += `
            <div class="detection-item">
                <span>${det.timestamp}</span>
                <span>${(det.confidence * 100).toFixed(2)}% Confidence</span>
            </div>
        `;
    });
}

// Connect CCTV
async function connectCCTV(rtspUrl, model) {
    try {
        const response = await fetch(`${API_BASE}/connect-cctv`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rtsp_url: rtspUrl,
                model: model
            })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Connected to CCTV!');
            // Start streaming
            document.getElementById('video-stream').src = `${API_BASE}/cctv-stream`;
        } else {
            alert('Connection failed: ' + data.error);
        }
    } catch (error) {
        console.error('CCTV error:', error);
    }
}

// Logout
async function logout() {
    await fetch(`${API_BASE}/logout`, { method: 'POST' });
    window.location.href = '/';
}





















































































































































































































































































































































































