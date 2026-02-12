/**
 * News Anchor Voice AI Controller
 * India AI Impact Summit 2026 - Session 5
 */

class NewsAnchorApp {
    constructor() {
        this.peerConnection = null;
        this.localStream = null;
        this.remoteAudio = null;
        this.dataChannel = null;
        this.isConnected = false;

        // State
        this.config = {
            customPrompt: '',
            features: { live_news: true, mock_fallback: true },
            llmParams: { temperature: 0.3, max_tokens: 100 },
            newsCategory: 'headlines',
            anchorStyle: 'professional'
        };

        this.metrics = { stt: [], llm: [], tts: [] };
        this.currentNews = [];

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadConfig();
        this.loadNews();
        console.log('📰 News Anchor Initialized');
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

        // Category Buttons
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.setCategory(e.currentTarget.dataset.category);
            });
        });

        // Style Buttons
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.config.anchorStyle = e.currentTarget.dataset.style;
            });
        });

        // Refresh News
        document.getElementById('refreshNewsBtn')?.addEventListener('click', () => this.refreshNews());

        // Sliders
        document.getElementById('llmTokens')?.addEventListener('input', (e) => {
            document.getElementById('tokensDisplay').textContent = e.target.value;
            this.config.llmParams.max_tokens = parseInt(e.target.value);
        });

        document.getElementById('llmTemp')?.addEventListener('input', (e) => {
            document.getElementById('tempDisplay').textContent = e.target.value;
            this.config.llmParams.temperature = parseFloat(e.target.value);
        });
    }

    switchTab(btn) {
        // Update Nav
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update Views
        const tabId = btn.dataset.tab;
        document.querySelectorAll('.view-panel').forEach(view => view.classList.remove('active'));

        if (tabId === 'dashboard') {
            document.getElementById('view-dashboard').classList.add('active');
        } else {
            document.getElementById('view-config').classList.add('active');
        }
    }

    // ==========================================
    // ANCHOR AVATAR ANIMATION
    // ==========================================

    setAnchorSpeaking(speaking) {
        const container = document.getElementById('anchorContainer');
        const status = document.getElementById('avatarStatus');

        if (speaking) {
            container?.classList.add('speaking');
            if (status) status.textContent = 'Reporting...';
        } else {
            container?.classList.remove('speaking');
            if (status) status.textContent = 'Ready to Report';
        }
    }

    setAnchorListening(listening) {
        const status = document.getElementById('avatarStatus');
        if (listening && status) {
            status.textContent = 'Listening...';
        }
    }

    // ==========================================
    // NEWS MANAGEMENT
    // ==========================================

    async loadNews(category = null) {
        const cat = category || this.config.newsCategory;
        try {
            const res = await fetch(`/api/news?category=${cat}`);
            const data = await res.json();
            this.currentNews = data.articles || [];
            this.updateHeadlinesUI(this.currentNews);
            this.updateTimestamp(data.timestamp);
        } catch (e) {
            console.error('Failed to load news', e);
        }
    }

    async setCategory(category) {
        this.config.newsCategory = category;
        await this.loadNews(category);

        // Update backend
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ newsCategory: category })
        });

        this.addMessage('system', `📂 Switched to ${category} news`);
    }

    async refreshNews() {
        const btn = document.getElementById('refreshNewsBtn');
        if (btn) {
            btn.textContent = '⏳ Refreshing...';
            btn.disabled = true;
        }

        try {
            await fetch('/api/news/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: this.config.newsCategory })
            });

            await this.loadNews();
            this.addMessage('system', '🔄 News refreshed!');
        } catch (e) {
            console.error('Failed to refresh news', e);
        } finally {
            if (btn) {
                btn.textContent = '🔄 Refresh News';
                btn.disabled = false;
            }
        }
    }

    updateHeadlinesUI(articles) {
        const container = document.getElementById('headlinesPreview');
        if (!container || !articles.length) return;

        container.innerHTML = articles.slice(0, 3).map((article, i) => `
            <div class="headline-item">
                <span class="headline-num">${i + 1}</span>
                <span class="headline-text">${article.title || 'No title'}</span>
                <span class="headline-source">${article.source || ''}</span>
            </div>
        `).join('');
    }

    updateTimestamp(timestamp) {
        const el = document.getElementById('newsTimestamp');
        if (el && timestamp) {
            const date = new Date(timestamp);
            el.textContent = `Last updated: ${date.toLocaleTimeString()}`;
        }
    }

    // ==========================================
    // CONFIGURATION
    // ==========================================

    async loadConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();

            if (data.customPrompt) {
                document.getElementById('customPrompt').value = data.customPrompt;
            }

            if (data.newsCategory) {
                this.config.newsCategory = data.newsCategory;
                // Update UI
                document.querySelectorAll('.category-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.category === data.newsCategory);
                });
            }

            if (data.anchorStyle) {
                this.config.anchorStyle = data.anchorStyle;
                document.querySelectorAll('.style-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.style === data.anchorStyle);
                });
            }

        } catch (e) {
            console.error('Failed to load config', e);
        }
    }

    async deployConfig() {
        const payload = {
            customPrompt: document.getElementById('customPrompt')?.value || '',
            anchorStyle: this.config.anchorStyle,
            llmParams: this.config.llmParams,
            features: {
                live_news: document.getElementById('liveNewsToggle')?.checked ?? true
            }
        };

        try {
            const btn = document.getElementById('deployConfigBtn');
            const originalText = btn?.innerHTML;
            if (btn) btn.textContent = '⏳ Updating...';

            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (btn) {
                btn.textContent = '✅ Updated!';
                setTimeout(() => btn.innerHTML = originalText, 2000);
            }

            this.addMessage('system', '🔄 Anchor settings updated.');

        } catch (e) {
            console.error('Deploy failed', e);
            alert('Failed to update: ' + e.message);
        }
    }

    // ==========================================
    // WEBRTC & RTVI
    // ==========================================

    async connect() {
        try {
            this.updateStatus('connecting');
            this.addMessage('system', '🎙️ Waking up News Anchor...');

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

            // Wait for ICE gathering to complete
            if (this.peerConnection.iceGatheringState !== 'complete') {
                await new Promise(resolve => {
                    const checkState = () => {
                        if (this.peerConnection.iceGatheringState === 'complete') {
                            this.peerConnection.removeEventListener('icegatheringstatechange', checkState);
                            resolve();
                        }
                    };
                    this.peerConnection.addEventListener('icegatheringstatechange', checkState);
                });
            }

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
            this.addMessage('system', '❌ Connection failed: ' + e.message);
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
                this.setAnchorListening(true);
                break;

            case 'user-stopped-speaking':
                this.metrics.vadEnd = now;
                break;

            case 'user-transcription':
                if (data.final) {
                    this.addMessage('user', data.text);
                    this.metrics.sttEnd = now;

                    const refInfo = this.metrics.vadEnd || this.metrics.speechStart;
                    if (refInfo) {
                        this.recordMetric('stt', now - refInfo);
                    }
                }
                break;

            case 'bot-llm-started':
                this.metrics.llmStart = now;
                if (this.metrics.sttEnd) {
                    this.recordMetric('llm', now - this.metrics.sttEnd);
                }
                break;

            case 'bot-tts-started':
                if (this.metrics.llmStart) {
                    this.recordMetric('tts', now - this.metrics.llmStart);
                }
                this.setAnchorSpeaking(true);
                break;

            case 'bot-tts-text':
                this.addMessage('assistant', data.text);
                break;

            case 'bot-stopped-speaking':
                this.setAnchorSpeaking(false);
                break;
        }
    }

    recordMetric(type, value) {
        if (!this.metrics[type]) this.metrics[type] = [];
        this.metrics[type].push(value);
        if (this.metrics[type].length > 10) this.metrics[type].shift();

        const el = document.getElementById(type + 'Time');
        if (el) {
            el.textContent = value;
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
        this.addMessage('system', '📴 Session Ended');
        this.setAnchorSpeaking(false);
    }

    onConnected() {
        this.isConnected = true;
        this.updateStatus('connected');
        this.addMessage('system', '🎙️ News Anchor is LIVE! Ask about any news topic.');
    }

    onDisconnected() {
        this.isConnected = false;
        this.updateStatus('disconnected');
    }

    updateStatus(status) {
        const el = document.getElementById('connectionStatus');
        el.className = `connection-status ${status}`;
        const statusText = {
            'connected': 'ON AIR',
            'connecting': 'CONNECTING...',
            'disconnected': 'STANDBY'
        };
        el.querySelector('.status-text').textContent = statusText[status] || 'STANDBY';
    }

    addMessage(role, text) {
        const div = document.createElement('div');
        div.className = `bubble ${role}`;

        if (role === 'assistant') {
            div.innerHTML = `<span class="bubble-label">NewsBot</span>${text}`;
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
    window.app = new NewsAnchorApp();
});
