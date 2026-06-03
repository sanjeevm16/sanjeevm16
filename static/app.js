document.addEventListener('DOMContentLoaded', () => {
    let sessionId = localStorage.getItem('sessionId');
    if (!sessionId) {
        sessionId = Math.random().toString(36).substring(2, 15);
        localStorage.setItem('sessionId', sessionId);
    }

    const chatCard = document.getElementById('chat-card');
    const chatBody = document.getElementById('chat-body');
    const textInput = document.getElementById('text-input');
    const sendButton = document.getElementById('send-button');
    const avatarContainer = document.getElementById('avatar-container');
    const avatarMouth = document.getElementById('avatar-mouth');
    const voiceSelect = document.getElementById('voice-select');
    const companionTitle = document.getElementById('companion-title');
    const thinkingRow = document.getElementById('thinking-row');
    const tabButtons = document.querySelectorAll('.tab-btn');

    let currentIndustry = 'hospitality';
    let voices = [];
    let lipSyncInterval;
    let typewriterTimeout;

    const greetings = {};
    greetings.hospitality = "Hello! I'm your Hospitality Companion. " +
        "How can I assist you with booking or guest queries today?";
    greetings.public_sector = "Welcome to Citizen Support. " +
        "How can I help you with permits, city forms, or civic compliance services today?";
    greetings.hospitals = "Hello, I am your Healthcare Assistant. " +
        "How can I check your appointments, billing details, or record requests today?";
    greetings.manufacturing = "Operations Support System active. " +
        "Please submit shipment tracking requests, order details, or parts queries.";

    const titles = {};
    titles.hospitality = "Hospitality Companion";
    titles.public_sector = "Public Sector Companion";
    titles.hospitals = "Healthcare Companion";
    titles.manufacturing = "Manufacturing Companion";

    const thinkingPhrases = {};
    thinkingPhrases.hospitality = "Checking details.";
    thinkingPhrases.public_sector = "Accessing records.";
    thinkingPhrases.hospitals = "Retrieving record.";
    thinkingPhrases.manufacturing = "Querying data.";

    function populateVoiceList() {
        const allVoices = speechSynthesis.getVoices();
        voices = allVoices.filter(voice => voice.name.includes('Google'));
        if (voices.length === 0) {
            voices = allVoices;
        }
        voiceSelect.innerHTML = '';

        let usVoiceIndex = -1;

        voices.forEach((voice, i) => {
            const option = document.createElement('option');
            option.textContent = `${voice.name} (${voice.lang})`;
            option.setAttribute('data-lang', voice.lang);
            option.setAttribute('data-name', voice.name);
            voiceSelect.appendChild(option);

            if (voice.lang === 'en-US') {
                if (usVoiceIndex === -1) {
                    usVoiceIndex = i;
                }
            }
        });

        if (usVoiceIndex !== -1) {
            voiceSelect.selectedIndex = usVoiceIndex;
        }
    }

    populateVoiceList();
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = populateVoiceList;
    }

    // Toggle Industry Tabs
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const industry = button.getAttribute('data-industry');
            if (industry === currentIndustry) return;

            // Reset talking / typing
            if (speechSynthesis.speaking) {
                speechSynthesis.cancel();
            }
            if (typewriterTimeout) {
                clearTimeout(typewriterTimeout);
            }
            clearInterval(lipSyncInterval);
            avatarMouth.setAttribute('y', '130');
            avatarMouth.setAttribute('height', '5');
            avatarMouth.setAttribute('rx', '2.5');
            avatarContainer.classList.remove('speaking');

            // Toggle active tabs
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Update UI properties
            currentIndustry = industry;
            chatCard.setAttribute('data-theme', industry);
            companionTitle.textContent = titles[industry];

            // Re-render chat messages with greeting
            chatBody.innerHTML = '';
            const greetRow = document.createElement('div');
            greetRow.className = 'message-row bot';
            greetRow.innerHTML = `<div class="message-bubble">${greetings[industry]}</div>`;
            chatBody.appendChild(greetRow);
            chatBody.scrollTop = chatBody.scrollHeight;
        });
    });

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    const typewriter = (text, element, speed = 35) => {
        if (typewriterTimeout) {
            clearTimeout(typewriterTimeout);
        }

        let segmentIndex = 0;
        element.innerHTML = "";

        if (window.Intl && Intl.Segmenter) {
            const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
            const segments = Array.from(segmenter.segment(text)).map(s => s.segment);

            function typeGrapheme() {
                if (segmentIndex < segments.length) {
                    element.innerHTML += segments[segmentIndex];
                    segmentIndex++;
                    chatBody.scrollTop = chatBody.scrollHeight;
                    typewriterTimeout = setTimeout(typeGrapheme, speed);
                } else {
                    typewriterTimeout = null;
                }
            }
            typeGrapheme();
        } else {
            function typeChar() {
                if (segmentIndex < text.length) {
                    element.innerHTML += text.charAt(segmentIndex);
                    segmentIndex++;
                    chatBody.scrollTop = chatBody.scrollHeight;
                    typewriterTimeout = setTimeout(typeChar, speed);
                } else {
                    typewriterTimeout = null;
                }
            }
            typeChar();
        }
    };

    const speak = (text) => {
        if (speechSynthesis.speaking) {
            speechSynthesis.cancel();
        }
        clearInterval(lipSyncInterval);
        avatarContainer.classList.remove('speaking');

        if (!voiceSelect.selectedOptions || voiceSelect.selectedOptions.length === 0) {
            return;
        }

        const selectedOption = voiceSelect.selectedOptions[0].getAttribute('data-name');
        const selectedVoice = voices.find(voice => voice.name === selectedOption);

        const utterance = new SpeechSynthesisUtterance(text);
        if (selectedVoice) {
            utterance.voice = selectedVoice;
        }

        utterance.onstart = () => {
            avatarContainer.classList.add('speaking');
            let mouthOpen = true;
            lipSyncInterval = setInterval(() => {
                if (mouthOpen) {
                    avatarMouth.setAttribute('y', '120');
                    avatarMouth.setAttribute('height', '30');
                    avatarMouth.setAttribute('rx', '15');
                } else {
                    avatarMouth.setAttribute('y', '130');
                    avatarMouth.setAttribute('height', '5');
                    avatarMouth.setAttribute('rx', '2.5');
                }
                mouthOpen = !mouthOpen;
            }, 150);
        };

        const stopSpeaking = () => {
            clearInterval(lipSyncInterval);
            avatarContainer.classList.remove('speaking');
            avatarMouth.setAttribute('y', '130');
            avatarMouth.setAttribute('height', '5');
            avatarMouth.setAttribute('rx', '2.5');
        };

        utterance.onend = stopSpeaking;
        utterance.onerror = stopSpeaking;

        speechSynthesis.speak(utterance);
    };

    const handleSendMessage = async () => {
        const message = textInput.value.trim();
        if (!message) return;

        // Unlock audio context on mobile (iOS/Safari/Android) using a sync speech trigger
        speak(thinkingPhrases[currentIndustry]);

        // Render user bubble
        const userRow = document.createElement('div');
        userRow.className = 'message-row user';
        userRow.innerHTML = `<div class="message-bubble">${escapeHtml(message)}</div>`;
        chatBody.appendChild(userRow);

        textInput.value = '';
        textInput.style.height = 'auto';
        chatBody.scrollTop = chatBody.scrollHeight;

        // Display thinking loader
        thinkingRow.style.display = 'flex';
        chatBody.scrollTop = chatBody.scrollHeight;

        try {
            const payload = {};
            payload.message = message;
            payload.session_id = sessionId;
            payload.industry = currentIndustry;

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            thinkingRow.style.display = 'none';

            // Render bot bubble
            const botRow = document.createElement('div');
            botRow.className = 'message-row bot';
            botRow.innerHTML = `<div class="message-bubble"></div>`;
            chatBody.appendChild(botRow);

            const bubble = botRow.querySelector('.message-bubble');
            typewriter(data.response, bubble);
            speak(data.response);
        } catch (error) {
            console.error('Error:', error);
            thinkingRow.style.display = 'none';

            const errorMessage = 'Sorry, something went wrong. Please try again.';
            const botRow = document.createElement('div');
            botRow.className = 'message-row bot';
            botRow.innerHTML = `<div class="message-bubble"></div>`;
            chatBody.appendChild(botRow);

            const bubble = botRow.querySelector('.message-bubble');
            typewriter(errorMessage, bubble);
            speak(errorMessage);
        }
    };

    sendButton.addEventListener('click', handleSendMessage);

    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    textInput.addEventListener('input', () => {
        textInput.style.height = 'auto';
        textInput.style.height = `${textInput.scrollHeight}px`;
    });
});
