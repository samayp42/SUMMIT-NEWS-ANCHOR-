/**
 * AirOwl Controller
 */

class ClimateBuddyApp {
    constructor() {
        this.peerConnection = null;
        this.localStream = null;
        this.remoteAudio = null;
        this.dataChannel = null;
        this.isConnected = false;

        // State
        this.config = {
            customPrompt: '',
            features: { rag: true, iot: true, safety: true },
            llmParams: { temperature: 0.0, max_tokens: 50 },
            sensorData: {},
            identity: {}
        };

        this.metrics = { stt: [], llm: [], tts: [] };

        this.init();
        this.startBlinking();
    }

    init() {
        this.bindEvents();
        this.loadConfig(); // Fetch initial state from server
        console.log('🦉 AirOwl Initialized');
    }

    bindEvents() {
        // Tab Navigation
        document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.currentTarget));
        });

        // Connection
        document.getElementById('startBtn')?.addEventListener('click', () => this.connect());
        document.getElementById('stopBtn')?.addEventListener('click', () => this.disconnect());

        // Config Deploy
        document.getElementById('deployConfigBtn')?.addEventListener('click', () => this.deployConfig());

        // Scenario Buttons
        document.querySelectorAll('.tag-btn[data-scenario]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Remove active from all
                document.querySelectorAll('.tag-btn[data-scenario]').forEach(b => b.classList.remove('active'));
                // Add to current
                e.currentTarget.classList.add('active');

                this.loadScenarioUI(e.currentTarget.dataset.scenario);
            });
        });
    }

    switchTab(btn) {
        // Update Nav
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update Views
        const tabId = btn.dataset.tab;
        document.querySelectorAll('.view-panel').forEach(view => view.classList.remove('active'));

        const targetView = 'view-config'; // Only config view remains
        document.getElementById(targetView).classList.add('active');
    }

    // ==========================================
    // EYES ANIMATION & LOGIC
    // ==========================================

    startBlinking() {
        // Blink every 3-6 seconds
        const blink = () => {
            const eyes = document.querySelectorAll('.eye');
            eyes.forEach(e => e.classList.add('blink'));
            setTimeout(() => {
                eyes.forEach(e => e.classList.remove('blink'));
                // Next blink random interval
                setTimeout(blink, Math.random() * 3000 + 3000);
            }, 100); // 100ms closed duration
        };
        setTimeout(blink, 2000);
    }

    setEyeStatus(aqi) {
        const eyes = document.querySelectorAll('.eye');
        eyes.forEach(e => {
            e.classList.remove('status-good', 'status-moderate', 'status-bad');
            if (aqi <= 50) e.classList.add('status-good'); // Green
            else if (aqi <= 100) e.classList.add('status-moderate'); // Orange
            else e.classList.add('status-bad'); // Red
        });
    }

    setAvatarSpeaking(speaking) {
        const eyes = document.querySelectorAll('.eye');
        eyes.forEach(e => e.classList.toggle('speaking', speaking));
    }

    // ==========================================
    // CONFIGURATION SYNC
    // ==========================================

    async loadConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();

            // Apply to UI
            if (data.customPrompt) {
                document.getElementById('customPrompt').value = data.customPrompt;
            }

            if (data.sensorData) this.updateSensorUI(data.sensorData);

        } catch (e) {
            console.error('Failed to load config', e);
        }
    }

    async deployConfig() {
        // Gather data from UI
        const payload = {
            customPrompt: document.getElementById('customPrompt').value,
            features: { rag: true, iot: true, safety: true } // Hardcoded default features
        };

        try {
            const btn = document.getElementById('deployConfigBtn');
            const originalText = btn.innerHTML;
            btn.textContent = '⏳ Updating...';

            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            // Notify
            btn.textContent = '✅ Updated!';
            setTimeout(() => btn.innerHTML = originalText, 2000);

            this.addMessage('system', '🔄 AirOwl directives updated.');

        } catch (e) {
            console.error('Deploy failed', e);
            alert('Failed to update: ' + e.message);
        }
    }

    loadScenarioUI(scenario) {
        const scenarios = {
            'good': { aqi: 35, pm25: 25, temperature: 24, location: 'Forest Reserve' },
            'moderate': { aqi: 85, pm25: 65, temperature: 30, location: 'City Park' },
            'hazardous': { aqi: 380, pm25: 350, temperature: 18, location: 'Traffic Zone' }
        };

        const data = scenarios[scenario];
        if (data) {
            this.deploySensorData(data);
        }
    }

    // Helper to send sensor data to backend immediately
    async deploySensorData(data) {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sensorData: data })
        });
        this.updateSensorUI(data);
    }

    updateSensorUI(data) {
        if (!data) return;
        document.getElementById('aqiValue').textContent = data.aqi || '--';
        document.getElementById('pm25Value').textContent = data.pm25 || '--';
        document.getElementById('tempValue').textContent = (data.temperature || '--') + '°';
        document.getElementById('sensorLocation').textContent = data.location || '--';

        // Update Eyes
        this.setEyeStatus(data.aqi || 0);

        // Color coding for AQI Circle
        const aqi = data.aqi || 0;
        const circle = document.querySelector('.air-quality-circle');

        let color = '#00E676';
        if (aqi > 50) color = '#FFAB00';
        if (aqi > 200) color = '#FF1744';

        if (circle) circle.style.borderColor = color;
    }

    // ==========================================
    // WEBRTC & RTVI
    // ==========================================

    async connect() {
        try {
            this.updateStatus('connecting');
            this.addMessage('system', 'Waking up AirOwl...');

            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true }
            });

            this.peerConnection = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });

            this.dataChannel = this.peerConnection.createDataChannel('rtvi', { ordered: true });
            this.setupDataChannel(this.dataChannel);

            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });

            this.peerConnection.ontrack = (event) => {
                if (event.track.kind === 'audio') {
                    this.remoteAudio = new Audio();
                    this.remoteAudio.srcObject = event.streams[0];
                    this.remoteAudio.play().catch(e => console.log('Autoplay blocked', e));
                }
            };

            this.peerConnection.onconnectionstatechange = () => {
                const state = this.peerConnection.connectionState;
                console.log('Connection:', state);
                if (state === 'connected') this.onConnected();
                else if (['disconnected', 'closed', 'failed'].includes(state)) this.onDisconnected();
            };

            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);

            // Wait for ICE
            await new Promise(resolve => setTimeout(resolve, 1000));

            const response = await fetch('/api/offer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sdp: this.peerConnection.localDescription.sdp,
                    type: this.peerConnection.localDescription.type
                })
            });

            const answer = await response.json();
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(answer));

            document.getElementById('startBtn').style.display = 'none';
            document.getElementById('stopBtn').style.display = 'block';

        } catch (e) {
            console.error('Connection failed', e);
            this.updateStatus('disconnected');
            this.addMessage('system', '❌ Link failed: ' + e.message);
        }
    }

    setupDataChannel(channel) {
        channel.onopen = () => {
            console.log('Data channel open');
            this.pingInterval = setInterval(() => {
                if (channel.readyState === 'open') channel.send('ping:' + Date.now());
            }, 1000);
        };
        channel.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                if (msg.label === 'rtvi-ai') this.handleRTVI(msg);
            } catch (err) { }
        };
    }

    handleRTVI(msg) {
        const { type, data } = msg;
        const now = Date.now();

        switch (type) {
            case 'user-started-speaking':
                this.metrics.speechStart = now;
                // Reset latency markers
                this.metrics.vadEnd = null;
                this.metrics.sttEnd = null;
                this.metrics.llmStart = null;
                break;

            case 'user-stopped-speaking':
                this.metrics.vadEnd = now;
                break;

            case 'user-transcription':
                if (data.final) {
                    this.addMessage('user', data.text);
                    this.metrics.sttEnd = now;

                    // STT Latency: VAD End -> Text Available
                    // Fallback to Speech Start if VAD End missing
                    const refInfo = this.metrics.vadEnd || this.metrics.speechStart;
                    if (refInfo) {
                        this.recordMetric('stt', now - refInfo);
                    }
                }
                break;

            case 'bot-llm-started':
                this.metrics.llmStart = now;
                // LLM Latency: Text Available -> LLM Processing Start
                if (this.metrics.sttEnd) {
                    this.recordMetric('llm', now - this.metrics.sttEnd);
                }
                break;

            case 'bot-tts-started':
                // TTS Latency: LLM Start -> Audio Start (First Token to Audio)
                if (this.metrics.llmStart) {
                    this.recordMetric('tts', now - this.metrics.llmStart);
                }
                this.setAvatarSpeaking(true);
                break;

            case 'bot-tts-text':
                this.addMessage('assistant', data.text);
                break;

            case 'bot-stopped-speaking':
                this.setAvatarSpeaking(false);
                break;
        }
    }

    recordMetric(type, value) {
        if (!this.metrics[type]) this.metrics[type] = [];
        this.metrics[type].push(value);
        if (this.metrics[type].length > 10) this.metrics[type].shift();

        // Show INSTANT value 
        const latestInfo = value;

        // Update DOM
        const el = document.getElementById(type + 'Time');
        if (el) {
            el.textContent = latestInfo;
            el.style.fontWeight = '800';
            setTimeout(() => el.style.fontWeight = '600', 300);
        }
    }

    disconnect() {
        if (this.peerConnection) this.peerConnection.close();
        if (this.localStream) this.localStream.getTracks().forEach(t => t.stop());
        if (this.pingInterval) clearInterval(this.pingInterval);

        this.updateStatus('disconnected');
        document.getElementById('startBtn').style.display = 'block';
        document.getElementById('stopBtn').style.display = 'none';
        this.addMessage('system', 'Session Ended');
        this.setAvatarSpeaking(false);
    }

    onConnected() {
        this.isConnected = true;
        this.updateStatus('connected');
        this.addMessage('system', 'AirOwl is Listening...');
    }

    onDisconnected() {
        this.isConnected = false;
        this.updateStatus('disconnected');
    }

    updateStatus(status) {
        const el = document.getElementById('connectionStatus');
        el.className = `connection-status ${status}`;
        el.querySelector('.status-text').textContent = status === 'connected' ? 'LIVE' : status === 'connecting' ? 'SYNCING...' : 'STANDBY';
    }

    addMessage(role, text) {
        const div = document.createElement('div');
        div.className = `bubble ${role}`;

        // Add label if AI
        if (role === 'assistant') {
            div.innerHTML = `<span class="bubble-label">AIROWL</span>${text}`;
        } else if (role === 'user') {
            div.innerHTML = `<span class="bubble-label" style="text-align:right">YOU</span>${text}`;
        } else {
            div.textContent = text;
        }

        const log = document.getElementById('chatContainer');
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new ClimateBuddyApp();
});
