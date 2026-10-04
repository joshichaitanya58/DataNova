document.addEventListener('DOMContentLoaded', function () {

    /* ---------------------------------------------------------------------
       1. "Ask Your Data" AI Copilot Chatbot Engine
       ------------------------------------------------------------------- */
    const askDataModalEl = document.getElementById("askDataModal");
    const openAskDataBtns = document.querySelectorAll(".dn-open-ask-modal");
    const askInput = document.getElementById('dnAskInput');
    const askForm = document.getElementById('dnAskForm');
    const askSubmitBtn = document.getElementById('btnSubmitAskAI');
    const chatStreamBox = document.getElementById('dnChatStreamBox');
    const chatWelcomeHero = document.getElementById('dnChatWelcomeHero');
    const chatMessagesList = document.getElementById('dnChatMessagesList');
    const aiTypingIndicator = document.getElementById('dnAiTypingIndicator');
    const clearChatBtn = document.getElementById('dnBtnClearChat');
    const voiceInputBtn = document.getElementById('dnBtnVoiceInput');
    const clearInputBtn = document.getElementById('dnBtnClearInput');
    const chatDatasetNameEl = document.getElementById('dnChatDatasetName');
    const langSelect = document.getElementById('dnAskLanguage');

    let chatHistory = [];
    let isAiResponding = false;
    let recognition = null;
    let isListening = false;

    // Helper: Sync Active Dataset Name in Chat Header Badge
    function syncChatDatasetBadge() {
        if (!chatDatasetNameEl) return;
        const selectEl = document.getElementById('datasetSelect');
        const activeOption = selectEl ? selectEl.options[selectEl.selectedIndex] : null;
        const currentName = activeOption ? activeOption.text.trim() : (window.activeDatasetName || '');
        
        if (activeDatasetId) {
            chatDatasetNameEl.innerHTML = `<span class="text-success fw-semibold">● Active:</span> ${currentName || 'Dataset #' + activeDatasetId}`;
        } else {
            chatDatasetNameEl.innerHTML = `<span class="text-warning fw-semibold">⚠ No dataset selected</span>`;
        }
    }

    function openAskModal(e) {
        if (e && e.preventDefault) e.preventDefault();
        syncChatDatasetBadge();
        if (askDataModalEl && typeof bootstrap !== 'undefined') {
            const bsModal = bootstrap.Modal.getOrCreateInstance(askDataModalEl);
            bsModal.show();
        }
        setTimeout(() => {
            if (askInput) askInput.focus();
        }, 250);
    }

    openAskDataBtns.forEach(btn => btn.addEventListener("click", openAskModal));

    // Markdown Formatter for AI Responses
    function formatAiMarkdown(text) {
        if (!text) return '';
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Code blocks
        escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre class="bg-dark text-light p-2.5 rounded-3 small my-2 overflow-x-auto"><code>$1</code></pre>');
        // Inline code
        escaped = escaped.replace(/`([^`]+)`/g, '<code class="bg-body-secondary px-1.5 py-0.5 rounded text-primary small">$1</code>');
        // Bold
        escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-body fw-bold">$1</strong>');
        // Italic
        escaped = escaped.replace(/\*([^*]+)\*/g, '<em class="text-body-secondary">$1</em>');
        // Bullet points
        escaped = escaped.replace(/^[\s]*[-•*]\s+(.*)$/gm, '<div class="d-flex align-items-start gap-2 my-1"><i class="bi bi-arrow-right-short text-primary mt-0.5 flex-shrink-0 fs-6"></i><span>$1</span></div>');
        // Numbered lists
        escaped = escaped.replace(/^[\s]*(\d+)\.\s+(.*)$/gm, '<div class="d-flex align-items-start gap-2 my-1"><span class="badge bg-primary-subtle text-primary border rounded-pill px-1.5 py-0.5 small flex-shrink-0" style="font-size:10px;">$1</span><span>$2</span></div>');
        // Headers (### Header)
        escaped = escaped.replace(/^###\s+(.*)$/gm, '<h6 class="fw-bold text-primary mt-2 mb-1">$1</h6>');
        escaped = escaped.replace(/^##\s+(.*)$/gm, '<h6 class="fw-bold text-body mt-2 mb-1">$1</h6>');
        // Line breaks / Paragraphs
        escaped = escaped.replace(/\n\n/g, '<div class="my-2"></div>');
        escaped = escaped.replace(/\n/g, '<br>');
        return escaped;
    }

    // Scroll chat to bottom
    function scrollChatToBottom() {
        if (chatStreamBox) {
            chatStreamBox.scrollTop = chatStreamBox.scrollHeight;
        }
    }

    // Render User Message Bubble
    function appendUserMessage(text) {
        if (chatWelcomeHero) chatWelcomeHero.style.display = 'none';
        if (chatMessagesList) chatMessagesList.style.display = 'flex';

        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const msgRow = document.createElement('div');
        msgRow.className = 'dn-chat-msg-row user';
        msgRow.innerHTML = `
            <div class="dn-chat-bubble-user">
                <div>${text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                <div class="text-end mt-1 text-white text-opacity-75" style="font-size: 10px;">${timeStr}</div>
            </div>
            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center flex-shrink-0 shadow-sm" style="width:34px;height:34px;font-size:12px;font-weight:600;">
                <i class="bi bi-person-fill"></i>
            </div>
        `;
        if (chatMessagesList) chatMessagesList.appendChild(msgRow);
        scrollChatToBottom();
    }

    // Render AI Assistant Message Bubble
    function appendAiMessage(answerText, isError = false) {
        if (chatMessagesList) chatMessagesList.style.display = 'flex';
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const msgId = 'ai-msg-' + Date.now();
        const formattedHtml = isError 
            ? `<div class="text-danger small"><i class="bi bi-exclamation-octagon-fill me-1"></i>${answerText}</div>`
            : `<div class="dn-ai-content">${formatAiMarkdown(answerText)}</div>`;

        const msgRow = document.createElement('div');
        msgRow.className = 'dn-chat-msg-row ai';
        msgRow.innerHTML = `
            <div class="dn-ai-avatar-orb" style="width: 34px; height: 34px; border-radius: 10px; font-size: 0.9rem;">
                <i class="bi bi-stars"></i>
            </div>
            <div class="dn-chat-bubble-ai" id="${msgId}">
                <div class="d-flex align-items-center justify-content-between mb-1.5 pb-1 border-bottom border-secondary border-opacity-10">
                    <span class="fw-bold small text-primary d-flex align-items-center gap-1" style="font-size: 11px;">
                        <i class="bi bi-cpu-fill"></i>DataNova AI
                    </span>
                    <div class="d-flex align-items-center gap-1">
                        ${!isError ? `
                            <button type="button" class="btn btn-sm btn-link text-secondary p-0 px-1 dn-ai-speak-btn" title="Read Aloud (Listen)">
                                <i class="bi bi-volume-up"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-link text-secondary p-0 px-1 dn-copy-ai-bubble-btn" title="Copy Answer">
                                <i class="bi bi-clipboard"></i>
                            </button>
                        ` : ''}
                        <span class="text-secondary ms-1" style="font-size: 10px;">${timeStr}</span>
                    </div>
                </div>
                ${formattedHtml}
            </div>
        `;
        if (chatMessagesList) chatMessagesList.appendChild(msgRow);
        scrollChatToBottom();
    }

    // Submit Query to /api/ask_data
    function submitAiQuery(question) {
        if (!question || isAiResponding) return;

        if (!activeDatasetId) {
            if (window.showToast) window.showToast("Please upload or select an active dataset first.", "warning");
            syncChatDatasetBadge();
            return;
        }

        appendUserMessage(question);
        if (askInput) askInput.value = '';
        if (clearInputBtn) clearInputBtn.style.display = 'none';

        isAiResponding = true;
        if (askSubmitBtn) {
            askSubmitBtn.disabled = true;
            askSubmitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span><span>Thinking...</span>';
        }
        if (aiTypingIndicator) {
            aiTypingIndicator.style.display = 'flex';
            scrollChatToBottom();
        }

        const selectedLang = langSelect ? langSelect.value : 'en';

        fetch('/api/ask_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: activeDatasetId,
                question: question,
                language: selectedLang
            })
        })
        .then(res => res.json())
        .then(data => {
            if (aiTypingIndicator) aiTypingIndicator.style.display = 'none';
            if (data.success && data.answer) {
                appendAiMessage(data.answer, false);
                chatHistory.push({ role: 'user', content: question });
                chatHistory.push({ role: 'assistant', content: data.answer });
            } else {
                appendAiMessage(data.message || 'Failed to analyze your query. Please verify dataset columns.', true);
            }
        })
        .catch(err => {
            console.error("Ask Data Copilot Error:", err);
            if (aiTypingIndicator) aiTypingIndicator.style.display = 'none';
            appendAiMessage('Network error: Could not reach the DataNova AI Analytics engine. Please try again.', true);
        })
        .finally(() => {
            isAiResponding = false;
            if (askSubmitBtn) {
                askSubmitBtn.disabled = false;
                askSubmitBtn.innerHTML = '<i class="bi bi-send-fill small"></i><span class="d-none d-sm-inline">Ask AI</span>';
            }
            setTimeout(() => { if (askInput) askInput.focus(); }, 150);
        });
    }

    // Form Submit Listener
    if (askForm) {
        askForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const question = askInput ? askInput.value.trim() : '';
            if (question) {
                submitAiQuery(question);
            }
        });
    }

    // Input changes (toggle clear button)
    if (askInput) {
        askInput.addEventListener('input', function () {
            if (clearInputBtn) {
                clearInputBtn.style.display = this.value.trim() ? 'inline-block' : 'none';
            }
        });
    }

    // Clear input button
    if (clearInputBtn) {
        clearInputBtn.addEventListener('click', function () {
            if (askInput) {
                askInput.value = '';
                this.style.display = 'none';
                askInput.focus();
            }
        });
    }

    // Suggested Questions Starter Cards & Quick Prompt Chips
    document.addEventListener('click', function (e) {
        const chip = e.target.closest('.dn-suggested-q, .dn-chip-prompt');
        if (chip) {
            e.preventDefault();
            const prompt = chip.getAttribute('data-question') || chip.getAttribute('data-prompt') || chip.textContent.trim();
            if (prompt) {
                submitAiQuery(prompt);
            }
        }
    });

    // Reset / New Chat Button
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', function () {
            chatHistory = [];
            if (chatMessagesList) {
                chatMessagesList.innerHTML = '';
                chatMessagesList.style.display = 'none';
            }
            if (chatWelcomeHero) {
                chatWelcomeHero.style.display = 'block';
            }
            if (askInput) {
                askInput.value = '';
                if (clearInputBtn) clearInputBtn.style.display = 'none';
                askInput.focus();
            }
            syncChatDatasetBadge();
        });
    }

    // Copy AI Bubble Answer
    document.addEventListener('click', function (e) {
        const copyBtn = e.target.closest('.dn-copy-ai-bubble-btn');
        if (copyBtn) {
            const bubble = copyBtn.closest('.dn-chat-bubble-ai');
            const textEl = bubble ? (bubble.querySelector('.dn-ai-content') || bubble) : null;
            const textToCopy = textEl ? textEl.innerText.trim() : '';
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const icon = copyBtn.querySelector('i');
                    if (icon) icon.className = 'bi bi-check-lg text-success';
                    setTimeout(() => {
                        if (icon) icon.className = 'bi bi-clipboard';
                    }, 2000);
                }).catch(() => {
                    if (window.showToast) window.showToast('Could not copy to clipboard', 'warning');
                });
            }
        }
    });

    // Text-to-Speech (Listen Aloud)
    document.addEventListener('click', function (e) {
        const speakBtn = e.target.closest('.dn-ai-speak-btn');
        if (speakBtn) {
            if (!('speechSynthesis' in window)) {
                if (window.showToast) window.showToast("Speech synthesis is not supported in this browser.", "info");
                return;
            }
            if (window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
                speakBtn.innerHTML = '<i class="bi bi-volume-up"></i>';
                return;
            }
            const bubble = speakBtn.closest('.dn-chat-bubble-ai');
            const textEl = bubble ? (bubble.querySelector('.dn-ai-content') || bubble) : null;
            const textToRead = textEl ? textEl.innerText.trim() : '';
            if (textToRead) {
                const utterance = new SpeechSynthesisUtterance(textToRead);
                const selectedLang = langSelect ? langSelect.value : 'en';
                if (selectedLang === 'hi') utterance.lang = 'hi-IN';
                else if (selectedLang === 'mr') utterance.lang = 'mr-IN';
                else utterance.lang = 'en-US';

                utterance.onstart = () => { speakBtn.innerHTML = '<i class="bi bi-stop-circle-fill text-danger"></i>'; };
                utterance.onend = () => { speakBtn.innerHTML = '<i class="bi bi-volume-up"></i>'; };
                utterance.onerror = () => { speakBtn.innerHTML = '<i class="bi bi-volume-up"></i>'; };
                window.speechSynthesis.speak(utterance);
            }
        }
    });

    // Voice Input Speech-to-Text (Web Speech API)
    if (voiceInputBtn) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRec) {
            recognition = new SpeechRec();
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onstart = function () {
                isListening = true;
                voiceInputBtn.classList.add('dn-voice-active');
                if (askInput) askInput.placeholder = "Listening... speak now into your microphone";
            };

            recognition.onresult = function (event) {
                const transcript = event.results[0][0].transcript;
                if (askInput && transcript) {
                    askInput.value = transcript;
                    if (clearInputBtn) clearInputBtn.style.display = 'inline-block';
                    submitAiQuery(transcript);
                }
            };

            recognition.onerror = function (event) {
                console.warn("Speech recognition error:", event.error);
                isListening = false;
                voiceInputBtn.classList.remove('dn-voice-active');
                if (askInput) askInput.placeholder = "Ask anything about your dataset...";
            };

            recognition.onend = function () {
                isListening = false;
                voiceInputBtn.classList.remove('dn-voice-active');
                if (askInput) askInput.placeholder = "Ask anything about your dataset...";
            };

            voiceInputBtn.addEventListener('click', function () {
                if (isListening) {
                    recognition.stop();
                } else {
                    const selectedLang = langSelect ? langSelect.value : 'en';
                    if (selectedLang === 'hi') recognition.lang = 'hi-IN';
                    else if (selectedLang === 'mr') recognition.lang = 'mr-IN';
                    else recognition.lang = 'en-US';
                    try {
                        recognition.start();
                    } catch (err) {
                        console.error("Mic start failed:", err);
                    }
                }
            });
        } else {
            voiceInputBtn.title = "Voice typing is not supported on this browser";
            voiceInputBtn.style.opacity = '0.5';
        }
    }

    /* ---------------------------------------------------------------------
       Smooth Auto-Scroll Helper
       ------------------------------------------------------------------- */
    function smoothScrollToTarget(targetElement) {
        if (!targetElement) return;

        // If target container is hidden or has no height, find first visible child panel
        let elementToScroll = targetElement;
        if (targetElement.offsetHeight === 0 || targetElement.style.display === 'none') {
            const firstVisible = targetElement.querySelector('.dn-panel:not([style*="display: none"]), div:not([style*="display: none"])');
            if (firstVisible && firstVisible.offsetHeight > 0) {
                elementToScroll = firstVisible;
            }
        }

        if (targetElement.id) {
            sessionStorage.setItem('datanova_analyst_active_step', '#' + targetElement.id);
        }

        const topbar = document.querySelector('.dn-topbar');
        const topbarHeight = topbar ? topbar.offsetHeight : 68;
        const targetRect = elementToScroll.getBoundingClientRect();
        const absoluteTop = targetRect.top + window.pageYOffset;
        const targetScrollTop = Math.max(0, absoluteTop - topbarHeight - 16);

        window.scrollTo({
            top: targetScrollTop,
            behavior: 'smooth'
        });

        // Add sleek pulse animation to highlight section
        elementToScroll.classList.remove('dn-pulse');
        void elementToScroll.offsetWidth; // force reflow
        elementToScroll.classList.add('dn-pulse');
        setTimeout(() => elementToScroll.classList.remove('dn-pulse'), 1600);
    }

    /* ---------------------------------------------------------------------
       2. Quick Action Buttons
       ------------------------------------------------------------------- */
    document.querySelectorAll('.dn-quick-action').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const actionText = (btn.textContent || '').trim().toLowerCase();
            let targetId = '';

            if (actionText.includes('upload dataset')) {
                targetId = 'upload';
            } else if (actionText.includes('clean data')) {
                targetId = 'step-cleaning';
            } else if (actionText.includes('run eda')) {
                targetId = 'step-eda';
            } else if (actionText.includes('ask ai')) {
                const openModalBtn = document.querySelector('.dn-open-ask-modal');
                if (openModalBtn) openModalBtn.click();
                return;
            } else if (actionText.includes('generate report')) {
                targetId = 'step-reports';
            }

            if (targetId) {
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    if (targetId !== 'upload' && !activeDatasetId) {
                        showToast('Please upload a dataset to access this feature.', 'info');
                    } else {
                        smoothScrollToTarget(targetElement);
                    }
                }
            }
        });
    });


    /* ---------------------------------------------------------------------
       3. File Upload and Data Analysis Workflow
       ------------------------------------------------------------------- */
    var uploadForm = document.getElementById('dnUploadForm');
    var fileInput = document.getElementById('dnFileInput');
    var uploadProgress = document.getElementById('dnUploadProgress');
    var progressBar = document.getElementById('dnProgressBar');
    var uploadFilename = document.getElementById('dnUploadFilename');
    var uploadPercentage = document.getElementById('dnUploadPercentage');
    // Data preview elements
    var uploadPanel = document.getElementById('upload');
    var previewPanel = document.getElementById('dnDataPreviewPanel');
    var previewContent = document.getElementById('dnDataPreviewContent');
    var previewFilename = document.getElementById('dnPreviewFilename');
    var uploadAnotherBtn = document.getElementById('dnUploadAnotherBtn');
    var overviewPanel = document.getElementById('dnDatasetOverview');
    var overviewRows = document.getElementById('dnOverviewRows');
    var overviewCols = document.getElementById('dnOverviewCols');
    // Column info elements
    var columnInfoPanel = document.getElementById('dnColumnInfoPanel');
    var columnInfoContent = document.getElementById('dnColumnInfoContent');
    var columnInfoFooter = document.getElementById('dnColumnInfoFooter');
    var viewAllColsBtn = document.getElementById('dnViewAllColsBtn');
    // Missing values elements
    var missingValuePanel = document.getElementById('dnMissingValuePanel');
    var missingValueSummary = document.getElementById('dnMissingValueSummary');
    var missingValueContent = document.getElementById('dnMissingValueContent');
    var missingValueActions = document.getElementById('dnMissingValueActions');
    var missingColumnSelect = document.getElementById('dnMissingColumnSelect');
    var missingStrategySelect = document.getElementById('dnMissingStrategySelect');
    var missingCustomValueContainer = document.getElementById('dnMissingCustomValueContainer');
    var missingCustomValueInput = document.getElementById('dnMissingCustomValue');
    // Cleaned Data Preview elements
    var cleanedPreviewPanel = document.getElementById('dnCleanedDataPreviewPanel');
    var cleanedPreviewContent = document.getElementById('dnCleanedDataPreviewContent');
    var cleanedRows = document.getElementById('dnCleanedRows');
    var cleanedCols = document.getElementById('dnCleanedCols');
    var missingBefore = document.getElementById('dnMissingBefore');
    var missingAfter = document.getElementById('dnMissingAfter');
    var valuesFixed = document.getElementById('dnValuesFixed');
    var rowsRemoved = document.getElementById('dnRowsRemoved');
    // Duplicate detection elements
    var duplicatePanel = document.getElementById('dnDuplicatePanel');
    var duplicateSummary = document.getElementById('dnDuplicateSummary');
    var duplicatePreviewContent = document.getElementById('dnDuplicatePreviewContent');
    var removeFullDuplicatesBtn = document.getElementById('dnRemoveFullDuplicatesBtn');
    var subDuplicatesContainer = document.getElementById('dnSubDuplicatesContainer');
    // Subset duplicate elements
    var duplicateColumnSelect = document.getElementById('dnDuplicateColumnSelect');
    var findSubDuplicatesBtn = document.getElementById('dnFindSubDuplicatesBtn');
    var subDuplicateResult = document.getElementById('dnSubDuplicateResult');
    var applyCleaningBtn = document.getElementById('dnApplyCleaningBtn');
    // Statistical Summary elements
    var statsPanel = document.getElementById('dnStatsPanel');
    var statsContent = document.getElementById('dnStatsContent');
    // AI Cleaning Suggestions elements
    var aiSuggestionsPanel = document.getElementById('dnAISuggestionsPanel');
    var aiSuggestionsContent = document.getElementById('dnAISuggestionsContent');
    var getAISuggestionsBtn = document.getElementById('dnGetAISuggestionsBtn');
    var aiLoadingSpinner = document.getElementById('aiLoadingSpinner');
    var aiSuggestionsResult = document.getElementById('aiSuggestionsResult');
    var aiUnwantedColumnsList = document.getElementById('aiUnwantedColumnsList');
    var applyAIRemovalBtn = document.getElementById('dnApplyAIRemovalBtn');
    // Automatic EDA elements
    var autoEDAPanel = document.getElementById('dnAutoEDAPanel');
    var generateEDABtn = document.getElementById('dnGenerateEDABtn');
    var edaLoadingSpinner = document.getElementById('dnEDALoadingSpinner');
    var edaResultContainer = document.getElementById('dnEDAResultContainer');
    // Correlation Analysis elements
    var correlationPanel = document.getElementById('dnCorrelationPanel');
    var generateCorrelationBtn = document.getElementById('dnGenerateCorrelationBtn');
    var correlationLoadingSpinner = document.getElementById('dnCorrelationLoadingSpinner');
    var correlationAlertMsg = document.getElementById('dnCorrelationAlertMsg');
    var correlationResultContainer = document.getElementById('dnCorrelationResultContainer');
    var correlationHeatmap = document.getElementById('dnCorrelationHeatmap');
    var scatterXSelect = document.getElementById('dnScatterX');
    var scatterYSelect = document.getElementById('dnScatterY');
    var generateScatterBtn = document.getElementById('dnGenerateScatterBtn');
    var scatterPlotResult = document.getElementById('dnScatterPlotResult');

    const processingLoader = document.getElementById('dnProcessingLoader');
    // Initialize activeDatasetId from a hidden input field, allowing persistence across reloads
    let activeDatasetId = document.getElementById('initialActiveDatasetId')?.value || null;
    let currentActiveTask = null; // To store manager-assigned task metadata for active dataset
    let fullColumnInfo = []; // To store the complete list of columns
    let missingColumnInfo = []; // To store info about columns with missing values

    if (uploadAnotherBtn) {
        uploadAnotherBtn.style.display = activeDatasetId ? 'inline-flex' : 'none';
    }

    // Small shared helper so every fetch failure produces a visible message
    // instead of dying silently in the console.
    function showFetchError(context, err) {
        console.error(`[DataNova] ${context} failed:`, err);
        // Show a toast for user visibility
        showToast(`Error: ${context} failed. Please try again.`, "danger");
    }

    // Improved toast function (reused across the file)
    function showToast(message, type = 'info') {
        let container = document.getElementById('dnToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'dnToastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1090';
            document.body.appendChild(container);
        }

        const bgClass = type === 'success' ? 'bg-success text-white' :
            type === 'danger' ? 'bg-danger text-white' :
                type === 'warning' ? 'bg-warning text-dark' : 'bg-dark text-white';
        const toastHtml = `
        <div class="toast align-items-center ${bgClass} border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = toastHtml.trim();
        const toastEl = tempDiv.firstChild;
        if (toastEl) {
            container.appendChild(toastEl);
            setTimeout(() => {
                if (toastEl && toastEl.parentNode) {
                    toastEl.remove();
                }
            }, 4000);
        }
    }

    function updateCleaningStrategies() {
        if (!missingColumnSelect || !missingStrategySelect) return;

        const selectedColumnName = missingColumnSelect.value;
        let semanticType = 'generic'; // Default for "All Columns"

        if (selectedColumnName !== 'all_columns') {
            const selectedColInfo = missingColumnInfo.find(c => c.name === selectedColumnName);
            if (selectedColInfo) {
                semanticType = selectedColInfo.semantic_type;
            }
        }

        // Define strategies for each semantic type
        const strategies = {
            measure: ['remove_row', 'fill_mean', 'fill_median', 'fill_mode', 'fill_custom'],
            currency: ['remove_row', 'fill_mean', 'fill_median', 'fill_mode', 'fill_custom'],
            percentage: ['remove_row', 'fill_mean', 'fill_median', 'fill_mode', 'fill_custom'],
            numeric: ['remove_row', 'fill_mean', 'fill_median', 'fill_mode', 'fill_custom'],
            categorical: ['remove_row', 'fill_mode', 'fill_custom'],
            identifier: ['remove_row', 'fill_custom'],
            datetime: ['remove_row', 'ffill', 'bfill', 'fill_custom'],
            text: ['remove_row', 'fill_custom'],
            generic: ['remove_row', 'fill_custom'] // Safest default for mixed/all
        };

        const recommended = {
            numeric: 'fill_median',
            categorical: 'fill_mode'
        };

        const availableStrategies = strategies[semanticType] || strategies.generic;
        missingStrategySelect.innerHTML = ''; // Clear existing options

        availableStrategies.forEach(strategyKey => {
            const option = document.createElement('option');
            option.value = strategyKey;
            let text = strategyKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (strategyKey === recommended[semanticType]) {
                text += ' (Recommended)';
            }
            option.textContent = text;
            missingStrategySelect.appendChild(option);
        });

        // Trigger change on strategy select to hide/show custom input
        missingStrategySelect.dispatchEvent(new Event('change'));
    }

    function populateDatasetWorkspace(response, displayName, shouldScroll) {
        // FIX: log why nothing rendered instead of silently returning.
        if (!response || !response.success || !response.preview_html) {
            console.warn('[DataNova] populateDatasetWorkspace: cannot render, unexpected response shape:', response);
            return;
        }

        // Activate sidebar links that require a dataset
        document.querySelectorAll('.dn-requires-dataset').forEach(link => {
            link.classList.remove('dn-nav-disabled');
        });

        activeDatasetId = response.dataset_id;
        if (uploadAnotherBtn) {
            uploadAnotherBtn.style.display = 'inline-flex';
        }
        if (uploadForm) uploadForm.style.display = 'none';
        if (uploadProgress) uploadProgress.style.display = 'none';

        document.querySelectorAll('.dn-sampled-warning').forEach(function (warning) {
            warning.remove();
        });

        if (previewFilename) {
            previewFilename.textContent = `First 5 rows of ${displayName || response.file_name || 'your dataset'}`;
        }
        if (previewContent) previewContent.innerHTML = response.preview_html;
        if (previewPanel) previewPanel.style.display = 'block';

        if (response.is_sampled && previewPanel) {
            const sampledWarning = `
                <div class="dn-alert dn-alert-warn mt-3 dn-sampled-warning"><i class="bi bi-exclamation-triangle-fill"></i> <strong>Large File Mode:</strong> This dataset is large, so you are working with a representative sample of the data to ensure performance. Final downloads will use the full dataset.</div>
            `;
            previewPanel.insertAdjacentHTML('beforeend', sampledWarning);
        }

        if (overviewRows) overviewRows.textContent = response.row_count.toLocaleString();
        if (overviewCols) overviewCols.textContent = response.column_count.toLocaleString();

        const memoryElem = document.getElementById('dnOverviewMemory');
        if (memoryElem && response.memory_summary) {
            memoryElem.textContent = response.memory_summary.formatted_memory;
        }

        const domainElem = document.getElementById('dnOverviewDomain');
        if (domainElem && response.business_domain) {
            domainElem.textContent = response.business_domain;
        }

        const qualityElem = document.getElementById('dnOverviewQuality');
        if (qualityElem && response.quality_metrics) {
            qualityElem.textContent = `${response.quality_metrics.score} / 100 (Grade ${response.quality_metrics.grade || 'A+'})`;
        }

        const exportBtn = document.getElementById('dnExportReportBtn');
        if (exportBtn) exportBtn.style.display = 'inline-flex';

        const downloadDropdown = document.getElementById('dnDownloadCleanedDropdown');
        if (downloadDropdown) downloadDropdown.style.display = 'inline-block';

        const rollbackBtn = document.getElementById('dnRollbackDatasetBtn');
        if (rollbackBtn) rollbackBtn.style.display = 'inline-flex';

        if (response.assigned_task && response.assigned_task.status !== 'Completed') {
            currentActiveTask = response.assigned_task;
        }

        if (overviewPanel) overviewPanel.style.display = 'block';

        // Refresh dynamic AI insights & dashboard analytics for newly populated dataset
        fetchAnalystAnalytics();

        fullColumnInfo = response.column_info || [];
        if (columnInfoContent) columnInfoContent.innerHTML = '';
        if (fullColumnInfo.length > 0 && columnInfoPanel && columnInfoContent) {
            fullColumnInfo.slice(0, 4).forEach(function (col) {
                var row = document.createElement('tr');
                var tagHtml = col.is_recommended_drop ? ' <span class="badge bg-danger-subtle text-danger ms-1">(Not Required)</span>' : '';
                row.innerHTML = `
                    <td>${col.name}${tagHtml}</td>
                    <td><span class="dn-badge-status neutral">${col.type}</span></td>
                `;
                columnInfoContent.appendChild(row);
            });

            if (viewAllColsBtn && columnInfoFooter) {
                viewAllColsBtn.setAttribute('data-state', 'more');
                if (fullColumnInfo.length > 4) {
                    viewAllColsBtn.textContent = `View All ${fullColumnInfo.length} Columns`;
                    columnInfoFooter.style.display = 'block';
                } else {
                    viewAllColsBtn.textContent = 'View All Columns';
                    columnInfoFooter.style.display = 'none';
                }
            }

            if (duplicateColumnSelect) {
                duplicateColumnSelect.innerHTML = '';
                fullColumnInfo.forEach(function (col) {
                    const badgeHtml = `
                        <label class="dn-dup-col-pill d-inline-flex align-items-center gap-1 px-2 py-1 border rounded bg-white small" style="cursor: pointer; user-select: none; font-size: 0.8rem;">
                            <input class="form-check-input mt-0 dn-dup-check" type="checkbox" value="${col.name}" id="dup-check-${col.name}">
                            <span class="dn-dup-col-name text-truncate" style="max-width: 170px;" title="${col.name}">${col.name}</span>
                        </label>`;
                    duplicateColumnSelect.insertAdjacentHTML('beforeend', badgeHtml);
                });

                const countBadge = document.getElementById('dnDupSelectedColsCount');
                if (countBadge) countBadge.textContent = `0 columns selected`;
                duplicateColumnSelect.querySelectorAll('.dn-dup-check').forEach(chk => {
                    chk.addEventListener('change', () => {
                        const checkedCount = duplicateColumnSelect.querySelectorAll('.dn-dup-check:checked').length;
                        if (countBadge) countBadge.textContent = `${checkedCount} column(s) selected`;
                    });
                });
            }

            columnInfoPanel.style.display = 'block';
        } else if (columnInfoPanel) {
            columnInfoPanel.style.display = 'none';
        }

        // Render Pattern & Trend Detection
        const patternPanel = document.getElementById('dnPatternDetectionPanel');
        const patternList = document.getElementById('dnPatternDetectionList');
        if (patternPanel && patternList) {
            patternList.innerHTML = '';
            let insightsFound = false;

            const insightColors = {
                trend: 'var(--dn-green)',
                correlation: 'var(--dn-violet)',
                outlier: 'var(--dn-amber)',
                seasonality: 'var(--dn-cyan)'
            };

            // Example: Check for time-series trend
            if (response.timeseries_analysis && response.timeseries_analysis.trend_direction) {
                const trend = response.timeseries_analysis.trend_direction;
                patternList.insertAdjacentHTML('beforeend', `<li><span class="dn-insight-dot" style="background:${insightColors.trend}"></span>A significant <strong>${trend} trend</strong> was detected in the primary time-series.</li>`);
                insightsFound = true;
            }

            // Example: Check for top correlation
            if (response.correlation_matrix && response.correlation_matrix.top_pairs && response.correlation_matrix.top_pairs.length > 0) {
                const topPair = response.correlation_matrix.top_pairs[0];
                patternList.insertAdjacentHTML('beforeend', `<li><span class="dn-insight-dot" style="background:${insightColors.correlation}"></span>A <strong>${topPair.relationship} correlation</strong> (r=${topPair.correlation.toFixed(2)}) was found between <strong>${topPair.col1}</strong> and <strong>${topPair.col2}</strong>.</li>`);
                insightsFound = true;
            }

            // Example: Check for outliers
            if (response.outliers && response.outliers.total_outlier_count > 0) {
                patternList.insertAdjacentHTML('beforeend', `<li><span class="dn-insight-dot" style="background:${insightColors.outlier}"></span>Detected <strong>${response.outliers.total_outlier_count.toLocaleString()}</strong> potential outliers in numeric columns.</li>`);
                insightsFound = true;
            }

            if (insightsFound) {
                patternPanel.style.display = 'block';
            }
        }

        // Render Drop Unwanted Columns Grid
        const dropColumnsPanel = document.getElementById('dnDropColumnsPanel');
        const dropColumnsGrid = document.getElementById('dnDropColumnsGrid');
        const confirmDropBtn = document.getElementById('dnConfirmDropColumnsBtn');
        const selectedColsCountSpan = document.getElementById('dnSelectedColumnsCount');

        if (dropColumnsPanel && dropColumnsGrid && fullColumnInfo.length > 0) {
            dropColumnsGrid.innerHTML = '';
            const colUsefulness = response.column_usefulness || [];
            const usefulnessMap = {};
            colUsefulness.forEach(item => { usefulnessMap[item.column] = item; });

            let preSelectedCount = 0;
            fullColumnInfo.forEach(col => {
                const uInfo = usefulnessMap[col.name] || {};
                const isRecDrop = col.is_recommended_drop || uInfo.is_recommended_drop || false;
                const tagText = col.is_recommended_drop ? '(Not Required)' : (uInfo.tag || '');
                const tagBadge = tagText ? `<span class="badge bg-danger-subtle text-danger border border-danger-subtle ms-1">${tagText}</span>` : '';
                const reasonText = col.drop_reason || uInfo.reason || '';

                if (isRecDrop) preSelectedCount++;

                const cardHtml = `
                    <div class="col-md-4 col-sm-6">
                        <div class="p-2 border rounded bg-body-tertiary">
                            <div class="form-check">
                                <input class="form-check-input dn-col-drop-check" type="checkbox" value="${col.name}" id="drop-col-${col.name}" ${isRecDrop ? 'checked' : ''}>
                                <label class="form-check-label fw-medium" for="drop-col-${col.name}">
                                    ${col.name}${tagBadge}
                                </label>
                            </div>
                            ${reasonText ? `<div class="text-muted extra-small ms-4 mt-1" style="font-size:0.75rem;">${reasonText}</div>` : ''}
                        </div>
                    </div>
                `;
                dropColumnsGrid.insertAdjacentHTML('beforeend', cardHtml);
            });

            if (selectedColsCountSpan) {
                selectedColsCountSpan.textContent = `${preSelectedCount} column(s) selected for removal`;
            }
            if (confirmDropBtn) {
                confirmDropBtn.disabled = preSelectedCount === 0;
            }

            dropColumnsGrid.querySelectorAll('.dn-col-drop-check').forEach(chk => {
                chk.addEventListener('change', () => {
                    const checkedCount = dropColumnsGrid.querySelectorAll('.dn-col-drop-check:checked').length;
                    if (selectedColsCountSpan) selectedColsCountSpan.textContent = `${checkedCount} column(s) selected for removal`;
                    if (confirmDropBtn) confirmDropBtn.disabled = checkedCount === 0;
                });
            });

            dropColumnsPanel.style.display = 'block';
        }

        // Render Custom Chart Builder Options
        const customChartPanel = document.getElementById('dnCustomChartPanel');
        const customXSelect = document.getElementById('dnCustomXSelect');
        const customYSelect = document.getElementById('dnCustomYSelect');

        if (customChartPanel && customXSelect && customYSelect && fullColumnInfo.length > 0) {
            customXSelect.innerHTML = '<option value="">-- Select X Column --</option>';
            customYSelect.innerHTML = '<option value="">-- None (Single Variable) --</option>';

            fullColumnInfo.forEach(col => {
                customXSelect.insertAdjacentHTML('beforeend', `<option value="${col.name}">${col.name}</option>`);
                customYSelect.insertAdjacentHTML('beforeend', `<option value="${col.name}">${col.name}</option>`);
            });

            customChartPanel.style.display = 'block';
        }

        missingColumnInfo = response.missing_info || [];
        if (missingValueContent) missingValueContent.innerHTML = '';
        if (response.total_missing_count > 0 && missingColumnInfo.length > 0 && missingValuePanel) {
            const totalCells = response.row_count * response.column_count;
            const totalMissingPercent = totalCells > 0 ? (response.total_missing_count / totalCells * 100).toFixed(2) : '0.00';
            if (missingValueSummary) {
                missingValueSummary.innerHTML = `<i class="bi bi-info-circle-fill"></i> Found <strong>${response.total_missing_count.toLocaleString()}</strong> missing values across <strong>${missingColumnInfo.length}</strong> columns (${totalMissingPercent}% of total data).`;
            }

            missingColumnInfo.forEach(function (col) {
                var row = document.createElement('tr');
                var recBadge = `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">
                    <i class="bi bi-magic me-1"></i> Replace with ${col.recommended_method || 'Smart Impute'}: <strong>${col.recommended_value || 'N/A'}</strong>
                </span>`;
                var explanationText = col.explanation ? `<div class="text-muted extra-small mt-1" style="font-size:0.75rem;">${col.explanation}</div>` : '';

                row.innerHTML = `
                    <td class="fw-medium">${col.name}</td>
                    <td class="text-end fw-semibold text-danger">${col.count.toLocaleString()}</td>
                    <td class="text-end fw-semibold text-warning">${col.percentage}%</td>
                    <td>${recBadge}${explanationText}</td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-outline-primary dn-apply-rec-btn py-0 px-2" data-col="${col.name}">
                            <i class="bi bi-lightning-charge-fill me-1"></i> Auto Impute
                        </button>
                    </td>
                `;
                missingValueContent.appendChild(row);
            });

            // Bind click handler for quick auto impute buttons
            missingValueContent.querySelectorAll('.dn-apply-rec-btn').forEach(btn => {
                btn.addEventListener('click', function () {
                    const colName = this.getAttribute('data-col');
                    if (missingColumnSelect) missingColumnSelect.value = colName;
                    if (missingStrategySelect) missingStrategySelect.value = 'smart_clean';
                    if (applyCleaningBtn) applyCleaningBtn.click();
                });
            });

            if (missingColumnSelect) {
                missingColumnSelect.innerHTML = '<option value="all_columns">All Columns</option>';
                missingColumnInfo.forEach(function (col) {
                    var option = document.createElement('option');
                    option.value = col.name;
                    option.textContent = col.name;
                    missingColumnSelect.appendChild(option);
                });
                if (typeof updateCleaningStrategies === 'function') {
                    updateCleaningStrategies();
                }
            }
            missingValuePanel.style.display = 'block';
            if (missingValueActions) missingValueActions.style.display = 'block';
            const nextStepBanner = document.getElementById('dnMissingValueNextStepBanner');
            if (nextStepBanner) nextStepBanner.style.display = 'none';
        } else {
            if (missingValuePanel) {
                missingValuePanel.style.display = 'block';
                if (missingValueSummary) {
                    missingValueSummary.className = 'dn-alert dn-alert-success bg-success-subtle text-success border border-success-subtle p-3 rounded';
                    missingValueSummary.innerHTML = '<i class="bi bi-check-circle-fill me-2 fs-5"></i> <strong>Zero Missing Values Remaining!</strong> All null values have been successfully imputed and cleaned.';
                }
                if (missingValueContent) missingValueContent.innerHTML = '<tr><td colspan="5" class="text-center text-success py-3"><i class="bi bi-check-circle-fill me-1"></i> No missing values detected in dataset.</td></tr>';
            }
            if (missingValueActions) missingValueActions.style.display = 'none';
            const nextStepBanner = document.getElementById('dnMissingValueNextStepBanner');
            if (nextStepBanner) nextStepBanner.style.display = 'block';
        }

        if (duplicatePreviewContent) {
            duplicatePreviewContent.style.display = 'none';
            duplicatePreviewContent.innerHTML = '';
        }
        if (subDuplicatesContainer) subDuplicatesContainer.style.display = 'none';
        if (subDuplicateResult) subDuplicateResult.style.display = 'none';
        if (removeFullDuplicatesBtn) removeFullDuplicatesBtn.style.display = 'inline-flex';

        if (response.duplicate_count > 0 && duplicatePanel) {
            if (duplicateSummary) {
                duplicateSummary.className = 'dn-alert dn-alert-info';
                duplicateSummary.innerHTML = `<i class="bi bi-info-circle-fill"></i> Found <strong>${response.duplicate_count.toLocaleString()}</strong> duplicate rows (${response.duplicate_percentage}% of the dataset).`;
            }
            duplicatePanel.style.display = 'block';

            if (response.duplicates_preview_html && duplicatePreviewContent) {
                duplicatePreviewContent.innerHTML = '<h4 class="dn-panel-title-sm mt-3 mb-2"><i class="bi bi-eye"></i> Preview of Duplicate Rows</h4>' + response.duplicates_preview_html;
                duplicatePreviewContent.style.display = 'block';
            }
            if (subDuplicatesContainer) subDuplicatesContainer.style.display = 'block';
        } else if (duplicatePanel) {
            duplicatePanel.style.display = 'none';
        }

        if (response.stats_summary_html && statsPanel && statsContent) {
            statsContent.innerHTML = response.stats_summary_html;
            statsPanel.style.display = 'block';
            addTooltipsToStatsTable();
        } else if (statsPanel) {
            statsPanel.style.display = 'none';
        }

        // Show the AI suggestions panel, but keep its content hidden until the button is clicked.
        if (aiSuggestionsPanel) {
            aiSuggestionsPanel.style.display = 'block';
        }

        if (autoEDAPanel) {
            autoEDAPanel.style.display = 'block';
        }

        if (correlationPanel) {
            correlationPanel.style.display = 'block';
            if (correlationResultContainer) correlationResultContainer.style.display = 'none';
        }

        if (activeDatasetId) {
            loadEdaResults(activeDatasetId);
        }

        if (shouldScroll && previewPanel) {
            previewPanel.scrollIntoView({ behavior: 'smooth' });
        }
    }

    function loadCurrentDataset(onComplete) {
        fetch('/api/current_dataset')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.has_dataset !== false && data.preview_html) {
                    populateDatasetWorkspace(data, data.file_name, false);

                    // Restore active section / scroll position if remembered or in URL hash
                    const savedHash = window.location.hash || sessionStorage.getItem('datanova_analyst_active_step');
                    if (savedHash && savedHash !== '#upload' && savedHash !== '#main-overview') {
                        const targetElem = document.querySelector(savedHash);
                        if (targetElem) {
                            setTimeout(() => {
                                smoothScrollToTarget(targetElem);
                            }, 350);
                        }
                    }
                }
                if (typeof onComplete === 'function') onComplete(data);
            })
            .catch(error => {
                console.warn('Could not restore current dataset on load:', error);
            });
    }

    if (uploadForm && fileInput) {
        // Function to handle file upload
        function uploadFile(file) {
            if (!file) return;

            // Show progress bar
            uploadForm.style.display = 'none'; // Hide dropzone
            uploadFilename.textContent = file.name;
            uploadPercentage.textContent = '0%';
            progressBar.style.width = '0%';
            uploadProgress.style.display = 'block';

            var formData = new FormData();
            formData.append('file', file);

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload_dataset', true);

            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    var percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                    uploadPercentage.textContent = Math.round(percentComplete) + '%';
                    if (percentComplete >= 100) {
                        // Once upload is complete, hide progress bar and show processing loader
                        uploadProgress.style.display = 'none';
                        if (processingLoader) processingLoader.style.display = 'flex';
                    }
                }
            };

            xhr.onload = function () {
                // Always hide the main processing loader when the request is complete.
                if (processingLoader) processingLoader.style.display = 'none';

                if (xhr.status === 200) {
                    var response;
                    try {
                        response = JSON.parse(xhr.responseText);
                    } catch (parseErr) {
                        showFetchError('uploadFile (JSON parse)', parseErr);
                        alert('The server returned an unexpected response while processing your file. Please try again.');
                        resetDropzoneAfterFailure();
                        return;
                    }

                    if (response.success && response.preview_html) {
                        populateDatasetWorkspace(response, file.name, true);
                        addTooltipsToStatsTable(); // Add tooltips after populating the workspace
                    } else {
                        console.warn('[DataNova] Upload response missing expected data:', response);
                        alert(response.message || 'The file was uploaded but the server did not return any preview data. Please check the file and try again.');
                        resetDropzoneAfterFailure();
                    }
                } else {
                    // Error
                    console.error('Upload failed:', xhr.status, xhr.responseText);
                    progressBar.classList.add('bg-danger');
                    uploadPercentage.textContent = 'Failed';
                    alert('Upload failed. Please check your connection and try again.');
                    resetDropzoneAfterFailure();
                }
            };

            xhr.onerror = function () {
                if (processingLoader) processingLoader.style.display = 'none';
                console.error('Upload failed: network error');
                alert('Upload failed due to a network error. Please try again.');
                resetDropzoneAfterFailure();
            };

            xhr.send(formData);
        }

        // FIX: helper to restore the dropzone after any failed upload
        function resetDropzoneAfterFailure() {
            uploadProgress.style.display = 'none';
            progressBar.classList.remove('bg-danger', 'bg-success');
            progressBar.style.width = '0%';
            uploadPercentage.textContent = '0%';
            uploadForm.style.display = 'flex';
            fileInput.value = '';
        }

        // --- Dropzone Click & Drag-and-Drop Event Listeners ---
        uploadForm.addEventListener('click', function (e) {
            const uploadPill = e.target.closest('[data-action="upload-file"]');
            if (uploadPill) {
                e.stopPropagation();
                fileInput.click();
                return;
            }
            if (e.target.closest('[data-bs-toggle]') || e.target.closest('.dn-source-pill')) {
                return;
            }
            fileInput.click();
        });

        fileInput.addEventListener('change', function () {
            if (fileInput.files && fileInput.files.length > 0) {
                uploadFile(fileInput.files[0]);
            }
        });

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function (evt) {
            window.addEventListener(evt, function (e) {
                e.preventDefault();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(function (evt) {
            uploadForm.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                uploadForm.classList.add('is-dragover');
            }, false);
        });

        ['dragleave', 'dragend'].forEach(function (evt) {
            uploadForm.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (evt === 'dragend' || !uploadForm.contains(e.relatedTarget)) {
                    uploadForm.classList.remove('is-dragover');
                }
            }, false);
        });

        uploadForm.addEventListener('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            uploadForm.classList.remove('is-dragover');

            var droppedFiles = e.dataTransfer ? e.dataTransfer.files : null;
            if (droppedFiles && droppedFiles.length > 0) {
                uploadFile(droppedFiles[0]);
            }
        }, false);

        // Handle "Upload Another" button click
        if (uploadAnotherBtn) {
            uploadAnotherBtn.addEventListener('click', function () {
                // 1. Raw Preview & Schema Panels
                if (previewPanel) previewPanel.style.display = 'none';
                if (previewContent) previewContent.innerHTML = '';
                if (previewFilename) previewFilename.textContent = '';
                if (overviewPanel) overviewPanel.style.display = 'none';
                if (columnInfoPanel) columnInfoPanel.style.display = 'none';
                if (columnInfoFooter) columnInfoFooter.style.display = 'none';
                if (columnInfoContent) columnInfoContent.innerHTML = '';

                // 2. Data Cleaning Pipeline Panels
                if (missingValuePanel) missingValuePanel.style.display = 'none';
                if (missingValueActions) missingValueActions.style.display = 'none';
                if (missingValueContent) missingValueContent.innerHTML = '';
                const missingNextBanner = document.getElementById('dnMissingValueNextStepBanner');
                if (missingNextBanner) missingNextBanner.style.display = 'none';

                if (duplicatePanel) duplicatePanel.style.display = 'none';
                if (subDuplicatesContainer) subDuplicatesContainer.style.display = 'none';
                if (subDuplicateResult) {
                    subDuplicateResult.style.display = 'none';
                    subDuplicateResult.innerHTML = '';
                }
                if (duplicatePreviewContent) {
                    duplicatePreviewContent.style.display = 'none';
                    duplicatePreviewContent.innerHTML = '';
                }
                if (duplicateColumnSelect) duplicateColumnSelect.innerHTML = '';

                const dropColumnsPanel = document.getElementById('dnDropColumnsPanel');
                if (dropColumnsPanel) dropColumnsPanel.style.display = 'none';
                const dropColumnsGrid = document.getElementById('dnDropColumnsGrid');
                if (dropColumnsGrid) dropColumnsGrid.innerHTML = '';

                if (cleanedPreviewPanel) {
                    cleanedPreviewPanel.style.display = 'none';
                    if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = '';
                    const downloadBtn = cleanedPreviewPanel.querySelector('#dnDownloadCleanedBtn');
                    if (downloadBtn) downloadBtn.remove();
                }

                // 3. Statistical EDA & AI Suggestions Panels
                if (statsPanel) statsPanel.style.display = 'none';
                if (statsContent) statsContent.innerHTML = '';

                if (aiSuggestionsPanel) {
                    aiSuggestionsPanel.style.display = 'none';
                    if (aiSuggestionsResult) aiSuggestionsResult.style.display = 'none';
                    if (aiUnwantedColumnsList) aiUnwantedColumnsList.innerHTML = '';
                    const aiNewFeaturesList = document.getElementById('aiNewFeaturesList');
                    if (aiNewFeaturesList) aiNewFeaturesList.innerHTML = '';
                    if (applyAIRemovalBtn) applyAIRemovalBtn.style.display = 'none';
                    if (aiLoadingSpinner) aiLoadingSpinner.style.display = 'none';
                }

                if (autoEDAPanel) {
                    autoEDAPanel.style.display = 'none';
                    if (window.Plotly && edaResultContainer) {
                        edaResultContainer.querySelectorAll('.dn-eda-plot > div[id^="dnPlotlyChart_"]').forEach(node => {
                            try { Plotly.purge(node); } catch (e) { /* ignore */ }
                        });
                    }
                    if (edaResultContainer) edaResultContainer.innerHTML = '';
                    if (edaLoadingSpinner) edaLoadingSpinner.style.display = 'none';
                }

                // 4. Correlation Analysis & Scatter Plot Panels
                if (correlationPanel) correlationPanel.style.display = 'none';
                if (correlationResultContainer) correlationResultContainer.style.display = 'none';
                if (correlationLoadingSpinner) correlationLoadingSpinner.style.display = 'none';
                if (correlationAlertMsg) correlationAlertMsg.style.display = 'none';
                const topCorrelationsContainer = document.getElementById('dnTopCorrelationsContainer');
                if (topCorrelationsContainer) topCorrelationsContainer.style.display = 'none';
                const topPos = document.getElementById('dnTopPositiveCorrelations');
                if (topPos) topPos.innerHTML = '';
                const topNeg = document.getElementById('dnTopNegativeCorrelations');
                if (topNeg) topNeg.innerHTML = '';
                const heatmapImg = document.getElementById('dnCorrelationHeatmap');
                if (heatmapImg) heatmapImg.src = '';

                if (scatterPlotResult) scatterPlotResult.style.display = 'none';
                const scatterPlotImg = document.getElementById('dnScatterPlotImg');
                if (scatterPlotImg) scatterPlotImg.src = '';
                if (scatterXSelect) scatterXSelect.innerHTML = '';
                if (scatterYSelect) scatterYSelect.innerHTML = '';

                // 5. Custom Visualizations Panel
                const customChartPanel = document.getElementById('dnCustomChartPanel');
                if (customChartPanel) customChartPanel.style.display = 'none';
                const customChartResult = document.getElementById('dnCustomChartResult');
                if (customChartResult) customChartResult.style.display = 'none';
                const customChartImg = document.getElementById('dnCustomChartImg');
                if (customChartImg) customChartImg.src = '';
                const customX = document.getElementById('dnCustomXSelect');
                if (customX) customX.innerHTML = '<option value="">-- Select X Column --</option>';
                const customY = document.getElementById('dnCustomYSelect');
                if (customY) customY.innerHTML = '<option value="">-- None (Single Variable) --</option>';

                // 6. Pattern & Trend Detection Panel
                const patternPanel = document.getElementById('dnPatternDetectionPanel');
                if (patternPanel) patternPanel.style.display = 'none';
                const patternList = document.getElementById('dnPatternDetectionList');
                if (patternList) patternList.innerHTML = '';

                // 7. Automated AI Profiling List
                const insightsList = document.getElementById('analystAiInsightsList');
                if (insightsList) {
                    insightsList.innerHTML = '<li><span class="dn-insight-dot" style="background:var(--dn-cyan)"></span>Upload a dataset to generate automated AI data profiling.</li>';
                }

                // 8. Live ML & Predictive Analytics Panel
                const step7Active = document.getElementById('step7PredictionsActiveContent');
                if (step7Active) step7Active.classList.add('d-none');
                const step7Empty = document.getElementById('step7PredictionsEmptyState');
                if (step7Empty) step7Empty.classList.remove('d-none');
                const step7Target = document.getElementById('step7TargetName');
                if (step7Target) step7Target.textContent = '--';
                const step7Formula = document.getElementById('step7FormulaText');
                if (step7Formula) step7Formula.textContent = '--';
                const step7Intercept = document.getElementById('step7InterceptText');
                if (step7Intercept) step7Intercept.textContent = 'Intercept (\u03b20): --';
                const step7R2 = document.getElementById('step7R2Value');
                if (step7R2) step7R2.textContent = '--';
                const step7Mae = document.getElementById('step7MaeValue');
                if (step7Mae) step7Mae.textContent = '--';
                const step7PredTbody = document.getElementById('step7PredTbody');
                if (step7PredTbody) step7PredTbody.innerHTML = '';
                const step7InstantInputsRow = document.getElementById('step7InstantInputsRow');
                if (step7InstantInputsRow) step7InstantInputsRow.innerHTML = '';
                const step7InstantPredictionResult = document.getElementById('step7InstantPredictionResult');
                if (step7InstantPredictionResult) {
                    step7InstantPredictionResult.classList.add('d-none');
                    step7InstantPredictionResult.innerHTML = '';
                }

                // 9. Top Header Action Buttons
                const exportBtn = document.getElementById('dnExportReportBtn');
                if (exportBtn) exportBtn.style.display = 'none';
                const downloadDropdown = document.getElementById('dnDownloadCleanedDropdown');
                if (downloadDropdown) downloadDropdown.style.display = 'none';
                const rollbackBtn = document.getElementById('dnRollbackDatasetBtn');
                if (rollbackBtn) rollbackBtn.style.display = 'none';

                // 10. Deactivate dataset-dependent sidebar links
                document.querySelectorAll('.dn-requires-dataset').forEach(link => {
                    link.classList.add('dn-nav-disabled');
                });

                // 11. State & Input Controls Reset
                if (missingCustomValueContainer) missingCustomValueContainer.style.display = 'none';
                if (missingCustomValueInput) missingCustomValueInput.value = '';

                activeDatasetId = null; // Clear active dataset ID
                if (uploadAnotherBtn) {
                    uploadAnotherBtn.style.display = 'none';
                }
                currentActiveTask = null; // Clear active task metadata
                missingColumnInfo = [];
                fullColumnInfo = [];

                if (viewAllColsBtn) {
                    viewAllColsBtn.textContent = 'View All Columns';
                    viewAllColsBtn.setAttribute('data-state', 'more');
                }

                // Show upload form & reset dropzone inputs
                if (uploadForm) uploadForm.style.display = 'flex';
                if (uploadProgress) uploadProgress.style.display = 'none';
                if (progressBar) progressBar.classList.remove('bg-success', 'bg-danger');
                if (fileInput) fileInput.value = '';

                // Scroll smoothly back up to Upload section
                const uploadSection = document.getElementById('upload');
                if (uploadSection) {
                    uploadSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }

                showToast('Dashboard reset. Ready to upload another dataset.', 'info');
            });
        }

        /* ---------------------------------------------------------------------
           Google Sheets Import Event Listener
           ------------------------------------------------------------------- */
        var gsheetForm = document.getElementById('dnGSheetForm');
        var gsheetUrlInput = document.getElementById('dnGSheetUrlInput');
        var gsheetBtn = document.getElementById('dnImportGSheetBtn');
        var gsheetStatus = document.getElementById('dnGSheetStatus');
        var gsheetMsg = document.getElementById('dnGSheetMsg');

        if (gsheetForm) {
            gsheetForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var url = gsheetUrlInput ? gsheetUrlInput.value.trim() : '';
                if (!url) {
                    if (gsheetUrlInput) gsheetUrlInput.classList.add('is-invalid');
                    return;
                }
                if (gsheetUrlInput) gsheetUrlInput.classList.remove('is-invalid');

                if (gsheetBtn) gsheetBtn.disabled = true;
                if (gsheetStatus) gsheetStatus.classList.remove('d-none');
                if (gsheetMsg) gsheetMsg.textContent = 'Connecting to Google Sheets and downloading dataset...';

                if (processingLoader) processingLoader.style.display = 'flex';

                fetch('/api/import_google_sheet', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({ sheet_url: url })
                })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (processingLoader) processingLoader.style.display = 'none';
                    if (gsheetBtn) gsheetBtn.disabled = false;
                    if (gsheetStatus) gsheetStatus.classList.add('d-none');

                    if (data.success && data.preview_html) {
                        // Close modal
                        var modalEl = document.getElementById('dnGoogleSheetModal');
                        if (modalEl && window.bootstrap && bootstrap.Modal) {
                            var modalInstance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                            modalInstance.hide();
                        }

                        populateDatasetWorkspace(data, data.file_name || 'Google Sheet Dataset', true);
                        addTooltipsToStatsTable();
                    } else {
                        var errText = (data.message || data.error || 'Failed to import Google Sheet dataset.').replace(/\n/g, '<br>');
                        if (gsheetStatus) {
                            gsheetStatus.className = 'mt-3 p-3 rounded bg-danger-subtle text-danger border border-danger-subtle';
                            gsheetStatus.innerHTML = '<div class="d-flex align-items-start gap-2"><i class="bi bi-exclamation-triangle-fill fs-5 mt-0.5 text-danger flex-shrink-0"></i><div class="small fw-medium">' + errText + '</div></div>';
                        } else {
                            alert(data.message || 'Failed to import Google Sheet dataset.');
                        }
                    }
                })
                .catch(function (err) {
                    if (processingLoader) processingLoader.style.display = 'none';
                    if (gsheetBtn) gsheetBtn.disabled = false;
                    console.error('[DataNova] Google Sheet import error:', err);
                    if (gsheetStatus) {
                        gsheetStatus.className = 'mt-3 p-3 rounded bg-danger-subtle text-danger border border-danger-subtle';
                        gsheetStatus.innerHTML = '<div class="d-flex align-items-center gap-2"><i class="bi bi-wifi-off fs-5 text-danger"></i><span class="small fw-semibold">Network error while fetching Google Sheet. Please check your connection and try again.</span></div>';
                    }
                });
            });
        }

        /* ---------------------------------------------------------------------
           MySQL Database Analysis Event Listeners & Functions
           ------------------------------------------------------------------- */
        var testMysqlBtn = document.getElementById('btnAnalystTestMysql');
        var mysqlForm = document.getElementById('dnMysqlForm');

        if (testMysqlBtn) {
            testMysqlBtn.addEventListener('click', function (e) {
                if (e && e.preventDefault) e.preventDefault();
                console.log('[DataNova] "Test & Fetch Tables" clicked');

                var statusEl = document.getElementById('analystMysqlStatus');
                var tableSelect = document.getElementById('analystMysqlTableSelect');

                var hostInput = document.getElementById('analystMysqlHost');
                var portInput = document.getElementById('analystMysqlPort');
                var userInput = document.getElementById('analystMysqlUser');
                var passInput = document.getElementById('analystMysqlPassword');
                var dbInput = document.getElementById('analystMysqlDatabase');

                var host = hostInput ? hostInput.value.trim() : '';
                var port = portInput ? portInput.value.trim() : '3306';
                var user = userInput ? userInput.value.trim() : 'root';
                var password = passInput ? passInput.value : '';
                var database = dbInput ? dbInput.value.trim() : '';

                if (!host || !database) {
                    if (statusEl) {
                        statusEl.className = 'alert alert-danger shadow-sm mb-3';
                        statusEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i>Please enter MySQL Host and Database Name.';
                        statusEl.classList.remove('d-none');
                    }
                    return;
                }

                testMysqlBtn.disabled = true;
                testMysqlBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Connecting...';

                if (statusEl) {
                    statusEl.className = 'alert alert-info shadow-sm mb-3';
                    statusEl.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Connecting to MySQL server and fetching table metadata...';
                    statusEl.classList.remove('d-none');
                }

                fetch('/api/mysql/test_connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ host: host, port: port, user: user, password: password, database: database })
                })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    testMysqlBtn.disabled = false;
                    testMysqlBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i> Test &amp; Fetch Tables';

                    if (data.success) {
                        if (statusEl) {
                            statusEl.className = 'alert alert-success shadow-sm mb-3';
                            statusEl.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>' + data.message;
                            statusEl.classList.remove('d-none');
                        }

                        if (tableSelect) {
                            tableSelect.innerHTML = '<option value="">-- Select a MySQL Table --</option>';
                            if (data.tables && data.tables.length > 0) {
                                data.tables.forEach(function(t) {
                                    var opt = document.createElement('option');
                                    opt.value = t.name;
                                    var rowStr = (t.estimated_rows !== undefined && t.estimated_rows !== 'N/A') ? ' (~' + t.estimated_rows + ' rows)' : '';
                                    opt.textContent = t.name + rowStr;
                                    tableSelect.appendChild(opt);
                                });
                            } else {
                                var opt = document.createElement('option');
                                opt.value = '';
                                opt.textContent = 'No tables found in database';
                                tableSelect.appendChild(opt);
                            }
                        }
                    } else {
                        if (statusEl) {
                            statusEl.className = 'alert alert-danger shadow-sm mb-3';
                            statusEl.innerHTML = '<i class="bi bi-x-circle-fill me-2"></i>' + (data.message || 'MySQL connection failed.');
                            statusEl.classList.remove('d-none');
                        }
                    }
                })
                .catch(function(err) {
                    testMysqlBtn.disabled = false;
                    testMysqlBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i> Test &amp; Fetch Tables';
                    if (statusEl) {
                        statusEl.className = 'alert alert-danger shadow-sm mb-3';
                        statusEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i>Network Error: ' + err.message;
                        statusEl.classList.remove('d-none');
                    }
                });
            });
        }

        if (mysqlForm) {
            mysqlForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var statusEl = document.getElementById('analystMysqlStatus');
                var runBtn = document.getElementById('btnAnalystRunMysql');
                var spinner = document.getElementById('analystMysqlSpinner');

                var host = document.getElementById('analystMysqlHost').value.trim();
                var port = document.getElementById('analystMysqlPort').value.trim();
                var user = document.getElementById('analystMysqlUser').value.trim();
                var password = document.getElementById('analystMysqlPassword').value;
                var database = document.getElementById('analystMysqlDatabase').value.trim();
                var tableSelect = document.getElementById('analystMysqlTableSelect').value;
                var queryInput = document.getElementById('analystMysqlQuery').value.trim();
                var limit = document.getElementById('analystMysqlLimit').value;

                if (!host || !database) {
                    if (statusEl) {
                        statusEl.className = 'alert alert-danger shadow-sm mb-3';
                        statusEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i>MySQL Host and Database Name are required.';
                        statusEl.classList.remove('d-none');
                    }
                    return;
                }

                if (!tableSelect && !queryInput) {
                    if (statusEl) {
                        statusEl.className = 'alert alert-danger shadow-sm mb-3';
                        statusEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i>Please select a table or type a custom SQL query.';
                        statusEl.classList.remove('d-none');
                    }
                    return;
                }

                if (runBtn) runBtn.disabled = true;
                if (spinner) spinner.classList.remove('d-none');

                if (statusEl) {
                    statusEl.className = 'alert alert-info shadow-sm mb-3';
                    statusEl.innerHTML = '<i class="bi bi-gear-wide-connected spin me-2"></i> Extracting MySQL data & executing automated EDA pipeline... Please wait.';
                    statusEl.classList.remove('d-none');
                }

                if (processingLoader) processingLoader.style.display = 'flex';

                fetch('/api/mysql/import_and_analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({
                        host: host,
                        port: port,
                        user: user,
                        password: password,
                        database: database,
                        table_name: tableSelect,
                        query: queryInput,
                        limit: limit
                    })
                })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (processingLoader) processingLoader.style.display = 'none';
                    if (runBtn) runBtn.disabled = false;
                    if (spinner) spinner.classList.add('d-none');

                    if (data.success && data.preview_html) {
                        // Close MySQL modal
                        var modalEl = document.getElementById('dnMysqlModal');
                        if (modalEl && window.bootstrap && bootstrap.Modal) {
                            var modalInstance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                            modalInstance.hide();
                        }

                        var displayName = 'mysql:' + database + '.' + (tableSelect || 'query');
                        populateDatasetWorkspace(data, data.file_name || displayName, true);
                        addTooltipsToStatsTable();
                    } else {
                        var errText = (data.message || data.error || 'Failed to analyze MySQL dataset.').replace(/\n/g, '<br>');
                        if (statusEl) {
                            statusEl.className = 'alert alert-danger shadow-sm mb-3';
                            statusEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i>' + errText;
                        } else {
                            alert(data.message || 'Failed to analyze MySQL dataset.');
                        }
                    }
                })
                .catch(function (err) {
                    if (processingLoader) processingLoader.style.display = 'none';
                    if (runBtn) runBtn.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    console.error('[DataNova] MySQL Analysis error:', err);
                    if (statusEl) {
                        statusEl.className = 'alert alert-danger shadow-sm mb-3';
                        statusEl.innerHTML = '<i class="bi bi-wifi-off me-2"></i>Network Error: ' + err.message;
                    } else {
                        alert('Network error while analyzing MySQL dataset.');
                    }
                });
            });
        }


        // Handle "View All Columns" button click
        if (viewAllColsBtn) {
            viewAllColsBtn.addEventListener('click', function () {
                const currentState = viewAllColsBtn.getAttribute('data-state');
                columnInfoContent.innerHTML = ''; // Clear the table body

                if (currentState === 'more') {
                    // --- Show all columns ---
                    fullColumnInfo.forEach(function (col) {
                        var row = document.createElement('tr');
                        row.innerHTML = `<td>${col.name}</td><td><span class="dn-badge-status neutral">${col.type}</span></td>`;
                        columnInfoContent.appendChild(row);
                    });
                    viewAllColsBtn.textContent = 'View Less';
                    viewAllColsBtn.setAttribute('data-state', 'less');
                } else {
                    // --- Show only the first 4 columns ---
                    const initialColumns = fullColumnInfo.slice(0, 4);
                    initialColumns.forEach(function (col) {
                        var row = document.createElement('tr');
                        row.innerHTML = `<td>${col.name}</td><td><span class="dn-badge-status neutral">${col.type}</span></td>`;
                        columnInfoContent.appendChild(row);
                    });
                    viewAllColsBtn.textContent = `View All ${fullColumnInfo.length} Columns`;
                    viewAllColsBtn.setAttribute('data-state', 'more');
                }
            });
        }

        // --- Duplicate Column Search & Quick Select Toolbar ---
        const dupSearchInput = document.getElementById('dnDupColSearchInput');
        if (dupSearchInput) {
            dupSearchInput.addEventListener('input', function () {
                const q = this.value.toLowerCase().trim();
                const pills = duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-col-pill') : [];
                pills.forEach(pill => {
                    const name = pill.querySelector('.dn-dup-col-name')?.textContent.toLowerCase() || '';
                    pill.style.display = (!q || name.includes(q)) ? 'inline-flex' : 'none';
                });
            });
        }

        const selectAllDupBtn = document.getElementById('btnSelectAllDupCols');
        if (selectAllDupBtn) {
            selectAllDupBtn.addEventListener('click', function () {
                const pills = duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-col-pill') : [];
                pills.forEach(pill => {
                    if (pill.style.display !== 'none') {
                        const chk = pill.querySelector('.dn-dup-check');
                        if (chk) chk.checked = true;
                    }
                });
                const countBadge = document.getElementById('dnDupSelectedColsCount');
                const checkedCount = duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-check:checked').length : 0;
                if (countBadge) countBadge.textContent = `${checkedCount} column(s) selected`;
            });
        }

        const clearDupBtn = document.getElementById('btnClearDupCols');
        if (clearDupBtn) {
            clearDupBtn.addEventListener('click', function () {
                const chks = duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-check') : [];
                chks.forEach(chk => { chk.checked = false; });
                const countBadge = document.getElementById('dnDupSelectedColsCount');
                if (countBadge) countBadge.textContent = `0 columns selected`;
            });
        }

        // Navigation button: Step 3B Duplicates -> Step 3C Drop Columns
        const dupGoToDropColsBtn = document.getElementById('dnDupGoToDropColsBtn');
        if (dupGoToDropColsBtn) {
            dupGoToDropColsBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const dropPanel = document.getElementById('dnDropColumnsPanel');
                if (dropPanel) {
                    dropPanel.style.display = 'block';
                    smoothScrollToTarget(dropPanel);
                    dropPanel.classList.add('dn-search-highlight-target');
                    setTimeout(() => dropPanel.classList.remove('dn-search-highlight-target'), 2000);
                }
            });
        }

        // Handle "Find Duplicates by Specific Columns" button click
        const removeSubKeepFirstBtn = document.getElementById('dnRemoveSubDuplicatesKeepFirstBtn');
        const removeSubKeepLastBtn = document.getElementById('dnRemoveSubDuplicatesKeepLastBtn');

        if (findSubDuplicatesBtn) {
            findSubDuplicatesBtn.addEventListener('click', function () {
                const selectedColumns = Array.from(duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-check:checked') : []).map(cb => cb.value);

                if (selectedColumns.length === 0) {
                    showToast('Please select at least one column to check for key duplicates.', 'warning');
                    return;
                }

                findSubDuplicatesBtn.disabled = true;
                findSubDuplicatesBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Finding...';
                if (removeSubKeepFirstBtn) removeSubKeepFirstBtn.style.display = 'none';
                if (removeSubKeepLastBtn) removeSubKeepLastBtn.style.display = 'none';

                fetch('/api/handle_duplicates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        dataset_id: activeDatasetId,
                        columns: selectedColumns,
                        action: 'find'
                    })
                })
                    .then(res => res.json())
                    .then(data => {
                        subDuplicateResult.style.display = 'block';
                        if (data.success && data.count > 0) {
                            subDuplicateResult.innerHTML = `
                                <div class="dn-alert dn-alert-info mb-2"><i class="bi bi-info-circle-fill me-1"></i> Found <strong>${data.count.toLocaleString()}</strong> rows sharing identical values across selected key columns (<strong>${selectedColumns.join(', ')}</strong>).</div>
                                <div class="table-responsive border rounded" style="max-height: 260px;">${data.preview_html}</div>
                            `;
                            if (removeSubKeepFirstBtn) removeSubKeepFirstBtn.style.display = 'inline-flex';
                            if (removeSubKeepLastBtn) removeSubKeepLastBtn.style.display = 'inline-flex';
                        } else if (data.success) {
                            subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-ok"><i class="bi bi-check-circle-fill me-1"></i> ${data.message || 'No duplicate rows found for the selected key columns.'}</div>`;
                        } else {
                            subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i> ${data.message || 'Failed to check for duplicates.'}</div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('findSubDuplicatesBtn', err);
                        subDuplicateResult.style.display = 'block';
                        subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i> Could not reach the server. Please try again.</div>`;
                    })
                    .finally(() => {
                        findSubDuplicatesBtn.disabled = false;
                        findSubDuplicatesBtn.innerHTML = '<i class="bi bi-search me-1"></i> Find Key Duplicates';
                    });
            });
        }

        // Helper for Subset Deduplication (Keep First / Keep Last)
        function executeSubsetDeduplication(keepStrategy, btnElement) {
            const selectedColumns = Array.from(duplicateColumnSelect ? duplicateColumnSelect.querySelectorAll('.dn-dup-check:checked') : []).map(cb => cb.value);
            if (selectedColumns.length === 0) {
                showToast('Please select at least one column to deduplicate.', 'warning');
                return;
            }

            const origHtml = btnElement ? btnElement.innerHTML : '';
            if (btnElement) {
                btnElement.disabled = true;
                btnElement.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span> Deduplicating...`;
            }

            fetch('/api/handle_duplicates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    columns: selectedColumns,
                    action: 'remove',
                    keep: keepStrategy
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Duplicate rows successfully removed!', 'success');
                        populateDatasetWorkspace(data);

                        if (data.cleaned_data) {
                            if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = data.cleaned_data.preview_html;
                            if (cleanedRows) cleanedRows.textContent = data.cleaned_data.row_count.toLocaleString();
                            if (cleanedCols) cleanedCols.textContent = data.cleaned_data.column_count.toLocaleString();
                            if (rowsRemoved) rowsRemoved.textContent = (data.rows_removed || 0).toLocaleString();
                        }

                        if (subDuplicateResult) {
                            subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-ok"><i class="bi bi-check-circle-fill me-1"></i> Deduplication complete. Removed <strong>${(data.rows_removed || 0).toLocaleString()}</strong> duplicate rows based on (${selectedColumns.join(', ')}).</div>`;
                        }
                        if (removeSubKeepFirstBtn) removeSubKeepFirstBtn.style.display = 'none';
                        if (removeSubKeepLastBtn) removeSubKeepLastBtn.style.display = 'none';

                        if (cleanedPreviewPanel) {
                            cleanedPreviewPanel.style.display = 'block';
                            updateCleanedDownloadLinks();
                        }
                    } else {
                        showToast(data.message || 'Failed to remove duplicates.', 'danger');
                    }
                })
                .catch(err => {
                    showFetchError('executeSubsetDeduplication', err);
                    showToast('Could not reach the server. Please try again.', 'danger');
                })
                .finally(() => {
                    if (btnElement) {
                        btnElement.disabled = false;
                        btnElement.innerHTML = origHtml;
                    }
                });
        }

        if (removeSubKeepFirstBtn) {
            removeSubKeepFirstBtn.addEventListener('click', function () {
                executeSubsetDeduplication('first', removeSubKeepFirstBtn);
            });
        }

        if (removeSubKeepLastBtn) {
            removeSubKeepLastBtn.addEventListener('click', function () {
                executeSubsetDeduplication('last', removeSubKeepLastBtn);
            });
        }

        // Handle "Remove Fully Identical Rows" button click
        if (removeFullDuplicatesBtn) {
            removeFullDuplicatesBtn.addEventListener('click', function () {
                handleRemoveFullDuplicates();
            });
        }

        // Function to handle the removal of fully identical duplicates
        function handleRemoveFullDuplicates() {
            const allColumns = fullColumnInfo.map(col => col.name);

            removeFullDuplicatesBtn.disabled = true;
            removeFullDuplicatesBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Removing...';

            fetch('/api/handle_duplicates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    columns: allColumns,
                    action: 'remove',
                    keep: 'first'
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Exact duplicate rows removed successfully!', 'success');
                        populateDatasetWorkspace(data);

                        if (duplicateSummary) {
                            duplicateSummary.className = 'dn-alert dn-alert-ok';
                            duplicateSummary.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> ${data.message || 'Zero exact duplicate rows remaining.'}`;
                        }

                        if (duplicatePreviewContent) duplicatePreviewContent.style.display = 'none';
                        if (removeFullDuplicatesBtn) removeFullDuplicatesBtn.style.display = 'none';

                        if (data.cleaned_data) {
                            if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = data.cleaned_data.preview_html;
                            if (cleanedRows) cleanedRows.textContent = data.cleaned_data.row_count.toLocaleString();
                            if (cleanedCols) cleanedCols.textContent = data.cleaned_data.column_count.toLocaleString();
                            if (rowsRemoved) rowsRemoved.textContent = (data.rows_removed || 0).toLocaleString();
                        }

                        if (cleanedPreviewPanel) {
                            cleanedPreviewPanel.style.display = 'block';
                            updateCleanedDownloadLinks();
                        }
                    } else {
                        showToast(data.message || 'Failed to remove duplicates.', 'danger');
                    }
                })
                .catch(err => {
                    showFetchError('handleRemoveFullDuplicates', err);
                    showToast('Could not remove duplicates — server error.', 'danger');
                })
                .finally(() => {
                    removeFullDuplicatesBtn.disabled = false;
                    removeFullDuplicatesBtn.innerHTML = '<i class="bi bi-trash me-1"></i> Remove Fully Identical Rows (100% Match)';
                });
        }

        if (missingStrategySelect) {
            missingStrategySelect.addEventListener('change', function () {
                if (this.value === 'fill_custom') {
                    missingCustomValueContainer.style.display = 'block';
                } else {
                    missingCustomValueContainer.style.display = 'none';
                }
            });
        }

        if (missingColumnSelect) {
            missingColumnSelect.addEventListener('change', updateCleaningStrategies);
        }

        if (applyCleaningBtn) {
            applyCleaningBtn.addEventListener('click', function () {
                const payload = {
                    dataset_id: activeDatasetId,
                    column: missingColumnSelect.value,
                    strategy: missingStrategySelect.value,
                    custom_value: missingCustomValueInput.value || null
                };

                if (payload.strategy === 'fill_custom' && !payload.custom_value) {
                    alert('Please enter a custom value.');
                    return;
                }

                applyCleaningBtn.disabled = true;
                applyCleaningBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Applying...';

                fetch('/api/clean_data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message || 'Data cleaning applied successfully!', 'success');
                            if (missingValueActions) missingValueActions.style.display = 'none';

                            const cleanedData = data.cleaned_data;
                            const summary = data.cleaning_summary;

                            if (cleanedData && summary) {
                                if (missingBefore) missingBefore.textContent = summary.missing_before.toLocaleString();
                                if (missingAfter) missingAfter.textContent = summary.missing_after.toLocaleString();
                                if (valuesFixed) valuesFixed.textContent = summary.values_fixed.toLocaleString();
                                if (rowsRemoved) rowsRemoved.textContent = summary.rows_removed.toLocaleString();

                                if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = cleanedData.preview_html;
                                if (cleanedRows) cleanedRows.textContent = cleanedData.row_count.toLocaleString();
                                if (cleanedCols) cleanedCols.textContent = cleanedData.column_count.toLocaleString();

                                if (cleanedPreviewPanel) cleanedPreviewPanel.style.display = 'block';
                                updateCleanedDownloadLinks();
                            }

                            const nextBanner = document.getElementById('dnMissingValueNextStepBanner');
                            if (nextBanner) nextBanner.style.display = 'block';

                            // Re-fetch dataset workspace state so Missing Values table & all overview cards reload instantly!
                            loadCurrentDataset(() => {
                                // Smoothly guide user to the next step: Review & Drop Columns
                                const dropPanel = document.getElementById('dnDropColumnsPanel');
                                if (dropPanel) {
                                    dropPanel.style.display = 'block';
                                    setTimeout(() => {
                                        smoothScrollToTarget(dropPanel);
                                    }, 200);
                                }
                            });
                        } else {
                            alert('Error cleaning data: ' + (data.message || 'Unknown error'));
                        }
                    })
                    .catch(err => {
                        showFetchError('applyCleaningBtn', err);
                        alert('Could not apply cleaning — the server could not be reached. Please try again.');
                    })
                    .finally(() => {
                        applyCleaningBtn.disabled = false;
                        applyCleaningBtn.innerHTML = 'Apply';
                    });
            });
        }

        // Helper to update Cleaned Dataset download links (CSV + Excel)
        function updateCleanedDownloadLinks() {
            if (!activeDatasetId) return;
            const csvBtn = document.getElementById('dnDownloadCleanedCsvBtn');
            const xlsxBtn = document.getElementById('dnDownloadCleanedXlsxBtn');
            if (csvBtn) {
                csvBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}?format=csv`;
            }
            if (xlsxBtn) {
                xlsxBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}?format=xlsx`;
            }
        }

        // Navigation button: Step 3A Imputation -> Step 3C Drop Columns
        const goToDropColsBtn = document.getElementById('dnGoToDropColumnsBtn');
        if (goToDropColsBtn) {
            goToDropColsBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const dropPanel = document.getElementById('dnDropColumnsPanel');
                if (dropPanel) {
                    dropPanel.style.display = 'block';
                    smoothScrollToTarget(dropPanel);
                    dropPanel.classList.add('dn-search-highlight-target');
                    setTimeout(() => dropPanel.classList.remove('dn-search-highlight-target'), 2000);
                }
            });
        }

        // Navigation button: Step 3C -> Cleaned Preview & Download
        const skipToCleanedBtn = document.getElementById('dnSkipToCleanedPreviewBtn');
        if (skipToCleanedBtn) {
            skipToCleanedBtn.addEventListener('click', function (e) {
                e.preventDefault();
                if (cleanedPreviewPanel) {
                    cleanedPreviewPanel.style.display = 'block';
                    updateCleanedDownloadLinks();
                    smoothScrollToTarget(cleanedPreviewPanel);
                }
            });
        }

        // Navigation button: Cleaned Preview -> Step 4 Statistical EDA
        const proceedToEdaBtn = document.getElementById('dnProceedToEdaBtn');
        if (proceedToEdaBtn) {
            proceedToEdaBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const edaSec = document.getElementById('step-eda');
                if (edaSec) {
                    smoothScrollToTarget(edaSec);
                }
            });
        }

        /* ---------------------------------------------------------------------
           3b. Smart Column Recommendations & Drop Actions
           ------------------------------------------------------------------- */
        const confirmDropBtn = document.getElementById('dnConfirmDropColumnsBtn');

        function executeDropColumns(columnsToDrop, btnElement, loadingText) {
            if (!activeDatasetId || !columnsToDrop || columnsToDrop.length === 0) {
                showToast('Please select at least one column to remove.', 'warning');
                return;
            }

            const origHtml = btnElement ? btnElement.innerHTML : '';
            if (btnElement) {
                btnElement.disabled = true;
                btnElement.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span> ${loadingText}`;
            }

            fetch('/api/drop_columns', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dataset_id: activeDatasetId, columns: columnsToDrop })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || `Successfully removed ${columnsToDrop.length} column(s)!`, 'success');
                        populateDatasetWorkspace(data);

                        // Update Cleaned Data Preview panel with cumulative dataset state (nulls + drops)
                        if (data.cleaned_data) {
                            if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = data.cleaned_data.preview_html;
                            if (cleanedRows) cleanedRows.textContent = data.cleaned_data.row_count.toLocaleString();
                            if (cleanedCols) cleanedCols.textContent = data.cleaned_data.column_count.toLocaleString();
                            if (missingAfter) missingAfter.textContent = (data.cleaned_data.missing_count || 0).toLocaleString();
                        } else if (data.preview_html) {
                            if (cleanedPreviewContent) cleanedPreviewContent.innerHTML = data.preview_html;
                            if (cleanedRows) cleanedRows.textContent = (data.row_count || 0).toLocaleString();
                            if (cleanedCols) cleanedCols.textContent = (data.column_count || 0).toLocaleString();
                            if (missingAfter) missingAfter.textContent = (data.total_missing_count || 0).toLocaleString();
                        }

                        if (cleanedPreviewPanel) {
                            cleanedPreviewPanel.style.display = 'block';
                            updateCleanedDownloadLinks();
                            setTimeout(() => {
                                smoothScrollToTarget(cleanedPreviewPanel);
                            }, 250);
                        }
                    } else {
                        showToast(data.message || 'Failed to drop columns.', 'danger');
                    }
                })
                .catch(err => {
                    showFetchError('executeDropColumns', err);
                    showToast('Could not connect to server. Please try again.', 'danger');
                })
                .finally(() => {
                    if (btnElement) {
                        btnElement.disabled = false;
                        btnElement.innerHTML = origHtml;
                    }
                });
        }

        if (confirmDropBtn) {
            confirmDropBtn.addEventListener('click', function () {
                const grid = document.getElementById('dnDropColumnsGrid');
                if (!grid) return;
                const checkedCols = Array.from(grid.querySelectorAll('.dn-col-drop-check:checked')).map(cb => cb.value);
                executeDropColumns(checkedCols, confirmDropBtn, 'Removing...');
            });
        }

        /* ---------------------------------------------------------------------
           4. AI Cleaning Suggestions
           ------------------------------------------------------------------- */
        if (getAISuggestionsBtn) {
            getAISuggestionsBtn.addEventListener('click', function () {
                if (!activeDatasetId) {
                    alert('Please upload a dataset first.');
                    return;
                }

                aiSuggestionsResult.style.display = 'none';
                aiUnwantedColumnsList.innerHTML = '';
                applyAIRemovalBtn.style.display = 'none';
                aiLoadingSpinner.style.display = 'block';
                getAISuggestionsBtn.disabled = true;
                getAISuggestionsBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Getting Suggestions...';

                fetch('/api/ai_suggest_cleaning', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId })
                })
                    .then(res => res.json())
                    .then(data => {
                        aiLoadingSpinner.style.display = 'none';
                        aiSuggestionsResult.style.display = 'block';

                        if (data.success && data.suggestions) {
                            const suggestions = data.suggestions;

                            if (suggestions.unwanted_columns && suggestions.unwanted_columns.length > 0) {
                                suggestions.unwanted_columns.forEach(col => {
                                    const checkboxHtml = `
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" value="${col.column_name}" id="ai-remove-${col.column_name}" checked>
                                        <label class="form-check-label" for="ai-remove-${col.column_name}">
                                            <strong>${col.column_name}</strong>: ${col.reason}
                                        </label>
                                    </div>`;
                                    aiUnwantedColumnsList.insertAdjacentHTML('beforeend', checkboxHtml);
                                });
                                applyAIRemovalBtn.style.display = 'block';
                            } else {
                                aiUnwantedColumnsList.innerHTML = '<div class="dn-alert dn-alert-ok"><i class="bi bi-check-circle-fill"></i> No specific columns suggested for removal.</div>';
                            }

                            const aiNewFeaturesList = document.getElementById('aiNewFeaturesList');
                            if (aiNewFeaturesList) {
                                aiNewFeaturesList.innerHTML = '';
                                if (suggestions.new_features && suggestions.new_features.length > 0) {
                                    suggestions.new_features.forEach(feature => {
                                        const listItem = `<li><i class="bi bi-lightbulb-fill text-primary me-2"></i><strong>${feature.feature_name}</strong>: ${feature.description} (Derivation: ${feature.derivation_idea})</li>`;
                                        aiNewFeaturesList.insertAdjacentHTML('beforeend', listItem);
                                    });
                                } else {
                                    aiNewFeaturesList.innerHTML = '<li><i class="bi bi-info-circle-fill text-muted me-2"></i>No new features suggested at this time.</li>';
                                }
                            }

                        } else {
                            aiSuggestionsResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Failed to get AI suggestions.'}</div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('getAISuggestionsBtn', err);
                        aiLoadingSpinner.style.display = 'none';
                        aiSuggestionsResult.style.display = 'block';
                        aiSuggestionsResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> Could not reach the server. Please try again.</div>`;
                    })
                    .finally(() => {
                        getAISuggestionsBtn.disabled = false;
                        getAISuggestionsBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Get AI Suggestions';
                    });
            });
        }

        if (applyAIRemovalBtn) {
            applyAIRemovalBtn.addEventListener('click', function () {
                const columnsToRemove = Array.from(aiUnwantedColumnsList.querySelectorAll('input:checked')).map(cb => cb.value);

                if (columnsToRemove.length === 0) {
                    alert('Please select at least one column to remove.');
                    return;
                }

                applyAIRemovalBtn.disabled = true;
                applyAIRemovalBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Removing...';

                fetch('/api/ai_apply_column_removal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId, columns_to_remove: columnsToRemove })
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            columnInfoContent.innerHTML = '';
                            fullColumnInfo = data.column_info;
                            const initialColumns = fullColumnInfo.slice(0, 4);
                            initialColumns.forEach(function (col) {
                                var row = document.createElement('tr');
                                row.innerHTML = `
                                <td>${col.name}</td>
                                <td><span class="dn-badge-status neutral">${col.type}</span></td>
                            `;
                                columnInfoContent.appendChild(row);
                            });
                            if (fullColumnInfo.length > 4) {
                                viewAllColsBtn.textContent = `View All ${fullColumnInfo.length} Columns`;
                                columnInfoFooter.style.display = 'block';
                            } else {
                                columnInfoFooter.style.display = 'none';
                            }

                            previewContent.innerHTML = data.preview_html;
                            overviewCols.textContent = data.column_count.toLocaleString();

                            aiSuggestionsResult.innerHTML = `
                            <div class="dn-alert dn-alert-ok">
                                <i class="bi bi-check-circle-fill"></i> ${data.message}
                            </div>
                        `;
                            const downloadBtn = document.createElement('a');
                            downloadBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}`;
                            downloadBtn.className = 'btn dn-btn-success btn-sm mt-2';
                            downloadBtn.innerHTML = '<i class="bi bi-download"></i> Download Cleaned Dataset (CSV)';
                            aiSuggestionsResult.appendChild(downloadBtn);

                            getAISuggestionsBtn.style.display = 'none';
                        } else {
                            alert('Error applying AI column removal: ' + (data.message || 'Unknown error'));
                        }
                    })
                    .catch(err => {
                        showFetchError('applyAIRemovalBtn', err);
                        alert('Could not apply column removal — the server could not be reached. Please try again.');
                    })
                    .finally(() => {
                        applyAIRemovalBtn.disabled = false;
                        applyAIRemovalBtn.innerHTML = '<i class="bi bi-trash"></i> Remove Selected Columns';
                    });
            });
        }

        /* ---------------------------------------------------------------------
           5. Automatic EDA Generation
           ------------------------------------------------------------------- */
        if (generateEDABtn) {
            generateEDABtn.addEventListener('click', function () {
                if (!activeDatasetId) {
                    alert('Please upload a dataset first.');
                    return;
                }

                edaResultContainer.innerHTML = '';
                edaLoadingSpinner.style.display = 'block';
                generateEDABtn.disabled = true;
                generateEDABtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Generating...';

                fetch('/api/generate_eda', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId })
                })
                    .then(res => res.json())
                    .then(data => {
                        edaLoadingSpinner.style.display = 'none';
                        if (data.success && data.recommended_charts) {
                            window.cachedEdaCharts = data.recommended_charts;
                            // renderEdaCharts() now makes #dnAutoEDAPanel visible itself
                            // (before drawing any chart into it), so just scroll to it here.
                            renderEdaCharts(data.recommended_charts);
                            if (autoEDAPanel) {
                                autoEDAPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }
                        } else {
                            edaResultContainer.innerHTML = `<div class="col-12"><div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Failed to generate EDA report.'}</div></div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('generateEDABtn', err);
                        edaLoadingSpinner.style.display = 'none';
                        edaResultContainer.innerHTML = `<div class="col-12"><div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> Could not reach the server. Please try again.</div></div>`;
                    })
                    .finally(() => {
                        generateEDABtn.disabled = false;
                        generateEDABtn.innerHTML = '<i class="bi bi-play-circle"></i> Generate EDA Report';
                    });
            });
        }

        /* ---------------------------------------------------------------------
           6. Correlation and Scatter Plot Generation
           ------------------------------------------------------------------- */
        if (generateCorrelationBtn) {
            generateCorrelationBtn.addEventListener('click', function () {
                if (!activeDatasetId) {
                    showToast('Please upload or select a dataset first.', 'warning');
                    return;
                }

                if (correlationAlertMsg) correlationAlertMsg.style.display = 'none';
                if (correlationResultContainer) correlationResultContainer.style.display = 'none';
                if (scatterPlotResult) scatterPlotResult.style.display = 'none';
                if (correlationLoadingSpinner) correlationLoadingSpinner.style.display = 'block';
                generateCorrelationBtn.disabled = true;
                generateCorrelationBtn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Analyzing...';

                fetch('/api/get_correlation_matrix', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId })
                })
                    .then(res => res.json())
                    .then(data => {
                        if (correlationLoadingSpinner) correlationLoadingSpinner.style.display = 'none';
                        if (data.success && data.heatmap_plot) {
                            if (correlationHeatmap) {
                                correlationHeatmap.src = `data:image/png;base64,${data.heatmap_plot}`;
                                correlationHeatmap.style.display = 'inline-block';
                            }

                            if (scatterXSelect && scatterYSelect) {
                                scatterXSelect.innerHTML = '';
                                scatterYSelect.innerHTML = '';
                                (data.numeric_columns || []).forEach(col => {
                                    scatterXSelect.add(new Option(col, col));
                                    scatterYSelect.add(new Option(col, col));
                                });
                                if (data.numeric_columns && data.numeric_columns.length > 1) {
                                    scatterYSelect.selectedIndex = 1;
                                }
                            }

                            if (correlationResultContainer) {
                                correlationResultContainer.style.display = 'block';
                            }

                            // --- Populate Top Correlations ---
                            const topCorrelationsContainer = document.getElementById('dnTopCorrelationsContainer');
                            const topPositiveList = document.getElementById('dnTopPositiveCorrelations');
                            const topNegativeList = document.getElementById('dnTopNegativeCorrelations');

                            if (topCorrelationsContainer && topPositiveList && topNegativeList) {
                                topPositiveList.innerHTML = '';
                                topNegativeList.innerHTML = '';

                                if (data.top_positive && data.top_positive.length > 0) {
                                    data.top_positive.forEach(item => {
                                        const li = `<li class="list-group-item dn-corr-item d-flex justify-content-between align-items-center small py-2 px-3">
                                            <span class="d-flex align-items-center gap-2 fw-medium">
                                                <i class="bi bi-arrow-up-right text-success"></i>
                                                <span>${item.var1} <span class="text-muted">&harr;</span> ${item.var2}</span>
                                            </span>
                                            <span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-2 py-1 fw-semibold">+${Number(item.correlation).toFixed(3)}</span>
                                        </li>`;
                                        topPositiveList.insertAdjacentHTML('beforeend', li);
                                    });
                                } else {
                                    topPositiveList.innerHTML = '<li class="list-group-item text-muted small">No significant positive correlation pairs.</li>';
                                }

                                if (data.top_negative && data.top_negative.length > 0) {
                                    data.top_negative.forEach(item => {
                                        const li = `<li class="list-group-item dn-corr-item d-flex justify-content-between align-items-center small py-2 px-3">
                                            <span class="d-flex align-items-center gap-2 fw-medium">
                                                <i class="bi bi-arrow-down-right text-danger"></i>
                                                <span>${item.var1} <span class="text-muted">&harr;</span> ${item.var2}</span>
                                            </span>
                                            <span class="badge bg-danger-subtle text-danger border border-danger-subtle rounded-pill px-2 py-1 fw-semibold">${Number(item.correlation).toFixed(3)}</span>
                                        </li>`;
                                        topNegativeList.insertAdjacentHTML('beforeend', li);
                                    });
                                } else {
                                    topNegativeList.innerHTML = '<li class="list-group-item text-muted small">No significant negative correlation pairs.</li>';
                                }

                                topCorrelationsContainer.style.display = 'block';
                            }
                            showToast('Correlation matrix generated successfully!', 'success');
                        } else {
                            if (correlationAlertMsg) {
                                correlationAlertMsg.className = 'dn-alert dn-alert-warn mb-3';
                                correlationAlertMsg.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i> ${data.message || 'Failed to generate correlation matrix.'}`;
                                correlationAlertMsg.style.display = 'block';
                            } else {
                                showToast(data.message || 'Failed to generate correlation matrix.', 'warning');
                            }
                        }
                    })
                    .catch(err => {
                        showFetchError('generateCorrelationBtn', err);
                        if (correlationLoadingSpinner) correlationLoadingSpinner.style.display = 'none';
                        if (correlationAlertMsg) {
                            correlationAlertMsg.className = 'dn-alert dn-alert-danger mb-3';
                            correlationAlertMsg.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i> Could not reach the server. Please try again.`;
                            correlationAlertMsg.style.display = 'block';
                        }
                    })
                    .finally(() => {
                        generateCorrelationBtn.disabled = false;
                        generateCorrelationBtn.innerHTML = '<i class="bi bi-play-circle me-1"></i> Analyze Correlations';
                    });
            });
        }

        if (generateScatterBtn) {
            generateScatterBtn.addEventListener('click', function () {
                const xCol = scatterXSelect ? scatterXSelect.value : '';
                const yCol = scatterYSelect ? scatterYSelect.value : '';
                if (!xCol || !yCol) {
                    showToast('Please select variables for both axes.', 'warning');
                    return;
                }

                const scatterSpinner = document.getElementById('dnScatterLoadingSpinner');
                const scatterImg = document.getElementById('dnScatterPlotImg');

                if (scatterPlotResult) scatterPlotResult.style.display = 'block';
                if (scatterSpinner) scatterSpinner.style.display = 'inline-block';
                if (scatterImg) scatterImg.style.display = 'none';
                generateScatterBtn.disabled = true;
                generateScatterBtn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Plotting...';

                fetch('/api/get_scatter_plot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId, x_col: xCol, y_col: yCol })
                })
                    .then(res => res.json())
                    .then(data => {
                        if (scatterSpinner) scatterSpinner.style.display = 'none';
                        if (data.success && data.scatter_plot) {
                            if (scatterImg) {
                                scatterImg.src = `data:image/png;base64,${data.scatter_plot}`;
                                scatterImg.style.display = 'inline-block';
                            }
                        } else {
                            showToast(data.message || 'Failed to generate scatter plot.', 'danger');
                        }
                    })
                    .catch(err => {
                        showFetchError('generateScatterBtn', err);
                        if (scatterSpinner) scatterSpinner.style.display = 'none';
                        showToast('Could not reach the server to generate scatter plot.', 'danger');
                    })
                    .finally(() => {
                        generateScatterBtn.disabled = false;
                        generateScatterBtn.innerHTML = 'Generate Plot';
                    });
            });
        }
    }

    // Helper function to render charts (used by EDA generation, dataset load, and 2D/3D mode toggling)
    window.cachedEdaCharts = [];
    function renderEdaCharts(charts, modeOverride) {
        if (!edaResultContainer) return;
        charts = charts || window.cachedEdaCharts || [];
        window.cachedEdaCharts = charts;

        // BUGFIX: Destroy any previously-rendered Plotly instances BEFORE wiping the
        // container's innerHTML. Plotly attaches a WebGL context (for 3D charts) and
        // internal event listeners to each chart <div>; simply overwriting innerHTML
        // leaves those contexts orphaned. Browsers only allow a small number of
        // simultaneous WebGL contexts (commonly 8-16), so repeatedly generating EDA
        // or toggling the 2D/3D preference without purging eventually exhausts that
        // limit and NEW charts render blank, corrupted, or "random"-looking.
        if (window.Plotly) {
            edaResultContainer.querySelectorAll('.dn-eda-plot > div[id^="dnPlotlyChart_"]').forEach(node => {
                try { Plotly.purge(node); } catch (e) { /* ignore */ }
            });
        }
        edaResultContainer.innerHTML = '';

        if (charts.length === 0) {
            edaResultContainer.innerHTML = `<div class="col-12"><div class="dn-alert dn-alert-info"><i class="bi bi-info-circle-fill"></i> No specific chart recommendations could be generated for this dataset.</div></div>`;
            return;
        }

        // BUGFIX: Make the EDA panel visible BEFORE any chart is drawn into it, not
        // after. #dnAutoEDAPanel starts as display:none. Plotly.newPlot() measures the
        // container's actual pixel width/height at call time — if the parent is
        // display:none that measurement is 0x0, so every chart (2D or 3D) gets drawn
        // at zero/garbled size and never recovers on its own. This was the main cause
        // of charts looking "random"/broken regardless of the 2D/3D setting.
        if (autoEDAPanel) {
            autoEDAPanel.style.display = 'block';
        }

        const currentPrefs = JSON.parse(localStorage.getItem('datanova_analyst_prefs') || '{}');
        const renderingEngine = modeOverride || currentPrefs.chartType || document.getElementById('prefChartTypeSelect')?.value || 'interactive_3d';
        const isDarkMode = document.documentElement.getAttribute('data-bs-theme') === 'dark';

        charts.forEach((chart, idx) => {
            // Deterministic id (container is always cleared/purged above, so no collision risk)
            const chartContainerId = `dnPlotlyChart_${idx}`;
            const is3D = Boolean(chart.is_3d);

            let cardTitle = chart.title;
            let cardDesc = chart.description;
            let badgeHtml = '';

            if (renderingEngine === '2d_standard') {
                cardTitle = chart.title_2d || (is3D ? chart.title.replace(/3D Spatial Projection/gi, 'Multi-Variable Interaction Scatter') : chart.title);
                cardDesc = chart.description_2d || chart.description;
                badgeHtml = `<span class="badge bg-secondary-subtle text-secondary me-2"><i class="bi bi-graph-up me-1"></i>2D Standard</span>`;
            } else if (is3D) {
                cardTitle = chart.title_3d || chart.title;
                cardDesc = chart.description_3d || chart.description;
                badgeHtml = `<span class="badge bg-primary-subtle text-primary me-2"><i class="bi bi-box me-1"></i>3D Dynamic (Plotly)</span>`;
            } else {
                badgeHtml = `<span class="badge bg-info-subtle text-info me-2"><i class="bi bi-bar-chart-line me-1"></i>Interactive Plotly</span>`;
            }

            // BUGFIX: '2d_standard' used to fall back to min-height:auto, which collapses
            // to 0px until the base64 <img> finishes decoding, causing a layout jump/flash.
            const isHeatmap = (chart.chart_type === 'heatmap');
            const minHeight = isHeatmap ? '460px' : ((renderingEngine === 'interactive_3d' && is3D) ? '420px' : '360px');
            const colClass = isHeatmap ? 'col-12 mb-3' : 'col-lg-6 mb-3';
            const imgMaxHeight = isHeatmap ? '540px' : '380px';

            const cardHtml = `
                <div class="${colClass}">
                    <div class="dn-eda-card h-100 d-flex flex-column justify-content-between">
                        <div class="dn-eda-card-header d-flex justify-content-between align-items-start pb-2 border-bottom">
                            <div>
                                <h5 class="dn-eda-card-title fw-bold mb-1">${cardTitle}</h5>
                                <p class="dn-eda-card-sub text-muted small mb-0">${cardDesc}</p>
                            </div>
                            <div>${badgeHtml}</div>
                        </div>
                        <div class="dn-eda-card-body flex-grow-1 d-flex align-items-center justify-content-center p-3">
                            <div class="dn-eda-plot position-relative w-100">
                                <div id="${chartContainerId}" style="width: 100%; min-height: ${minHeight};"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            edaResultContainer.insertAdjacentHTML('beforeend', cardHtml);

            const el = document.getElementById(chartContainerId);
            if (!el) return;

            if (renderingEngine === '2d_standard') {
                // 2D Standard Rendering: Show crisp high-res 2D image (no 3D projection box)
                const imgData = chart.plot_2d || chart.plot;
                if (imgData) {
                    el.innerHTML = `<div class="text-center w-100 py-2"><img src="data:image/png;base64,${imgData}" alt="${cardTitle}" class="img-fluid rounded shadow-sm" style="max-height: ${imgMaxHeight}; width: 100%; object-fit: contain;"></div>`;
                } else if (chart.plotly_json && window.Plotly) {
                    const layout = JSON.parse(JSON.stringify(chart.plotly_json.layout || {}));
                    layout.autosize = true;
                    layout.paper_bgcolor = 'transparent';
                    layout.plot_bgcolor = 'transparent';
                    layout.font = { color: isDarkMode ? '#E2E8F0' : '#1E293B', family: 'Inter, sans-serif' };
                    Plotly.newPlot(chartContainerId, chart.plotly_json.data || [], layout, { responsive: true, displayModeBar: false });
                }
            } else {
                // Interactive 3D / 2D Plotly Engine
                if (chart.plotly_json && window.Plotly) {
                    try {
                        const layout = JSON.parse(JSON.stringify(chart.plotly_json.layout || {}));
                        layout.autosize = true;
                        layout.paper_bgcolor = 'transparent';
                        layout.plot_bgcolor = 'transparent';
                        layout.font = { color: isDarkMode ? '#E2E8F0' : '#1E293B', family: 'Inter, sans-serif' };

                        if (is3D && layout.scene) {
                            layout.scene.bgcolor = 'transparent';
                            layout.scene.camera = layout.scene.camera || { eye: { x: 1.55, y: 1.55, z: 1.2 } };
                            layout.scene.aspectratio = layout.scene.aspectratio || { x: 1.1, y: 1.1, z: 0.85 };
                        }

                        Plotly.newPlot(chartContainerId, chart.plotly_json.data || [], layout, {
                            responsive: true,
                            displayModeBar: 'hover',
                            displaylogo: false,
                            modeBarButtonsToRemove: [
                                'sendDataToCloud',
                                'lasso2d',
                                'select2d',
                                'hoverClosestCartesian',
                                'hoverCompareCartesian',
                                'toggleSpikelines',
                                'hoverClosest3d'
                            ],
                            toImageButtonOptions: {
                                format: 'png',
                                filename: (cardTitle || 'datanova_eda_chart').toLowerCase().replace(/[^a-z0-9]/g, '_'),
                                height: 600,
                                width: 900,
                                scale: 2
                            }
                        });
                    } catch (e) {
                        console.warn("Plotly render failed, using fallback img:", e);
                        const fallbackImg = is3D ? (chart.plot_3d || chart.plot) : (chart.plot_2d || chart.plot);
                        if (fallbackImg) {
                            el.innerHTML = `<div class="text-center w-100 py-2"><img src="data:image/png;base64,${fallbackImg}" alt="${cardTitle}" class="img-fluid rounded shadow-sm" style="max-height: ${imgMaxHeight}; width: 100%; object-fit: contain;"></div>`;
                        }
                    }
                } else {
                    const fallbackImg = is3D ? (chart.plot_3d || chart.plot) : (chart.plot_2d || chart.plot);
                    if (fallbackImg) {
                        el.innerHTML = `<div class="text-center w-100 py-2"><img src="data:image/png;base64,${fallbackImg}" alt="${cardTitle}" class="img-fluid rounded shadow-sm" style="max-height: ${imgMaxHeight}; width: 100%; object-fit: contain;"></div>`;
                    }
                }
            }
        });

        // Safety net: force every Plotly chart to re-measure its container once the
        // browser has actually painted the now-visible panel. Covers edge cases (e.g.
        // sidebar collapse/expand, modal transitions) where the initial measurement
        // could still be stale even though the panel is no longer display:none.
        if (window.Plotly) {
            requestAnimationFrame(() => {
                edaResultContainer.querySelectorAll('.dn-eda-plot > div[id^="dnPlotlyChart_"]').forEach(node => {
                    try { Plotly.Plots.resize(node); } catch (e) { /* ignore */ }
                });
            });
        }
    }
    window.renderEdaCharts = renderEdaCharts;

    function loadEdaResults(datasetId) {
        if (!datasetId) return;
        fetch(`/api/get_eda_results/${datasetId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.recommended_charts && edaResultContainer) {
                    window.cachedEdaCharts = data.recommended_charts;
                    renderEdaCharts(data.recommended_charts);
                }
            })
            .catch(error => showFetchError('loadEdaResults', error));
    }

    const exportReportBtn = document.getElementById('dnExportReportBtn');
    if (exportReportBtn) {
        exportReportBtn.addEventListener('click', function () {
            if (!activeDatasetId) { showToast('Please upload a dataset first.', 'warning'); return; }
            window.location.href = `/api/export_eda_report/${activeDatasetId}`;
        });
    }

    const rollbackDatasetBtn = document.getElementById('dnRollbackDatasetBtn');
    if (rollbackDatasetBtn) {
        const rollbackModal = new bootstrap.Modal(document.getElementById('rollbackConfirmModal'));
        const confirmRollbackBtn = document.getElementById('confirmRollbackBtn');

        rollbackDatasetBtn.addEventListener('click', function () {
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }
            rollbackModal.show();
        });

        if (confirmRollbackBtn) {
            confirmRollbackBtn.addEventListener('click', function () {
                confirmRollbackBtn.disabled = true;
                confirmRollbackBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rolling back...';

                fetch('/api/rollback_dataset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId })
                })
                    .then(res => res.json())
                    .then(data => {
                        rollbackModal.hide();
                        if (data.success) {
                            alert('Dataset successfully rolled back to its raw state!');
                            loadCurrentDataset();
                        } else {
                            alert('Rollback failed: ' + (data.message || 'Unknown error'));
                        }
                    })
                    .catch(err => {
                        showFetchError('confirmRollbackBtn', err);
                        rollbackModal.hide();
                        alert('Rollback failed — the server could not be reached. Please try again.');
                    })
                    .finally(() => {
                        confirmRollbackBtn.disabled = false;
                        confirmRollbackBtn.innerHTML = '<i class="bi bi-trash"></i> Yes, Rollback';
                    });
            });
        }
    }

    // Handle Download Cleaned Dataset (CSV & Excel)
    const downloadCSVBtn = document.getElementById('dnDownloadCleanedCSV');
    const downloadExcelBtn = document.getElementById('dnDownloadCleanedExcel');

    if (downloadCSVBtn) {
        downloadCSVBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }
            window.location.href = `/api/download_cleaned_dataset/${activeDatasetId}?format=csv`;
        });
    }

    if (downloadExcelBtn) {
        downloadExcelBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }
            window.location.href = `/api/download_cleaned_dataset/${activeDatasetId}?format=excel`;
        });
    }

    // Handle Custom Chart Builder
    const customXSelect = document.getElementById('dnCustomXSelect');
    const customYSelect = document.getElementById('dnCustomYSelect');
    const customChartTypeSelect = document.getElementById('dnCustomChartTypeSelect');
    const customAggSelect = document.getElementById('dnCustomAggSelect');
    const generateCustomChartBtn = document.getElementById('dnGenerateCustomChartBtn');
    const customChartResult = document.getElementById('dnCustomChartResult');
    const customChartSpinner = document.getElementById('dnCustomChartSpinner');
    const customChartImg = document.getElementById('dnCustomChartImg');

    function updateChartRecommendations() {
        if (!activeDatasetId || !customXSelect || !customXSelect.value || !customChartTypeSelect) return;

        const xCol = customXSelect.value;
        const yCol = customYSelect ? customYSelect.value : null;

        fetch('/api/recommend_charts_for_columns', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: activeDatasetId,
                x_col: xCol,
                y_col: yCol
            })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.chart_options) {
                    customChartTypeSelect.innerHTML = '';
                    data.chart_options.forEach(opt => {
                        const optionElem = document.createElement('option');
                        optionElem.value = opt.value;
                        optionElem.textContent = opt.label;
                        if (opt.recommended) {
                            optionElem.classList.add('fw-bold', 'text-success');
                        }
                        customChartTypeSelect.appendChild(optionElem);
                    });
                }
            })
            .catch(err => showFetchError('updateChartRecommendations', err));
    }

    if (customXSelect) customXSelect.addEventListener('change', updateChartRecommendations);
    if (customYSelect) customYSelect.addEventListener('change', updateChartRecommendations);

    if (generateCustomChartBtn) {
        generateCustomChartBtn.addEventListener('click', function () {
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }
            if (!customXSelect || !customXSelect.value) { alert('Please select an X-Axis column.'); return; }

            const xCol = customXSelect.value;
            const yCol = customYSelect ? customYSelect.value : null;
            const chartType = customChartTypeSelect ? customChartTypeSelect.value : 'bar';
            const aggFunc = customAggSelect ? customAggSelect.value : 'sum';

            if (customChartResult) customChartResult.style.display = 'block';
            if (customChartSpinner) customChartSpinner.style.display = 'inline-block';
            if (customChartImg) customChartImg.style.display = 'none';

            fetch('/api/generate_custom_chart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    x_col: xCol,
                    y_col: yCol,
                    chart_type: chartType,
                    agg_func: aggFunc
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (customChartSpinner) customChartSpinner.style.display = 'none';
                    if (data.success && data.plot) {
                        if (customChartImg) {
                            const rawPlot = typeof data.plot === 'object' ? data.plot.plot : data.plot;
                            if (rawPlot) {
                                const imgSrc = rawPlot.startsWith('data:image') ? rawPlot : `data:image/png;base64,${rawPlot}`;
                                customChartImg.src = imgSrc;
                                customChartImg.style.display = 'inline-block';
                            }
                        }
                    } else {
                        alert('Error generating graph: ' + (data.message || 'Unknown error'));
                        if (customChartResult) customChartResult.style.display = 'none';
                    }
                })
                .catch(err => {
                    if (customChartSpinner) customChartSpinner.style.display = 'none';
                    showFetchError('generateCustomChartBtn', err);
                    alert('An error occurred while generating the graph.');
                });
        });
    }

    // Function to add tooltips to the statistical summary table
    function addTooltipsToStatsTable() {
        const metricDescriptions = {
            'column': 'Column Name: Attribute or feature name in your dataset.',
            'count': 'Count: Number of valid (non-null) data records in this column.',
            'unique_count': 'Unique Count: Number of distinct or unique non-null values in this column.',
            'unique_ratio': 'Unique Ratio: Ratio of unique values to total count (Unique Count / Count). Higher values indicate higher cardinality.',
            'mean': 'Mean: Arithmetic average value of the data points in this column.',
            'median': 'Median: Middle value when data is ordered (50th percentile).',
            'std': 'Standard Deviation (STD): Measures average dispersion or spread of data points from the mean.',
            'variance': 'Variance: Average of squared differences from the mean, representing overall data spread.',
            'cv': 'Coefficient of Variation (CV = Std / |Mean|): Measures relative variability independent of measurement scale.',
            'mad': 'Mean Absolute Deviation (MAD): Average distance of data points from the column mean.',
            'min': 'Minimum (Min): Lowest recorded value in this column.',
            'max': 'Maximum (Max): Highest recorded value in this column.',
            'range': 'Range: Difference between Maximum and Minimum values (Max - Min).',
            'iqr': 'Interquartile Range (IQR = 75th% - 25th%): Range of middle 50% of values.',
            'skewness': 'Skewness: Measures distribution asymmetry around the mean (>0 right-skewed, <0 left-skewed).',
            'skew': 'Skewness: Measures distribution asymmetry around the mean (>0 right-skewed, <0 left-skewed).',
            'kurtosis': 'Kurtosis: Measures distribution peakness and tail heaviness (>3 heavy-tailed).',
            'kurt': 'Kurtosis: Measures distribution peakness and tail heaviness (>3 heavy-tailed).',
            '25pct': '25th Percentile (1st Quartile - Q1): 25% of values fall below this point.',
            '50pct': '50th Percentile (Median - Q2): 50% of values fall below this point.',
            '75pct': '75th Percentile (3rd Quartile - Q3): 75% of values fall below this point.',
            '25%': '25th Percentile (1st Quartile - Q1): 25% of values fall below this point.',
            '50%': '50th Percentile (Median - Q2): 50% of values fall below this point.',
            '75%': '75th Percentile (3rd Quartile - Q3): 75% of values fall below this point.',
            'missing_count': 'Missing Count: Total number of empty, null, or NaN cells in this column.',
            'missing_pct': 'Missing Percentage: Percentage of missing cells in this column.',
            'missing_ratio': 'Missing Ratio: Proportion of missing cells in this column.'
        };

        const statsHeaders = document.querySelectorAll('.dn-table-stats thead th, #dnStatsContent table thead th, .dn-table-preview thead th');
        if (!statsHeaders || statsHeaders.length === 0) return;

        statsHeaders.forEach(header => {
            if (!header || !header.textContent) return;
            let metricName = header.textContent.trim().toLowerCase();
            let description = metricDescriptions[metricName] || header.getAttribute('title');

            if (!description && metricName.startsWith('pct')) {
                const numericPart = parseFloat(metricName);
                if (!isNaN(numericPart) && metricDescriptions[`${numericPart}%`]) {
                    description = metricDescriptions[`${numericPart}%`];
                }
            }

            if (description) {
                header.setAttribute('data-bs-toggle', 'tooltip');
                header.setAttribute('data-bs-placement', 'top');
                header.setAttribute('title', description);
                header.style.cursor = 'help';
                try {
                    const tooltipInstance = bootstrap.Tooltip.getInstance(header);
                    if (tooltipInstance) tooltipInstance.dispose();
                    new bootstrap.Tooltip(header);
                } catch (e) {
                    // Ignore if Bootstrap Tooltip fails
                }
            }
        });
    }

    // Bind multi-format report downloads
    function setupReportDownloadButtons() {
        const formats = [
            { id: 'btnDownloadHtml', endpoint: '/api/export_eda_report/' },
            { id: 'btnDownloadPdf', endpoint: '/api/export_pdf/' },
            { id: 'btnDownloadWord', endpoint: '/api/export_word/' },
            { id: 'btnDownloadPpt', endpoint: '/api/export_ppt/' },
            { id: 'btnDownloadExcel', endpoint: '/api/export_excel/' },
            { id: 'btnQuickReport', endpoint: '/api/export_pdf/' }
        ];

        formats.forEach(item => {
            const btn = document.getElementById(item.id);
            if (btn) {
                btn.addEventListener('click', function () {
                    if (!activeDatasetId) {
                        showToast("Please upload or select a dataset first.", "warning");
                        return;
                    }
                    window.open(item.endpoint + activeDatasetId, '_blank');
                });
            }
        });
    }

    setupReportDownloadButtons();

    // --- Dynamic Analyst Dashboard Analytics & Plotly Previews ---
    function fetchAnalystAnalytics() {
        fetch('/api/analyst/dashboard_data')
            .then(res => res.json())
            .then(resData => {
                if (resData.success && resData.data) {
                    renderAnalystAnalytics(resData.data);
                }
            })
            .catch(err => {
                console.log("Analyst analytics fetch warning: ", err);
                renderDefaultAnalystPlotly();
            });
    }

    function renderAnalystAnalytics(data) {
        if (data.ai_insights && Array.isArray(data.ai_insights)) {
            const listEl = document.getElementById('analystAiInsightsList');
            if (listEl) {
                listEl.innerHTML = data.ai_insights.map(ins => `
                    <li><span class="dn-insight-dot" style="background:var(--dn-primary)"></span>${ins}</li>
                `).join('');
            }
        }
    }

    // ML Tool Cards Click Handlers
    document.querySelectorAll('.dn-clickable-tool').forEach(toolCard => {
        toolCard.addEventListener('click', function () {
            const toolType = this.getAttribute('data-tool') || 'analytics';
            if (!activeDatasetId) {
                showToast("Please upload or select a dataset first.", "warning");
                return;
            }
            if (toolType === 'forecasting' || toolType === 'regression') {
                const chartPanel = document.getElementById('dnCustomChartPanel');
                if (chartPanel) {
                    chartPanel.style.display = 'block';
                    chartPanel.scrollIntoView({ behavior: 'smooth' });
                    showToast(`Select columns to build custom ${toolType} visualizations.`, "info");
                }
            } else if (toolType === 'anomaly') {
                const edaPanel = document.getElementById('dnAutoEDAPanel');
                if (edaPanel) {
                    edaPanel.style.display = 'block';
                    edaPanel.scrollIntoView({ behavior: 'smooth' });
                    showToast("Running anomaly and outlier profiling...", "info");
                }
            } else {
                showToast(`ML Tool '${toolType}' activated for active dataset #${activeDatasetId}.`, "success");
            }
        });
    });

    /* ---------------------------------------------------------------------
       Assigned Work / Tasks Handlers for Analyst
       ------------------------------------------------------------------- */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderAnalystTasks(tasks) {
        const tbody = document.getElementById('analystAssignedTasksTableBody');
        const badge = document.getElementById('analystAssignedTasksBadge');
        const profileBadge = document.getElementById('profileAssignedTasksCount');
        const incompleteCount = (tasks || []).filter(t => t.status !== 'Completed').length;
        if (badge) {
            badge.textContent = incompleteCount;
        }
        if (profileBadge) {
            profileBadge.textContent = `${incompleteCount} Tasks`;
        }
        if (!tbody) return;

        if (!tasks || tasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-secondary py-4">
                        <i class="bi bi-check2-circle fs-3 d-block mb-1 text-muted"></i> No tasks currently assigned to you.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = tasks.map(task => {
            let priorityBadge = '<span class="badge bg-info-subtle text-info border border-info-subtle">Low</span>';
            if (task.priority === 'High') {
                priorityBadge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-exclamation-triangle me-1"></i>High</span>';
            } else if (task.priority === 'Medium') {
                priorityBadge = '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Medium</span>';
            }

            let statusBadge = '<span class="badge bg-amber text-dark" style="background:#f59e0b"><i class="bi bi-clock me-1"></i>Pending</span>';
            let actionButtons = `
                <button class="btn btn-outline-primary" data-action="update-task-status" data-task-id="${task.id}" data-status="In Progress"><i class="bi bi-play-fill me-1"></i> Start</button>
                <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Done</button>
            `;

            if (task.status === 'Completed') {
                statusBadge = '<span class="badge bg-success text-white"><i class="bi bi-check-circle me-1"></i>Completed</span>';
                actionButtons = `<span class="badge bg-success-subtle text-success border border-success-subtle py-2 px-2"><i class="bi bi-check2-all me-1"></i>Completed</span>`;
            } else if (task.status === 'In Progress') {
                statusBadge = '<span class="badge bg-primary text-white"><i class="bi bi-hourglass-split me-1"></i>In Progress</span>';
                actionButtons = `
                    <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Complete</button>
                    <button class="btn btn-outline-secondary" data-action="update-task-status" data-task-id="${task.id}" data-status="Pending"><i class="bi bi-pause-fill me-1"></i> Pause</button>
                `;
            } else if (task.status === 'Reopened') {
                statusBadge = '<span class="badge bg-warning text-dark border border-warning-subtle"><i class="bi bi-arrow-counterclockwise me-1"></i>Reopened</span>';
                actionButtons = `
                    <button class="btn btn-outline-primary" data-action="update-task-status" data-task-id="${task.id}" data-status="In Progress"><i class="bi bi-play-fill me-1"></i> Start</button>
                    <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Done</button>
                `;
            }

            const descHtml = task.description ? `<div class="small text-secondary text-truncate" style="max-width:300px;">${escapeHtml(task.description)}</div>` : '';
            const datasetHtml = task.dataset_id ? `
                <div class="mt-2 d-flex flex-wrap align-items-center gap-2">
                    <span class="badge bg-primary-subtle text-primary border border-primary-subtle d-inline-flex align-items-center" style="font-size:0.75rem;">
                        <i class="bi bi-file-earmark-spreadsheet me-1"></i>${escapeHtml(task.dataset_file_name || 'Task Dataset')}
                    </span>
                    <button type="button" class="btn btn-sm btn-primary py-0 px-2 btn-load-task-dataset" data-dataset-id="${task.dataset_id}" data-filename="${escapeHtml(task.dataset_file_name || 'Task Dataset')}" style="font-size:0.75rem; border-radius:4px;">
                        <i class="bi bi-play-circle-fill me-1"></i> Analyze Dataset
                    </button>
                </div>
            ` : '';
            const remarkHtml = task.remark ? `<div class="small mt-1 p-1 px-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle" style="max-width:320px;"><i class="bi bi-chat-left-dots-fill me-1"></i><strong>Manager Remark:</strong> ${escapeHtml(task.remark)}</div>` : '';

            const submitBtnHtml = (task.dataset_id && task.status !== 'Completed') ? `
                <button type="button" class="btn btn-sm btn-success fw-semibold btn-submit-task-direct" data-task-id="${task.id}" data-dataset-id="${task.dataset_id}" data-task-title="${escapeHtml(task.task_title || '')}" data-manager-name="${escapeHtml(task.manager_name || 'Manager')}" data-due-date="${escapeHtml(task.due_date || '')}" title="Submit this work and share dashboard with team">
                    <i class="bi bi-send-check-fill me-1"></i> Submit Work
                </button>
            ` : '';

            return `
                <tr data-task-id="${task.id}">
                    <td>
                        <div class="fw-semibold">${escapeHtml(task.task_title || '')}</div>
                        ${descHtml}
                        ${datasetHtml}
                        ${remarkHtml}
                    </td>
                    <td>
                        <div class="small fw-semibold">${escapeHtml(task.manager_name || 'Management')}</div>
                        <div class="small text-secondary">${escapeHtml(task.manager_email || '')}</div>
                    </td>
                    <td>${priorityBadge}</td>
                    <td class="small">${escapeHtml(task.due_date || 'Flexible')}</td>
                    <td>${statusBadge}</td>
                    <td class="text-end">
                        <div class="d-flex align-items-center justify-content-end gap-1 flex-wrap">
                            ${submitBtnHtml}
                            <div class="btn-group btn-group-sm">
                                ${actionButtons}
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function refreshAnalystTasks() {
        const btn = document.getElementById('refreshAnalystTasksBtn');
        if (btn) btn.classList.add('disabled');
        fetch('/api/user/assigned_tasks')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.tasks) {
                    renderAnalystTasks(data.tasks);
                }
            })
            .catch(err => console.warn('Could not refresh assigned tasks:', err))
            .finally(() => {
                if (btn) btn.classList.remove('disabled');
            });
    }

    // Submit task work click delegation from assigned tasks table
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-submit-task-direct');
        if (!btn) return;
        e.preventDefault();
        const taskId = btn.getAttribute('data-task-id');
        const dsId = btn.getAttribute('data-dataset-id');
        const taskTitle = btn.getAttribute('data-task-title') || 'Assigned Task';
        const mgrName = btn.getAttribute('data-manager-name') || 'Manager';
        const dueDate = btn.getAttribute('data-due-date') || 'No deadline';

        currentActiveTask = {
            id: taskId,
            task_title: taskTitle,
            manager_name: mgrName,
            due_date: dueDate,
            dataset_id: dsId
        };
        if (dsId) {
            activeDatasetId = dsId;
        }

        if (submitTaskModalInstance) {
            submitTaskModalInstance.show();
        } else {
            const modalEl = document.getElementById('submitTaskWorkModal');
            if (modalEl) {
                const instance = new bootstrap.Modal(modalEl);
                instance.show();
            }
        }
    });

    // Status update click delegation
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-action="update-task-status"]');
        if (!btn) return;
        e.preventDefault();
        const taskId = btn.getAttribute('data-task-id');
        const status = btn.getAttribute('data-status');
        if (!taskId || !status) return;

        btn.disabled = true;
        fetch('/api/manager/update_task_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId, status: status })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (typeof showToast === 'function') {
                        showToast(data.message || `Task updated to ${status}.`, "success");
                    }
                    refreshAnalystTasks();
                    if (window.DataNovaStateBus) {
                        if (typeof window.DataNovaStateBus.notify === 'function') {
                            window.DataNovaStateBus.notify('MUTATION_TASK_UPDATE', { task_id: taskId, status: status });
                        } else if (typeof window.DataNovaStateBus.emit === 'function') {
                            window.DataNovaStateBus.emit('MUTATION_TASK_UPDATE', { task_id: taskId, status: status });
                        }
                    }
                } else {
                    if (typeof showToast === 'function') {
                        showToast(data.message || 'Failed to update task status.', "danger");
                    }
                }
            })
            .catch(err => {
                console.error('Error updating task status:', err);
                if (typeof showToast === 'function') {
                    showToast('Network error while updating task.', 'danger');
                }
            })
            .finally(() => {
                btn.disabled = false;
            });
    });

    // Task dataset load & analyze click delegation
    document.addEventListener('click', function (e) {
        const loadBtn = e.target.closest('.btn-load-task-dataset');
        if (!loadBtn) return;
        e.preventDefault();
        const dsId = loadBtn.getAttribute('data-dataset-id');
        const fName = loadBtn.getAttribute('data-filename') || 'Task Dataset';
        if (!dsId) return;

        const origHtml = loadBtn.innerHTML;
        loadBtn.disabled = true;
        loadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Loading...';

        fetch(`/api/load_dataset/${dsId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    populateDatasetWorkspace(data, fName, true);
                    if (typeof showToast === 'function') {
                        showToast(data.message || `Assigned dataset '${fName}' loaded into analysis workspace!`, 'success');
                    }
                    const previewPanel = document.getElementById('dnDataPreviewPanel') || document.getElementById('step-preview') || document.getElementById('dnDatasetStatsGrid');
                    if (previewPanel) {
                        previewPanel.scrollIntoView({ behavior: 'smooth' });
                    }
                } else {
                    if (typeof showToast === 'function') {
                        showToast(data.message || 'Failed to load task dataset.', 'danger');
                    }
                    loadBtn.disabled = false;
                    loadBtn.innerHTML = origHtml;
                }
            })
            .catch(err => {
                console.error('Error loading task dataset:', err);
                if (typeof showToast === 'function') {
                    showToast('Network error while loading task dataset.', 'danger');
                }
                loadBtn.disabled = false;
                loadBtn.innerHTML = origHtml;
            });
    });

    const refreshTasksBtn = document.getElementById('refreshAnalystTasksBtn');
    if (refreshTasksBtn) {
        refreshTasksBtn.addEventListener('click', function (e) {
            e.preventDefault();
            refreshAnalystTasks();
        });
    }

    /* ---------------------------------------------------------------------
       Sidebar Navigation & Smooth Scroll Management
       ------------------------------------------------------------------- */
    const sidebarNavLinks = document.querySelectorAll('#dnAnalystSidebarNav .dn-nav-link');
    sidebarNavLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#') && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    sidebarNavLinks.forEach(l => l.classList.remove('active'));
                    this.classList.add('active');
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    /* ---------------------------------------------------------------------
       Quick Action Buttons Navigation
       ------------------------------------------------------------------- */
    const btnQuickUpload = document.getElementById('btnQuickUpload');
    if (btnQuickUpload) {
        btnQuickUpload.addEventListener('click', function (e) {
            e.preventDefault();
            const uploadSection = document.getElementById('upload');
            if (uploadSection) {
                uploadSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                const fileInp = document.getElementById('dnFileInput');
                if (fileInp) setTimeout(() => fileInp.click(), 400);
            }
        });
    }

    const btnQuickClean = document.getElementById('btnQuickClean');
    if (btnQuickClean) {
        btnQuickClean.addEventListener('click', function (e) {
            e.preventDefault();
            if (!activeDatasetId) {
                showToast('Please upload a dataset first to start cleaning.', 'warning');
                const uploadSection = document.getElementById('upload');
                if (uploadSection) uploadSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            const cleanSection = document.getElementById('step-cleaning');
            if (cleanSection) cleanSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    const btnQuickEDA = document.getElementById('btnQuickEDA');
    if (btnQuickEDA) {
        btnQuickEDA.addEventListener('click', function (e) {
            e.preventDefault();
            if (!activeDatasetId) {
                showToast('Please upload a dataset first to run EDA.', 'warning');
                const uploadSection = document.getElementById('upload');
                if (uploadSection) uploadSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            const edaSection = document.getElementById('step-eda');
            if (edaSection) edaSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            const genBtn = document.getElementById('dnGenerateEDABtn');
            if (genBtn) genBtn.click();
        });
    }

    /* ---------------------------------------------------------------------
       Multilingual Support (i18n) for Analyst Dashboard
       ------------------------------------------------------------------- */
    const I18N_DICTIONARY = {
        en: {
            flowSection: "Data Analysis Flow",
            workloadSection: "Workload & Tasks",
            accountSection: "Account",
            navDashboard: "Dashboard",
            navUpload: "1. Upload Dataset",
            navPreview: "2. Raw Preview",
            navCleaning: "3. Data Cleaning",
            navEDA: "4. Statistical EDA",
            navCorrelation: "5. Correlation Matrix",
            navVisualizations: "6. Visualizations & Charts",
            navInsights: "7. AI Insights & ML",
            navReports: "8. Reports & Export",
            navAskAI: "Ask Your Data",
            navAssignedTasks: "Assigned Work",
            navSharedDashboards: "Shared Dashboards",
            navProfile: "Profile",
            navSettings: "Settings",
            navLogout: "Logout",
            roleAnalyst: "ANALYST ACCESS",

            searchPlaceholder: "Search your datasets...",
            notificationsTitle: "Notifications",

            eyebrowAnalytics: "ANALYTICS WORKSPACE",
            overviewTitle: "Analyst Dashboard",
            overviewSub: "Upload, clean, explore, visualize, and generate executive reports from your datasets.",
            btnPreviousDatasets: "Previous Datasets",
            btnShareDashboard: "Share Dashboard",
            btnExportEDA: "Export Full EDA",
            btnDownloadCleaned: "Download Cleaned Data",
            btnDownloadCSV: "Download as CSV (.csv)",
            btnDownloadExcel: "Download as Excel (.xlsx)",
            btnRollback: "Rollback",
            btnAskAI: "Ask AI",
            btnUploadHeader: "Upload Dataset",

            kpiTotalDatasets: "Total Datasets",
            kpiRowsAnalyzed: "Rows Analyzed",
            kpiDataQuality: "Data Quality",
            kpiMissingValues: "Missing Values",
            kpiDuplicatesFound: "Duplicates Found",
            kpiReportsGenerated: "Reports Generated",

            step1Eyebrow: "STEP 1: DATA INGESTION",
            step1Title: "Upload Dataset",
            uploadPanelTitle: "Select or Drop Dataset File",
            uploadDropText: "Drag and drop your CSV, Excel (.xlsx, .xls), or JSON file here",
            uploadDropSub: "Supports CSV, XLSX, XLS, JSON up to 100MB with automatic delimiter detection",
            btnBrowseFiles: "Browse Files",
            btnQuickDemo: "Start Quick Demo",
            btnRecentDatasets: "Recent Datasets",

            step2Eyebrow: "STEP 2: EXPLORATION",
            step2Title: "Raw Dataset Preview",
            btnProceedCleaning: "Proceed to Cleaning",
            btnRunEDA: "Run EDA Immediately",

            step3Eyebrow: "STEP 3: PRE-PROCESSING",
            step3Title: "Data Quality & Cleaning",
            sub3ATitle: " Missing Values Treatment",
            sub3BTitle: " Duplicate Row Detection",
            sub3CTitle: " Manage & Drop Unwanted Columns",
            btnAutoCleanMissing: "Auto-Clean Missing",
            btnRemoveDuplicates: "Remove Fully Identical Rows",
            btnAutoCleanRecommended: "⚡ Auto-Clean All Recommended",
            btnRemoveSelectedCols: "Remove Selected Columns",

            step4Eyebrow: "STEP 4: SUMMARY STATISTICS",
            step4Title: "Statistical EDA & Summary",
            btnGenerateEDA: "Generate Statistical Summary",

            step5Eyebrow: "STEP 5: RELATIONSHIPS",
            step5Title: "Correlation Heatmap & Analysis",
            btnGenerateCorrelation: "Generate Correlation Matrix",

            step6Eyebrow: "STEP 6: VISUAL ANALYTICS",
            step6Title: "Interactive Visualizations & Chart Builder",
            btnGenerateViz: "Generate Visualization",

            step7Eyebrow: "STEP 7: MACHINE LEARNING & AI",
            step7Title: "Automated ML Insights",
            btnTrainML: "Train ML Model",
            btnGenerateInsights: "Generate AI Insights",

            step8Eyebrow: "STEP 8: EXECUTIVE SUMMARY",
            step8Title: "Executive Report & Data Export",
            btnDownloadPDF: "Download PDF Report",
            btnDownloadHTML: "Download HTML Report",

            assignedTasksTitle: "Assigned Work & Tasks",
            sharedDashboardsTitle: "Shared Dashboards & Team Collaboration",

            settingsModalTitle: "Analyst Preferences & Settings",
            lblTheme: "Workspace Theme",
            optThemeLight: "Light Mode",
            optThemeDark: "Dark Mode",
            optThemeAuto: "Auto / System Default",
            lblChartEngine: "Default Chart Rendering Engine",
            optChart3D: "3D Dynamic & Interactive Charts (Plotly)",
            optChart2D: "2D Standard High-Res Visualizations",
            lblLanguage: "Dashboard & AI Language",
            lblAutoEDA: "Instant dataset analysis reports",
            lblAutoRefresh: "Real-time task auto-sync",
            btnCancel: "Cancel",
            btnSaveSettings: "Save Settings",

            profileModalTitle: "Analyst Profile & Credentials"
        },
        hi: {
            flowSection: "डेटा विश्लेषण प्रक्रिया",
            workloadSection: "कार्य और असाइनमेंट",
            accountSection: "खाता",
            navDashboard: "डैशबोर्ड",
            navUpload: "1. डेटासेट अपलोड करें",
            navPreview: "2. रॉ डेटा पूर्वावलोकन",
            navCleaning: "3. डेटा क्लीनिंग",
            navEDA: "4. सांख्यिकीय EDA",
            navCorrelation: "5. सहसंबंध मैट्रिक्स (Correlation)",
            navVisualizations: "6. विज़ुअलाइज़ेशन और चार्ट्स",
            navInsights: "7. AI इनसाइट्स और ML",
            navReports: "8. रिपोर्ट और निर्यात",
            navAskAI: "डेटा से प्रश्न पूछें",
            navAssignedTasks: "सौंपे गए कार्य",
            navSharedDashboards: "साझा डैशबोर्ड",
            navProfile: "प्रोफ़ाइल",
            navSettings: "सेटिंग्स",
            navLogout: "लॉगआउट",
            roleAnalyst: "विश्लेषक एक्सेस (ANALYST)",

            searchPlaceholder: "अपने डेटासेट खोजें...",
            notificationsTitle: "सूचनाएं",

            eyebrowAnalytics: "एनालिटिक्स वर्कस्पेस",
            overviewTitle: "एनालिस्ट डैशबोर्ड",
            overviewSub: "अपने डेटासेट को अपलोड, साफ़, विश्लेषण, विज़ुअलाइज़ और रिपोर्ट तैयार करें।",
            btnPreviousDatasets: "पिछले डेटासेट",
            btnShareDashboard: "डैशबोर्ड साझा करें",
            btnExportEDA: "पूर्ण EDA निर्यात करें",
            btnDownloadCleaned: "क्लीन्ड डेटा डाउनलोड करें",
            btnDownloadCSV: "CSV (.csv) डाउनलोड करें",
            btnDownloadExcel: "Excel (.xlsx) डाउनलोड करें",
            btnRollback: "वापस लें (Rollback)",
            btnAskAI: "AI से पूछें",
            btnUploadHeader: "डेटासेट अपलोड करें",

            kpiTotalDatasets: "कुल डेटासेट",
            kpiRowsAnalyzed: "विश्लेषण की गई पंक्तियाँ",
            kpiDataQuality: "डेटा गुणवत्ता",
            kpiMissingValues: "मिसिंग वैल्यूज",
            kpiDuplicatesFound: "डुप्लिकेट पंक्तियाँ",
            kpiReportsGenerated: "तैयार की गई रिपोर्ट",

            step1Eyebrow: "चरण 1: डेटा अपलोड",
            step1Title: "डेटासेट अपलोड करें",
            step1Badge: "वर्कफ़्लो चरण 1 / 8",
            uploadPanelTitle: "डेटासेट फ़ाइल चुनें या ड्रैग करें",
            uploadDropText: "अपनी CSV, Excel (.xlsx, .xls), या JSON फ़ाइल यहाँ ड्रैग और ड्रॉप करें",
            uploadDropSub: "स्वचालित पहचान के साथ 100MB तक CSV, XLSX, XLS, JSON समर्थित है",
            btnBrowseFiles: "फ़ाइलें चुनें (Browse)",
            btnQuickDemo: "त्वरित डेमो शुरू करें",
            btnRecentDatasets: "हाल के डेटासेट",

            step2Eyebrow: "चरण 2: डेटा अन्वेषण",
            step2Title: "रॉ डेटा पूर्वावलोकन (Preview)",
            step2Badge: "वर्कफ़्लो चरण 2 / 8",
            btnProceedCleaning: "क्लीनिंग की ओर बढ़ें",
            btnRunEDA: "तुरंत EDA चलाएं",

            step3Eyebrow: "चरण 3: प्री-प्रोसेसिंग",
            step3Title: "डेटा गुणवत्ता और क्लीनिंग",
            step3Badge: "वर्कफ़्लो चरण 3 / 8",
            sub3ATitle: "3A. मिसिंग वैल्यूज का उपचार",
            sub3BTitle: "3B. डुप्लिकेट पंक्तियों की पहचान",
            sub3CTitle: "3C. अवांछित कॉलम हटाएं",
            btnAutoCleanMissing: "मिसिंग वैल्यूज ऑटो-क्लीन करें",
            btnRemoveDuplicates: "समान पंक्तियाँ हटाएं",
            btnAutoCleanRecommended: "⚡ सभी अनुशंसित ऑटो-क्लीन करें",
            btnRemoveSelectedCols: "चुने हुए कॉलम हटाएं",

            step4Eyebrow: "चरण 4: सांख्यिकीय विवरण",
            step4Title: "सांख्यिकीय EDA और सारांश",
            step4Badge: "वर्कफ़्लो चरण 4 / 8",
            btnGenerateEDA: "सांख्यिकीय सारांश तैयार करें",

            step5Eyebrow: "चरण 5: डेटा संबंध",
            step5Title: "सहसंबंध हीटमैप और विश्लेषण",
            step5Badge: "वर्कफ़्लो चरण 5 / 8",
            btnGenerateCorrelation: "सहसंबंध मैट्रिक्स तैयार करें",

            step6Eyebrow: "चरण 6: विज़ुअल एनालिटिक्स",
            step6Title: "इंटरैक्टिव विज़ुअलाइज़ेशन और चार्ट्स",
            step6Badge: "वर्कफ़्लो चरण 6 / 8",
            btnGenerateViz: "विज़ुअलाइज़ेशन बनाएं",

            step7Eyebrow: "चरण 7: मशीन लर्निंग और AI",
            step7Title: "स्वचालित ML और AI इनसाइट्स",
            step7Badge: "वर्कफ़्लो चरण 7 / 8",
            btnTrainML: "ML मॉडल प्रशिक्षित करें",
            btnGenerateInsights: "AI इनसाइट्स जनरेट करें",

            step8Eyebrow: "चरण 8: कार्यकारी सारांश",
            step8Title: "कार्यकारी रिपोर्ट और डेटा निर्यात",
            step8Badge: "वर्कफ़्लो चरण 8 / 8",
            btnDownloadPDF: "PDF रिपोर्ट डाउनलोड करें",
            btnDownloadHTML: "HTML रिपोर्ट डाउनलोड करें",

            assignedTasksTitle: "सौंपे गए कार्य और वर्कलोड",
            sharedDashboardsTitle: "साझा डैशबोर्ड और टीम सहयोग",

            settingsModalTitle: "विश्लेषक प्राथमिकताएं और सेटिंग्स",
            lblTheme: "वर्कस्पेस थीम",
            optThemeLight: "लाइट मोड",
            optThemeDark: "डार्क मोड",
            optThemeAuto: "ऑटो / सिस्टम डिफॉल्ट",
            lblChartEngine: "डिफ़ॉल्ट चार्ट रेंडरिंग इंजन",
            optChart3D: "3D डायनामिक व इंटरैक्टिव चार्ट्स (Plotly)",
            optChart2D: "2D मानक हाई-रेज़ोल्यूशन विज़ुअलाइज़ेशन",
            lblLanguage: "डैशबोर्ड और AI भाषा",
            lblAutoEDA: "डेटासेट अपलोड करने के बाद स्वचालित EDA बनाएं",
            lblAutoRefresh: "असाइन किए गए कार्यों को स्वतः सिंक करें",
            btnCancel: "रद्द करें",
            btnSaveSettings: "सेटिंग्स सहेजें",

            profileModalTitle: "विश्लेषक प्रोफ़ाइल और विवरण"
        },
        mr: {
            flowSection: "डेटा विश्लेषण प्रक्रिया",
            workloadSection: "कामाचे नियोजन व कार्ये",
            accountSection: "खाते",
            navDashboard: "डॅशबोर्ड",
            navUpload: "1. डेटासेट अपलोड करा",
            navPreview: "2. रॉ डेटा पूर्वावलोकन",
            navCleaning: "3. डेटा क्लीनिंग",
            navEDA: "4. सांख्यिकी EDA",
            navCorrelation: "5. सहसंबंध मॅट्रिक्स (Correlation)",
            navVisualizations: "6. व्हिज्युअलायझेशन आणि चार्ट्स",
            navInsights: "7. AI इनसाइट्स आणि ML",
            navReports: "8. रिपोर्ट्स आणि निर्यात",
            navAskAI: "डेटाशी संवाद साधा",
            navAssignedTasks: "दिलेली कार्ये (Assigned Tasks)",
            navSharedDashboards: "शेअर केलेले डॅशबोर्ड",
            navProfile: "प्रोफाइल",
            navSettings: "सेटिंग्ज",
            navLogout: "लॉगआउट",
            roleAnalyst: "विश्लेषक ॲक्सेस (ANALYST)",

            searchPlaceholder: "तुमचे डेटासेट शोधा...",
            notificationsTitle: "सूचना",

            eyebrowAnalytics: "ॲनालिटिक्स वर्कस्पेस",
            overviewTitle: "ॲनालिस्ट डॅशबोर्ड",
            overviewSub: "तुमचे डेटासेट अपलोड, क्लीन, एक्सप्लोर, व्हिज्युअलाइज करा आणि रिपोर्ट तयार करा.",
            btnPreviousDatasets: "मागील डेटासेट",
            btnShareDashboard: "डॅशबोर्ड शेअर करा",
            btnExportEDA: "पूर्ण EDA एक्सपोर्ट करा",
            btnDownloadCleaned: "क्लीन्ड डेटा डाउनलोड करा",
            btnDownloadCSV: "CSV (.csv) डाउनलोड करा",
            btnDownloadExcel: "Excel (.xlsx) डाउनलोड करा",
            btnRollback: "मागे घ्या (Rollback)",
            btnAskAI: "AI ला विचारा",
            btnUploadHeader: "डेटासेट अपलोड करा",

            kpiTotalDatasets: "एकूण डेटासेट",
            kpiRowsAnalyzed: "विश्लेषण केलेल्या ओळी",
            kpiDataQuality: "डेटा गुणवत्ता",
            kpiMissingValues: "मिसिंग व्हॅल्यूज",
            kpiDuplicatesFound: "डुप्लिकेट ओळी",
            kpiReportsGenerated: "तयार केलेले रिपोर्ट्स",

            step1Eyebrow: "टप्पा 1: डेटा अपलोड",
            step1Title: "डेटासेट अपलोड करा",
            step1Badge: "वर्कफ्लो टप्पा 1 / 8",
            uploadPanelTitle: "डेटासेट फाइल निवडा किंवा ड्रॅग करा",
            uploadDropText: "तुमची CSV, Excel (.xlsx, .xls), किंवा JSON फाइल येथे ड्रॅग आणि ड्रॉप करा",
            uploadDropSub: "स्वयंचलित ओळखीसह 100MB पर्यंत CSV, XLSX, XLS, JSON समर्थित",
            btnBrowseFiles: "फाइल निवडा (Browse)",
            btnQuickDemo: "त्वरित डेमो सुरू करा",
            btnRecentDatasets: "अलीकडील डेटासेट",

            step2Eyebrow: "टप्पा 2: डेटा अन्वेषण",
            step2Title: "रॉ डेटा पूर्वावलोकन (Preview)",
            step2Badge: "वर्कफ्लो टप्पा 2 / 8",
            btnProceedCleaning: "क्लीनिंगकडे पुढे जा",
            btnRunEDA: "लगेच EDA चालवा",

            step3Eyebrow: "टप्पा 3: प्री-प्रोसेसिंग",
            step3Title: "डेटा गुणवत्ता आणि क्लीनिंग",
            step3Badge: "वर्कफ्लो टप्पा 3 / 8",
            sub3ATitle: "3A. मिसिंग व्हॅल्यूज दुरुस्ती",
            sub3BTitle: "3B. डुप्लिकेट ओळी शोधणे",
            sub3CTitle: "3C. नको असलेले स्तंभ काढून टाका",
            btnAutoCleanMissing: "मिसिंग व्हॅल्यूज ऑटो-क्लीन करा",
            btnRemoveDuplicates: "समान ओळी काढून टाका",
            btnAutoCleanRecommended: "⚡ सर्व शिफारसी ऑटो-क्लीन करा",
            btnRemoveSelectedCols: "निवडलेले स्तंभ काढून टाका",

            step4Eyebrow: "टप्पा 4: सांख्यिकी माहिती",
            step4Title: "सांख्यिकी EDA आणि सारांश",
            step4Badge: "वर्कफ्लो टप्पा 4 / 8",
            btnGenerateEDA: "सांख्यिकी सारांश तयार करा",

            step5Eyebrow: "टप्पा 5: डेटा संबंध",
            step5Title: "सहसंबंध हीटमॅप आणि विश्लेषण",
            step5Badge: "वर्कफ्लो टप्पा 5 / 8",
            btnGenerateCorrelation: "सहसंबंध मॅट्रिक्स तयार करा",

            step6Eyebrow: "टप्पा 6: व्हिज्युअल ॲनालिटिक्स",
            step6Title: "इंटरॅक्टिव्ह व्हिज्युअलायझेशन आणि चार्ट्स",
            step6Badge: "वर्कफ्लो टप्पा 6 / 8",
            btnGenerateViz: "व्हिज्युअलायझेशन तयार करा",

            step7Eyebrow: "टप्पा 7: मशीन लर्निंग आणि AI",
            step7Title: "स्वयंचलित ML आणि AI इनसाइट्स",
            step7Badge: "वर्कफ्लो टप्पा 7 / 8",
            btnTrainML: "ML मॉडेल प्रशिक्षित करा",
            btnGenerateInsights: "AI इनसाइट्स जनरेट करा",

            step8Eyebrow: "टप्पा 8: मुख्य सारांश",
            step8Title: "कार्यकारी अहवाल आणि डेटा निर्यात",
            step8Badge: "वर्कफ्लो टप्पा 8 / 8",
            btnDownloadPDF: "PDF रिपोर्ट डाउनलोड करा",
            btnDownloadHTML: "HTML रिपोर्ट डाउनलोड करा",

            assignedTasksTitle: "दिलेली कार्ये आणि वर्कलोड",
            sharedDashboardsTitle: "शेअर केलेले डॅशबोर्ड आणि संघ सहयोग",

            settingsModalTitle: "विश्लेषक प्राधान्ये आणि सेटिंग्ज",
            lblTheme: "वर्कस्पेस थीम",
            optThemeLight: "लाइट मोड",
            optThemeDark: "डार्क मोड",
            optThemeAuto: "ऑटो / सिस्टम डिफॉल्ट",
            lblChartEngine: "डिफॉल्ट चार्ट रेंडरिंग इंजिन",
            optChart3D: "3D डायनॅमिक व इंटरॅक्टिव्ह चार्ट्स (Plotly)",
            optChart2D: "2D मानक हाय-रिझोल्यूशन व्हिज्युअलायझेशन",
            lblLanguage: "डॅशबोर्ड आणि AI भाषा",
            lblAutoEDA: "डेटासेट अपलोड केल्यानंतर आपोआप EDA तयार करा",
            lblAutoRefresh: "दिलेल्या कार्यांचे अपडेट आपोआप सिंक करा",
            btnCancel: "रद्द करा",
            btnSaveSettings: "सेटिंग्ज जतन करा",

            profileModalTitle: "विश्लेषक प्रोफाइल आणि तपशील"
        }
    };

    window.applyDashboardLanguage = function (lang) {
        if (!lang || !I18N_DICTIONARY[lang]) {
            lang = 'en';
        }
        const dict = I18N_DICTIONARY[lang];

        // 1. Sidebar Section Labels
        const sectionLabels = document.querySelectorAll('#dnAnalystSidebarNav .dn-nav-section-label');
        if (sectionLabels && sectionLabels.length >= 3) {
            sectionLabels[0].textContent = dict.flowSection;
            sectionLabels[1].textContent = dict.workloadSection;
            sectionLabels[2].textContent = dict.accountSection;
        }

        // 2. Sidebar Navigation Links
        const setLink = (id, iconClass, text, badgeHtml = '') => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = `<i class="${iconClass}"></i> ${text}${badgeHtml ? ' ' + badgeHtml : ''}`;
            }
        };

        const taskBadgeEl = document.getElementById('analystAssignedTasksBadge');
        const taskCount = taskBadgeEl ? taskBadgeEl.textContent.trim() : '0';
        const sharedBadgeEl = document.getElementById('analystSharedBadge');
        const sharedCount = sharedBadgeEl ? sharedBadgeEl.textContent.trim() : '0';
        const sharedDisplay = sharedBadgeEl && sharedBadgeEl.style.display === 'none' ? 'style="display:none;"' : '';

        setLink('navAnalystDashboard', 'bi bi-grid-1x2-fill', dict.navDashboard);
        setLink('navUploadDataset', 'bi bi-cloud-upload', dict.navUpload);
        setLink('navRawPreview', 'bi bi-database', dict.navPreview);
        setLink('navDataCleaning', 'bi bi-shield-check', dict.navCleaning);
        setLink('navStatisticalEDA', 'bi bi-search', dict.navEDA);
        setLink('navCorrelationMatrix', 'bi bi-grid-3x3', dict.navCorrelation);
        setLink('navVisualizations', 'bi bi-bar-chart-line', dict.navVisualizations);
        setLink('navAIInsights', 'bi bi-stars', dict.navInsights);
        setLink('navReportsExport', 'bi bi-file-earmark-bar-graph', dict.navReports);
        setLink('navAskYourData', 'bi bi-chat-dots', dict.navAskAI);
        setLink('navAssignedTasks', 'bi bi-check2-square', dict.navAssignedTasks, `<span class="badge rounded-pill bg-primary ms-auto" id="analystAssignedTasksBadge">${taskCount}</span>`);
        setLink('navSharedDashboards', 'bi bi-share', dict.navSharedDashboards, `<span class="badge rounded-pill bg-info ms-auto" id="analystSharedBadge" ${sharedDisplay}>${sharedCount}</span>`);
        setLink('navAnalystProfile', 'bi bi-person', dict.navProfile);
        setLink('navAnalystSettings', 'bi bi-gear', dict.navSettings);

        // Sidebar Footer Role Pill
        const rolePill = document.querySelector('.dn-sidebar-footer .dn-role-pill');
        if (rolePill) rolePill.innerHTML = `<i class="bi bi-clipboard-data"></i> ${dict.roleAnalyst}`;

        // 3. Topbar
        const searchInput = document.querySelector('.dn-topbar-search input');
        if (searchInput) searchInput.setAttribute('placeholder', dict.searchPlaceholder);

        const notifHeader = document.querySelector('.dn-dropdown-header-custom strong');
        if (notifHeader) notifHeader.textContent = dict.notificationsTitle;

        // 4. Main Overview Header
        const eyebrowOverview = document.querySelector('#main-overview .dn-eyebrow');
        if (eyebrowOverview) eyebrowOverview.innerHTML = `<i class="bi bi-clipboard-data"></i> ${dict.eyebrowAnalytics}`;

        const titleOverview = document.querySelector('#main-overview .dn-page-title');
        if (titleOverview) titleOverview.textContent = dict.overviewTitle;

        const subOverview = document.querySelector('#main-overview .dn-page-sub');
        if (subOverview) subOverview.textContent = dict.overviewSub;

        // Overview Header Buttons
        const prevBtn = document.getElementById('btnHeaderViewPrevious');
        if (prevBtn) prevBtn.innerHTML = `<i class="bi bi-clock-history me-1"></i> ${dict.btnPreviousDatasets}`;

        const shareBtn = document.getElementById('btnShareDashboard');
        if (shareBtn) shareBtn.innerHTML = `<i class="bi bi-share-fill me-1"></i> ${dict.btnShareDashboard}`;

        const exportBtn = document.getElementById('dnExportReportBtn');
        if (exportBtn) exportBtn.innerHTML = `<i class="bi bi-file-earmark-pdf-fill me-1"></i> ${dict.btnExportEDA}`;

        const downloadCleanedBtn = document.querySelector('#dnDownloadCleanedDropdown > button');
        if (downloadCleanedBtn) downloadCleanedBtn.innerHTML = `<i class="bi bi-download me-1"></i> ${dict.btnDownloadCleaned}`;

        const csvDl = document.getElementById('dnDownloadCleanedCSV');
        if (csvDl) csvDl.innerHTML = `<i class="bi bi-filetype-csv text-success me-2"></i> ${dict.btnDownloadCSV}`;

        const excelDl = document.getElementById('dnDownloadCleanedExcel');
        if (excelDl) excelDl.innerHTML = `<i class="bi bi-file-earmark-excel text-primary me-2"></i> ${dict.btnDownloadExcel}`;

        const rollbackBtn = document.getElementById('dnRollbackDatasetBtn');
        if (rollbackBtn) rollbackBtn.innerHTML = `<i class="bi bi-arrow-counterclockwise me-1"></i> ${dict.btnRollback}`;

        const askAiHeaderBtns = document.querySelectorAll('#main-overview .dn-open-ask-modal');
        askAiHeaderBtns.forEach(btn => {
            btn.innerHTML = `<i class="bi bi-chat-dots me-1"></i> ${dict.btnAskAI}`;
        });

        const uploadHeaderBtn = document.querySelector('#main-overview a[href="#upload"]');
        if (uploadHeaderBtn) uploadHeaderBtn.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> ${dict.btnUploadHeader}`;

        // 5. KPI Labels
        const kpiLabels = document.querySelectorAll('.dn-kpi-card .dn-kpi-label');
        if (kpiLabels && kpiLabels.length >= 6) {
            kpiLabels[0].textContent = dict.kpiTotalDatasets;
            kpiLabels[1].textContent = dict.kpiRowsAnalyzed;
            kpiLabels[2].textContent = dict.kpiDataQuality;
            kpiLabels[3].textContent = dict.kpiMissingValues;
            kpiLabels[4].textContent = dict.kpiDuplicatesFound;
            kpiLabels[5].textContent = dict.kpiReportsGenerated;
        }

        // 6. Step 1: Upload Dataset
        const step1 = document.getElementById('upload');
        if (step1) {
            const eb = step1.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> ${dict.step1Eyebrow}`;
            const h2 = step1.querySelector('h2');
            if (h2) h2.textContent = dict.step1Title;
            const badge = step1.querySelector('.badge');
            if (badge) badge.textContent = dict.step1Badge;

            const dzTitle = document.querySelector('#dnDropzone h3');
            if (dzTitle) dzTitle.innerHTML = `<i class="bi bi-cloud-arrow-up text-primary me-2"></i>${dict.uploadPanelTitle}`;
            const dzText = document.querySelector('#dnDropzone .dn-dropzone-text');
            if (dzText) dzText.textContent = dict.uploadDropText;
            const dzSub = document.querySelector('#dnDropzone .dn-dropzone-sub');
            if (dzSub) dzSub.textContent = dict.uploadDropSub;

            const selectBtn = document.getElementById('dnSelectFilesBtn');
            if (selectBtn) selectBtn.innerHTML = `<i class="bi bi-folder2-open me-2"></i>${dict.btnBrowseFiles}`;
            const demoBtn = document.getElementById('dnQuickDemoBtn');
            if (demoBtn) demoBtn.innerHTML = `<i class="bi bi-lightning-charge me-1"></i> ${dict.btnQuickDemo}`;
            const recentBtn = document.getElementById('dnRecentDatasetsBtn');
            if (recentBtn) recentBtn.innerHTML = `<i class="bi bi-clock-history me-1"></i> ${dict.btnRecentDatasets}`;
        }

        // 7. Step 2: Raw Preview
        const step2 = document.getElementById('step-preview');
        if (step2) {
            const eb = step2.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-database me-1"></i> ${dict.step2Eyebrow}`;
            const h2 = step2.querySelector('h2');
            if (h2) h2.textContent = dict.step2Title;
            const badge = step2.querySelector('.badge');
            if (badge) badge.textContent = dict.step2Badge;

            const proceedBtn = document.getElementById('dnProceedToCleaningBtn');
            if (proceedBtn) proceedBtn.innerHTML = `<i class="bi bi-arrow-right-circle me-1"></i> ${dict.btnProceedCleaning}`;
            const runEdaBtn = document.getElementById('dnRunEdaNowBtn');
            if (runEdaBtn) runEdaBtn.innerHTML = `<i class="bi bi-play-circle me-1"></i> ${dict.btnRunEDA}`;
        }

        // 8. Step 3: Data Cleaning
        const step3 = document.getElementById('step-cleaning');
        if (step3) {
            const eb = step3.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-shield-check me-1"></i> ${dict.step3Eyebrow}`;
            const h2 = step3.querySelector('h2');
            if (h2) h2.textContent = dict.step3Title;
            const badge = step3.querySelector('.badge');
            if (badge) badge.textContent = dict.step3Badge;

            const sub3A = document.querySelector('#dnMissingValuesPanel .dn-panel-title');
            if (sub3A) sub3A.innerHTML = `<i class="bi bi-question-diamond"></i> ${dict.sub3ATitle}`;
            const sub3B = document.querySelector('#dnDuplicateRowsPanel .dn-panel-title');
            if (sub3B) sub3B.innerHTML = `<i class="bi bi-files"></i> ${dict.sub3BTitle}`;
            const sub3C = document.querySelector('#dnDropColumnsPanel .dn-panel-title');
            if (sub3C) sub3C.innerHTML = `<i class="bi bi-trash3 text-danger me-2"></i>${dict.sub3CTitle}`;

            const autoCleanBtn = document.getElementById('dnAutoCleanMissingBtn');
            if (autoCleanBtn) autoCleanBtn.innerHTML = `<i class="bi bi-magic me-1"></i> ${dict.btnAutoCleanMissing}`;
            const removeDupBtn = document.getElementById('dnRemoveFullDuplicatesBtn');
            if (removeDupBtn) removeDupBtn.innerHTML = `<i class="bi bi-trash"></i> ${dict.btnRemoveDuplicates}`;
            const dropColsBtn = document.getElementById('dnConfirmDropColumnsBtn');
            if (dropColsBtn) dropColsBtn.innerHTML = `<i class="bi bi-trash me-1"></i> ${dict.btnRemoveSelectedCols}`;
        }

        // 9. Step 4: EDA
        const step4 = document.getElementById('step-eda');
        if (step4) {
            const eb = step4.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-search me-1"></i> ${dict.step4Eyebrow}`;
            const h2 = step4.querySelector('h2');
            if (h2) h2.textContent = dict.step4Title;
            const badge = step4.querySelector('.badge');
            if (badge) badge.textContent = dict.step4Badge;

            const genEdaBtn = document.getElementById('dnGenerateEDABtn');
            if (genEdaBtn) genEdaBtn.innerHTML = `<i class="bi bi-bar-chart-steps me-1"></i> ${dict.btnGenerateEDA}`;
        }

        // 10. Step 5: Correlation Matrix
        const step5 = document.getElementById('step-correlation');
        if (step5) {
            const eb = step5.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-grid-3x3 me-1"></i> ${dict.step5Eyebrow}`;
            const h2 = step5.querySelector('h2');
            if (h2) h2.textContent = dict.step5Title;
            const badge = step5.querySelector('.badge');
            if (badge) badge.textContent = dict.step5Badge;

            const genCorrBtn = document.getElementById('dnGenerateCorrelationBtn');
            if (genCorrBtn) genCorrBtn.innerHTML = `<i class="bi bi-play-fill me-1"></i> ${dict.btnGenerateCorrelation}`;
        }

        // 11. Step 6: Visualizations & Charts
        const step6 = document.getElementById('step-visualization');
        if (step6) {
            const eb = step6.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-bar-chart-line me-1"></i> ${dict.step6Eyebrow}`;
            const h2 = step6.querySelector('h2');
            if (h2) h2.textContent = dict.step6Title;
            const badge = step6.querySelector('.badge');
            if (badge) badge.textContent = dict.step6Badge;

            const genVizBtn = document.getElementById('dnGenerateChartBtn');
            if (genVizBtn) genVizBtn.innerHTML = `<i class="bi bi-palette me-1"></i> ${dict.btnGenerateViz}`;
        }

        // 12. Step 7: AI Insights & ML
        const step7 = document.getElementById('step-insights');
        if (step7) {
            const eb = step7.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-stars me-1"></i> ${dict.step7Eyebrow}`;
            const h2 = step7.querySelector('h2');
            if (h2) h2.textContent = dict.step7Title;
            const badge = step7.querySelector('.badge');
            if (badge) badge.textContent = dict.step7Badge;

            const trainBtn = document.getElementById('dnTrainMLBtn');
            if (trainBtn) trainBtn.innerHTML = `<i class="bi bi-cpu me-1"></i> ${dict.btnTrainML}`;
            const genInsightsBtn = document.getElementById('dnGenerateInsightsBtn');
            if (genInsightsBtn) genInsightsBtn.innerHTML = `<i class="bi bi-stars me-1"></i> ${dict.btnGenerateInsights}`;
        }

        // 13. Step 8: Reports & Export
        const step8 = document.getElementById('step-reports');
        if (step8) {
            const eb = step8.querySelector('.dn-eyebrow');
            if (eb) eb.innerHTML = `<i class="bi bi-file-earmark-bar-graph me-1"></i> ${dict.step8Eyebrow}`;
            const h2 = step8.querySelector('h2');
            if (h2) h2.textContent = dict.step8Title;
            const badge = step8.querySelector('.badge');
            if (badge) badge.textContent = dict.step8Badge;

            const pdfBtn = document.getElementById('dnDownloadPdfReportBtn');
            if (pdfBtn) pdfBtn.innerHTML = `<i class="bi bi-file-earmark-pdf me-1"></i> ${dict.btnDownloadPDF}`;
            const htmlBtn = document.getElementById('dnDownloadHtmlReportBtn');
            if (htmlBtn) htmlBtn.innerHTML = `<i class="bi bi-file-earmark-code me-1"></i> ${dict.btnDownloadHTML}`;
        }

        // 14. Workload & Shared Panels
        const assignedHeader = document.querySelector('#assignedTasksPanel .dn-panel-title');
        if (assignedHeader) assignedHeader.innerHTML = `<i class="bi bi-check2-square text-primary me-2"></i>${dict.assignedTasksTitle}`;

        const sharedHeader = document.querySelector('#sharedDashboardsPanel .dn-panel-title');
        if (sharedHeader) sharedHeader.innerHTML = `<i class="bi bi-share text-primary me-2"></i>${dict.sharedDashboardsTitle}`;

        // 15. Settings Modal
        const settingsTitle = document.getElementById('analystSettingsModalLabel');
        if (settingsTitle) settingsTitle.innerHTML = `<i class="bi bi-gear-wide-connected text-primary me-2"></i>${dict.settingsModalTitle}`;

        const lblTheme = document.getElementById('lblPrefTheme');
        if (lblTheme) lblTheme.textContent = dict.lblTheme;
        const optLight = document.getElementById('optPrefThemeLight');
        if (optLight) optLight.textContent = dict.optThemeLight;
        const optDark = document.getElementById('optPrefThemeDark');
        if (optDark) optDark.textContent = dict.optThemeDark;
        const optAuto = document.getElementById('optPrefThemeSystem');
        if (optAuto) optAuto.textContent = dict.optThemeAuto;

        const lblChart = document.getElementById('lblPrefChart');
        if (lblChart) lblChart.textContent = dict.lblChartEngine;
        const opt3D = document.getElementById('optPrefChart3D');
        if (opt3D) opt3D.textContent = dict.optChart3D;
        const opt2D = document.getElementById('optPrefChart2D');
        if (opt2D) opt2D.textContent = dict.optChart2D;

        const lblLang = document.getElementById('lblPrefAILang');
        if (lblLang) lblLang.textContent = dict.lblLanguage;

        const lblAutoEda = document.getElementById('lblPrefAutoEda');
        if (lblAutoEda) lblAutoEda.textContent = dict.lblAutoEDA;

        const lblAutoRef = document.getElementById('lblPrefAutoRefresh');
        if (lblAutoRef) lblAutoRef.textContent = dict.lblAutoRefresh;

        const cancelPrefBtn = document.getElementById('btnCancelAnalystPref');
        if (cancelPrefBtn) cancelPrefBtn.textContent = dict.btnCancel;

        const savePrefBtn = document.getElementById('btnSaveAnalystPref');
        if (savePrefBtn) savePrefBtn.innerHTML = `<i class="bi bi-check2-circle me-1"></i>${dict.btnSaveSettings}`;

        // 16. Profile Modal Title
        const profModalTitle = document.getElementById('analystProfileModalLabel');
        if (profModalTitle) profModalTitle.innerHTML = `<i class="bi bi-person-badge text-primary me-2"></i>${dict.profileModalTitle}`;

        // Sync Select Values
        const prefLangSelect = document.getElementById('prefAILangSelect');
        if (prefLangSelect && prefLangSelect.value !== lang) {
            prefLangSelect.value = lang;
        }
        const askLangSelect = document.getElementById('dnAskLanguage');
        if (askLangSelect && askLangSelect.value !== lang) {
            askLangSelect.value = lang;
        }

        // Store language
        localStorage.setItem('datanova_analyst_lang', lang);
    };

    /* ---------------------------------------------------------------------
       Analyst Preferences & Settings
       ------------------------------------------------------------------- */
    window.saveAnalystPreferences = function () {
        const theme = document.getElementById('prefThemeSelect')?.value || 'system';
        const chartType = document.getElementById('prefChartTypeSelect')?.value || 'interactive_3d';
        const aiLang = document.getElementById('prefAILangSelect')?.value || 'en';
        const autoEda = document.getElementById('prefAutoEdaToggle')?.checked ?? true;
        const autoRefresh = document.getElementById('prefAutoRefreshTasksToggle')?.checked ?? true;

        const prefs = { theme, chartType, aiLang, autoEda, autoRefresh };
        localStorage.setItem('datanova_analyst_prefs', JSON.stringify(prefs));
        localStorage.setItem('datanova_analyst_lang', aiLang);

        // Apply language immediately across dashboard
        if (typeof applyDashboardLanguage === 'function') {
            applyDashboardLanguage(aiLang);
        }

        // Apply chart engine preference immediately to EDA charts
        if (typeof renderEdaCharts === 'function' && window.cachedEdaCharts && window.cachedEdaCharts.length > 0) {
            renderEdaCharts(window.cachedEdaCharts, chartType);
        }

        // Apply theme immediately
        if (theme === 'dark' || theme === 'light') {
            document.documentElement.setAttribute('data-bs-theme', theme);
            localStorage.setItem('theme', theme);
        } else {
            const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-bs-theme', systemPrefersDark ? 'dark' : 'light');
            localStorage.removeItem('theme');
        }

        // Close modal
        const modalEl = document.getElementById('analystSettingsModal');
        if (modalEl && window.bootstrap) {
            const modalInstance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            modalInstance.hide();
        }

        const msg = aiLang === 'hi' ? 'सेटिंग्स सफलतापूर्वक सहेजी गईं!' : (aiLang === 'mr' ? 'सेटिंग्ज यशस्वीरित्या सेव्ह झाल्या!' : 'Settings saved successfully!');
        showToast(msg, 'success');
    };

    function loadAnalystPreferences() {
        try {
            let activeLang = localStorage.getItem('datanova_analyst_lang') || 'en';
            let activeChartType = 'interactive_3d';
            const raw = localStorage.getItem('datanova_analyst_prefs');
            if (raw) {
                const prefs = JSON.parse(raw);
                if (document.getElementById('prefThemeSelect') && prefs.theme) {
                    document.getElementById('prefThemeSelect').value = prefs.theme;
                }
                if (document.getElementById('prefChartTypeSelect') && prefs.chartType) {
                    document.getElementById('prefChartTypeSelect').value = prefs.chartType;
                    activeChartType = prefs.chartType;
                }
                if (prefs.aiLang) {
                    activeLang = prefs.aiLang;
                }
                if (document.getElementById('prefAutoEdaToggle') && typeof prefs.autoEda === 'boolean') {
                    document.getElementById('prefAutoEdaToggle').checked = prefs.autoEda;
                }
                if (document.getElementById('prefAutoRefreshTasksToggle') && typeof prefs.autoRefresh === 'boolean') {
                    document.getElementById('prefAutoRefreshTasksToggle').checked = prefs.autoRefresh;
                }
            }

            if (document.getElementById('prefAILangSelect')) {
                document.getElementById('prefAILangSelect').value = activeLang;
            }
            if (document.getElementById('dnAskLanguage')) {
                document.getElementById('dnAskLanguage').value = activeLang;
            }

            // Apply loaded language to entire UI
            applyDashboardLanguage(activeLang);

            // Add change listener to immediate reactive language switch
            const langSelect = document.getElementById('prefAILangSelect');
            if (langSelect && !langSelect.dataset.listenerBound) {
                langSelect.dataset.listenerBound = 'true';
                langSelect.addEventListener('change', function (e) {
                    applyDashboardLanguage(e.target.value);
                });
            }

            // Add change listener to immediate reactive 2D/3D chart switch
            const chartSelect = document.getElementById('prefChartTypeSelect');
            if (chartSelect && !chartSelect.dataset.listenerBound) {
                chartSelect.dataset.listenerBound = 'true';
                chartSelect.addEventListener('change', function (e) {
                    if (typeof renderEdaCharts === 'function' && window.cachedEdaCharts && window.cachedEdaCharts.length > 0) {
                        renderEdaCharts(window.cachedEdaCharts, e.target.value);
                    }
                });
            }
        } catch (e) {
            console.warn('Could not load analyst preferences:', e);
        }
    }
    loadAnalystPreferences();
    loadCurrentDataset();

    /* ---------------------------------------------------------------------
       Clear Cache & Session Management (Profile Modal)
       ------------------------------------------------------------------- */
    function clearAnalystCacheAndSession() {
        const btn = document.getElementById('btnAnalystClearCacheSession');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clearing Cache &amp; Session...';
        }

        fetch('/api/clear_analyst_cache_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(res => res.json())
        .then(data => {
            // Clear local storage items related to dataset and pipeline state
            localStorage.removeItem('datanova_active_dataset_id');
            localStorage.removeItem('datanova_active_dataset_filename');
            localStorage.removeItem('datanova_active_dataset_rows');
            localStorage.removeItem('datanova_active_dataset_cols');

            // Clear session storage
            try { sessionStorage.clear(); } catch (e) {}

            // Purge Plotly WebGL instances from DOM
            if (window.Plotly) {
                document.querySelectorAll('.dn-eda-plot > div[id^="dnPlotlyChart_"]').forEach(node => {
                    try { Plotly.purge(node); } catch (e) {}
                });
            }

            // Clear in-memory caches
            window.cachedEdaCharts = [];
            window.activeDatasetId = null;

            showToast(data.message || 'Project cache and active session cleared successfully!', 'success');

            // Close Profile Modal
            const profileModalEl = document.getElementById('analystProfileModal');
            if (profileModalEl && window.bootstrap) {
                const modalInstance = bootstrap.Modal.getInstance(profileModalEl);
                if (modalInstance) modalInstance.hide();
            }

            // Refresh view smoothly
            setTimeout(() => {
                window.location.reload();
            }, 750);
        })
        .catch(err => {
            console.error('Failed to clear cache & session:', err);
            localStorage.removeItem('datanova_active_dataset_id');
            localStorage.removeItem('datanova_active_dataset_filename');
            try { sessionStorage.clear(); } catch (e) {}
            showToast('Local cache cleared successfully.', 'info');
            setTimeout(() => {
                window.location.reload();
            }, 750);
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i> Clear Cache &amp; Session';
            }
        });
    }
    window.clearAnalystCacheAndSession = clearAnalystCacheAndSession;

    const clearCacheBtn = document.getElementById('btnAnalystClearCacheSession');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', clearAnalystCacheAndSession);
    }

    /* ---------------------------------------------------------------------
       Keyboard Shortcuts
       ------------------------------------------------------------------- */
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            if (typeof openAskModal === 'function') {
                openAskModal(e);
            }
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
            e.preventDefault();
            const uploadSection = document.getElementById('upload');
            if (uploadSection) {
                uploadSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                const fileInp = document.getElementById('dnFileInput');
                if (fileInp) fileInp.click();
            }
        }
    });

    /* ---------------------------------------------------------------------
       Previous Datasets Modal & Loader Manager
       ------------------------------------------------------------------- */
    let cachedPreviousDatasets = [];
    const prevModalEl = document.getElementById('previousDatasetsModal');
    const prevListContainer = document.getElementById('previousDatasetsListContainer');
    const prevLoading = document.getElementById('previousDatasetsLoading');
    const searchPrevInput = document.getElementById('searchPreviousDatasetsInput');
    const refreshPrevBtn = document.getElementById('refreshPreviousDatasetsBtn');
    const prevCountText = document.getElementById('previousDatasetsCountText');

    function fetchPreviousDatasets() {
        if (!prevListContainer) return;
        if (prevLoading) prevLoading.style.display = 'block';
        prevListContainer.innerHTML = '';

        fetch('/api/previous_datasets')
            .then(res => res.json())
            .then(data => {
                if (data.success && Array.isArray(data.datasets)) {
                    cachedPreviousDatasets = data.datasets;
                    renderPreviousDatasets(cachedPreviousDatasets);
                    if (prevCountText) {
                        prevCountText.textContent = `${data.datasets.length} dataset${data.datasets.length === 1 ? '' : 's'} available`;
                    }
                } else {
                    prevListContainer.innerHTML = `
                        <div class="text-center py-4 text-muted">
                            <i class="bi bi-exclamation-triangle fs-3 text-warning mb-2 d-block"></i>
                            <div>Failed to load previous datasets.</div>
                            <small>${data.message || 'Please try again.'}</small>
                        </div>
                    `;
                }
            })
            .catch(err => {
                console.error('Error fetching previous datasets:', err);
                if (prevListContainer) {
                    prevListContainer.innerHTML = `
                        <div class="text-center py-4 text-muted">
                            <i class="bi bi-wifi-off fs-3 text-danger mb-2 d-block"></i>
                            <div>Network error fetching previous datasets.</div>
                        </div>
                    `;
                }
            })
            .finally(() => {
                if (prevLoading) prevLoading.style.display = 'none';
            });
    }

    function renderPreviousDatasets(datasets) {
        if (!prevListContainer) return;
        if (!datasets || datasets.length === 0) {
            prevListContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="dn-avatar mx-auto mb-3" style="width:54px;height:54px;background:rgba(99,102,241,0.1);color:var(--dn-primary);display:flex;align-items:center;justify-content:center;border-radius:50%;">
                        <i class="bi bi-folder-x fs-4"></i>
                    </div>
                    <h6 class="fw-semibold mb-1">No Previous Datasets Found</h6>
                    <p class="text-secondary small mb-3">Upload a CSV or Excel dataset to begin your data analysis journey.</p>
                    <button class="btn btn-sm dn-btn-primary" data-bs-dismiss="modal" onclick="document.getElementById('upload')?.scrollIntoView({behavior:'smooth'}); setTimeout(()=>document.getElementById('dnFileInput')?.click(), 400);">
                        <i class="bi bi-cloud-upload me-1"></i> Upload Dataset Now
                    </button>
                </div>
            `;
            return;
        }

        const itemsHtml = datasets.map(ds => {
            const isActive = activeDatasetId && String(activeDatasetId) === String(ds.id);
            return `
                <div class="dn-dataset-card p-3 mb-2 rounded border bg-body-tertiary d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2 ${isActive ? 'border-primary shadow-sm' : ''}">
                    <div class="d-flex align-items-start gap-3">
                        <span class="dn-kpi-icon flex-shrink-0" style="background:${isActive ? 'var(--dn-primary)' : 'rgba(99,102,241,0.12)'};color:${isActive ? '#fff' : 'var(--dn-primary)'};width:42px;height:42px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;">
                            <i class="bi bi-file-earmark-spreadsheet"></i>
                        </span>
                        <div>
                            <div class="d-flex align-items-center gap-2 flex-wrap">
                                <span class="fw-bold">${ds.file_name}</span>
                                ${isActive ? '<span class="badge bg-primary text-white"><i class="bi bi-check2 me-1"></i>Active Now</span>' : ''}
                            </div>
                            <div class="d-flex align-items-center gap-3 mt-1 small text-secondary flex-wrap">
                                <span><i class="bi bi-calendar3 me-1"></i>${ds.uploaded_at}</span>
                                <span><i class="bi bi-hdd me-1"></i>${ds.file_size}</span>
                                <span><i class="bi bi-list-ol me-1"></i>${Number(ds.row_count).toLocaleString()} rows</span>
                                <span><i class="bi bi-layout-three-columns me-1"></i>${ds.column_count} cols</span>
                            </div>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2 w-100 w-md-auto justify-content-end mt-2 mt-md-0">
                        <button class="btn btn-sm ${isActive ? 'btn-outline-primary' : 'dn-btn-primary'} btn-load-prev-dataset" data-dataset-id="${ds.id}" data-filename="${ds.file_name}">
                            <i class="bi ${isActive ? 'bi-arrow-clockwise' : 'bi-box-arrow-in-down-right'} me-1"></i> ${isActive ? 'Reload' : 'Load Dataset'}
                        </button>
                        <button class="btn btn-sm btn-outline-danger btn-delete-prev-dataset" data-dataset-id="${ds.id}" data-filename="${ds.file_name}" title="Delete Dataset">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        prevListContainer.innerHTML = itemsHtml;

        // Attach Load Handlers
        prevListContainer.querySelectorAll('.btn-load-prev-dataset').forEach(btn => {
            btn.addEventListener('click', function () {
                const dsId = this.getAttribute('data-dataset-id');
                const fName = this.getAttribute('data-filename');
                if (!dsId) return;

                const origHtml = this.innerHTML;
                this.disabled = true;
                this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Loading...';

                fetch(`/api/load_dataset/${dsId}`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            if (prevModalEl && window.bootstrap) {
                                const modalInst = bootstrap.Modal.getInstance(prevModalEl);
                                if (modalInst) modalInst.hide();
                            }
                            populateDatasetWorkspace(data, fName, true);
                            showToast(data.message || `Dataset '${fName}' loaded successfully!`, 'success');
                        } else {
                            showToast(data.message || 'Failed to load dataset.', 'danger');
                            this.disabled = false;
                            this.innerHTML = origHtml;
                        }
                    })
                    .catch(err => {
                        console.error('Error loading dataset:', err);
                        showToast('Network error while loading dataset.', 'danger');
                        this.disabled = false;
                        this.innerHTML = origHtml;
                    });
            });
        });

        // Attach Delete Handlers
        prevListContainer.querySelectorAll('.btn-delete-prev-dataset').forEach(btn => {
            btn.addEventListener('click', function () {
                const dsId = this.getAttribute('data-dataset-id');
                const fName = this.getAttribute('data-filename');
                if (!dsId) return;

                if (!confirm(`Are you sure you want to delete dataset "${fName}"? This action cannot be undone.`)) {
                    return;
                }

                this.disabled = true;
                fetch(`/api/delete_dataset/${dsId}`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast(`Dataset "${fName}" deleted successfully.`, 'success');
                            if (String(activeDatasetId) === String(dsId)) {
                                activeDatasetId = null;
                                location.reload();
                            } else {
                                fetchPreviousDatasets();
                            }
                        } else {
                            showToast(data.message || 'Failed to delete dataset.', 'danger');
                            this.disabled = false;
                        }
                    })
                    .catch(err => {
                        console.error('Error deleting dataset:', err);
                        showToast('Error deleting dataset.', 'danger');
                        this.disabled = false;
                    });
            });
        });
    }

    if (searchPrevInput) {
        searchPrevInput.addEventListener('input', function (e) {
            const query = e.target.value.toLowerCase().trim();
            if (!query) {
                renderPreviousDatasets(cachedPreviousDatasets);
                return;
            }
            const filtered = cachedPreviousDatasets.filter(ds =>
                (ds.file_name && ds.file_name.toLowerCase().includes(query)) ||
                (ds.uploaded_at && ds.uploaded_at.toLowerCase().includes(query))
            );
            renderPreviousDatasets(filtered);
        });
    }

    if (refreshPrevBtn) {
        refreshPrevBtn.addEventListener('click', function () {
            fetchPreviousDatasets();
        });
    }

    if (prevModalEl) {
        prevModalEl.addEventListener('show.bs.modal', function () {
            if (searchPrevInput) searchPrevInput.value = '';
            fetchPreviousDatasets();
        });
    }

    /* ---------------------------------------------------------------------
       17. Share Active Dashboard & Collaborative Review
       ------------------------------------------------------------------- */
    const shareModalEl = document.getElementById('shareDashboardModal');
    let shareModalInstance = null;
    if (shareModalEl) {
        shareModalInstance = new bootstrap.Modal(shareModalEl);
    }
    const teamMembersContainer = document.getElementById('teamMembersChecklistContainer');
    const selectAllTeamCheckbox = document.getElementById('selectAllTeamMembers');
    const shareDashboardForm = document.getElementById('shareDashboardForm');
    const shareTitleInput = document.getElementById('shareDashboardTitle');
    const shareDescInput = document.getElementById('shareDashboardDesc');
    const shareModalSubtitle = document.getElementById('shareModalDatasetSubtitle');

    let cachedTeamMembers = [];

    function fetchTeamMembersForSharing() {
        if (!teamMembersContainer) return;
        teamMembersContainer.innerHTML = `
            <div class="text-center py-3 text-secondary small">
                <div class="spinner-border spinner-border-sm text-primary" role="status"></div> Loading team members...
            </div>`;
        fetch('/api/team_members_for_sharing')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.members) {
                    cachedTeamMembers = data.members;
                    renderTeamMembersChecklist(cachedTeamMembers);
                } else {
                    teamMembersContainer.innerHTML = `<div class="text-danger small p-2">${escapeHtml(data.message || 'Failed to load team members.')}</div>`;
                }
            })
            .catch(err => {
                console.error('Error fetching team members:', err);
                teamMembersContainer.innerHTML = `<div class="text-danger small p-2">Error loading team members.</div>`;
            });
    }

    function renderTeamMembersChecklist(members) {
        if (!teamMembersContainer) return;
        if (!members || members.length === 0) {
            teamMembersContainer.innerHTML = `<div class="text-muted small p-3 text-center"><i class="bi bi-people me-1"></i>No team members found in your manager's team roster.</div>`;
            return;
        }

        teamMembersContainer.innerHTML = members.map(m => {
            let roleBadge = '<span class="badge bg-secondary">Developer</span>';
            if (m.raw_role === 'manager') roleBadge = '<span class="badge bg-primary">Manager</span>';
            else if (m.raw_role === 'analyst') roleBadge = '<span class="badge bg-info text-dark">Analyst</span>';
            else if (m.raw_role === 'admin') roleBadge = '<span class="badge bg-danger">Admin</span>';

            return `
                <div class="d-flex align-items-center justify-content-between p-2 px-3 mb-1 border rounded bg-body shadow-sm" style="transition: background 0.15s ease;">
                    <div class="d-flex align-items-center gap-2 m-0 p-0" style="min-height: auto;">
                        <input class="form-check-input m-0 dn-team-member-chk" type="checkbox" value="${m.id}" id="teamMemberChk_${m.id}" style="float: none; width: 1.15rem; height: 1.15rem; cursor: pointer;" checked>
                        <label class="form-check-label small fw-semibold text-body ms-2 mb-0" for="teamMemberChk_${m.id}" style="cursor: pointer; user-select: none;">
                            ${escapeHtml(m.name)}
                            <span class="text-secondary fw-normal d-block" style="font-size:0.75rem;">${escapeHtml(m.email)}</span>
                        </label>
                    </div>
                    <div>${roleBadge}</div>
                </div>
            `;
        }).join('');

        if (selectAllTeamCheckbox) {
            selectAllTeamCheckbox.checked = true;
        }

        // Attach individual change listener to update Select All state
        teamMembersContainer.querySelectorAll('.dn-team-member-chk').forEach(chk => {
            chk.addEventListener('change', function () {
                const allChks = teamMembersContainer.querySelectorAll('.dn-team-member-chk');
                const checkedCount = teamMembersContainer.querySelectorAll('.dn-team-member-chk:checked').length;
                if (selectAllTeamCheckbox) {
                    selectAllTeamCheckbox.checked = (checkedCount === allChks.length);
                    selectAllTeamCheckbox.indeterminate = (checkedCount > 0 && checkedCount < allChks.length);
                }
            });
        });
    }

    if (selectAllTeamCheckbox) {
        selectAllTeamCheckbox.addEventListener('change', function () {
            const isChecked = this.checked;
            if (teamMembersContainer) {
                teamMembersContainer.querySelectorAll('.dn-team-member-chk').forEach(chk => {
                    chk.checked = isChecked;
                });
            }
        });
    }

    // When opening share modal
    if (shareModalEl) {
        shareModalEl.addEventListener('show.bs.modal', function (e) {
            if (!activeDatasetId) {
                showToast("Please upload or select an active dataset first to share.", "warning");
            }
            if (shareModalSubtitle) {
                const activeMeta = document.getElementById('dnActiveDatasetMeta');
                const fileName = activeMeta ? activeMeta.textContent : `Dataset #${activeDatasetId || ''}`;
                shareModalSubtitle.textContent = `Sharing: ${fileName}`;
            }
            fetchTeamMembersForSharing();
        });
    }

    // Share Form Submit Handler
    if (shareDashboardForm) {
        shareDashboardForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!activeDatasetId) {
                showToast("Please select or upload a dataset before sharing.", "danger");
                return;
            }

            const title = shareTitleInput ? shareTitleInput.value.trim() : '';
            const description = shareDescInput ? shareDescInput.value.trim() : '';

            if (!title) {
                showToast("Please enter a title for the shared dashboard.", "warning");
                return;
            }

            const selectedMemberIds = [];
            if (teamMembersContainer) {
                teamMembersContainer.querySelectorAll('.dn-team-member-chk:checked').forEach(chk => {
                    selectedMemberIds.push(parseInt(chk.value));
                });
            }

            if (selectedMemberIds.length === 0) {
                showToast("Please select at least one team member to share with.", "warning");
                return;
            }

            const submitBtn = document.getElementById('btnSubmitShareDashboard');
            const origHtml = submitBtn ? submitBtn.innerHTML : 'Share Dashboard';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Sharing...';
            }

            fetch('/api/share_dashboard_with_team', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    title: title,
                    description: description,
                    user_ids: selectedMemberIds
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || "Dashboard shared successfully.", "success");
                        if (shareDashboardForm) shareDashboardForm.reset();
                        if (shareModalInstance) shareModalInstance.hide();
                        fetchAnalystSharedDashboards();
                        if (window.DataNovaStateBus) {
                            if (typeof window.DataNovaStateBus.notify === 'function') {
                                window.DataNovaStateBus.notify('MUTATION_DASHBOARD_SHARED', { dataset_id: activeDatasetId });
                            }
                        }
                    } else {
                        showToast(data.message || "Failed to share dashboard.", "danger");
                    }
                })
                .catch(err => {
                    console.error("Error sharing dashboard:", err);
                    showToast("Network error while sharing dashboard.", "danger");
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = origHtml;
                    }
                });
        });
    }

    /* ---------------------------------------------------------------------
       17.1. Submit Assigned Task Work & Share with Team
       ------------------------------------------------------------------- */
    const submitTaskModalEl = document.getElementById('submitTaskWorkModal');
    let submitTaskModalInstance = null;
    if (submitTaskModalEl) {
        submitTaskModalInstance = new bootstrap.Modal(submitTaskModalEl);
    }
    const submitTeamMembersContainer = document.getElementById('submitTeamMembersChecklistContainer');
    const selectAllSubmitTeamCheckbox = document.getElementById('selectAllSubmitTeamMembers');
    const submitTaskWorkForm = document.getElementById('submitTaskWorkForm');
    const submitTaskWorkTitle = document.getElementById('submitTaskWorkTitle');
    const submitTaskWorkNotes = document.getElementById('submitTaskWorkNotes');
    const submitWorkTaskId = document.getElementById('submitWorkTaskId');
    const submitModalTaskTitle = document.getElementById('submitModalTaskTitle');
    const submitModalTaskMeta = document.getElementById('submitModalTaskMeta');

    function renderSubmitTeamMembersChecklist(members) {
        if (!submitTeamMembersContainer) return;
        if (!members || members.length === 0) {
            submitTeamMembersContainer.innerHTML = `<div class="text-muted small p-3 text-center"><i class="bi bi-people me-1"></i>No team members found in your manager's team roster.</div>`;
            return;
        }

        submitTeamMembersContainer.innerHTML = members.map(m => {
            let roleBadge = '<span class="badge bg-secondary">Developer</span>';
            if (m.raw_role === 'manager') roleBadge = '<span class="badge bg-primary">Manager</span>';
            else if (m.raw_role === 'analyst') roleBadge = '<span class="badge bg-info text-dark">Analyst</span>';
            else if (m.raw_role === 'admin') roleBadge = '<span class="badge bg-danger">Admin</span>';

            return `
                <div class="d-flex align-items-center justify-content-between p-2 px-3 mb-1 border rounded bg-body shadow-sm" style="transition: background 0.15s ease;">
                    <div class="d-flex align-items-center gap-2 m-0 p-0" style="min-height: auto;">
                        <input class="form-check-input m-0 dn-submit-team-member-chk" type="checkbox" value="${m.id}" id="submitTeamMemberChk_${m.id}" style="float: none; width: 1.15rem; height: 1.15rem; cursor: pointer;" checked>
                        <label class="form-check-label small fw-semibold text-body ms-2 mb-0" for="submitTeamMemberChk_${m.id}" style="cursor: pointer; user-select: none;">
                            ${escapeHtml(m.name)}
                            <span class="text-secondary fw-normal d-block" style="font-size:0.75rem;">${escapeHtml(m.email)}</span>
                        </label>
                    </div>
                    <div>${roleBadge}</div>
                </div>
            `;
        }).join('');

        if (selectAllSubmitTeamCheckbox) {
            selectAllSubmitTeamCheckbox.checked = true;
        }

        submitTeamMembersContainer.querySelectorAll('.dn-submit-team-member-chk').forEach(chk => {
            chk.addEventListener('change', function () {
                const allChks = submitTeamMembersContainer.querySelectorAll('.dn-submit-team-member-chk');
                const checkedCount = submitTeamMembersContainer.querySelectorAll('.dn-submit-team-member-chk:checked').length;
                if (selectAllSubmitTeamCheckbox) {
                    selectAllSubmitTeamCheckbox.checked = (checkedCount === allChks.length);
                    selectAllSubmitTeamCheckbox.indeterminate = (checkedCount > 0 && checkedCount < allChks.length);
                }
            });
        });
    }

    if (selectAllSubmitTeamCheckbox) {
        selectAllSubmitTeamCheckbox.addEventListener('change', function () {
            const isChecked = this.checked;
            if (submitTeamMembersContainer) {
                submitTeamMembersContainer.querySelectorAll('.dn-submit-team-member-chk').forEach(chk => {
                    chk.checked = isChecked;
                });
            }
        });
    }

    if (submitTaskModalEl) {
        submitTaskModalEl.addEventListener('show.bs.modal', function () {
            if (currentActiveTask) {
                if (submitWorkTaskId) submitWorkTaskId.value = currentActiveTask.id || '';
                if (submitModalTaskTitle) submitModalTaskTitle.textContent = currentActiveTask.task_title || 'Assigned Task';
                if (submitModalTaskMeta) submitModalTaskMeta.textContent = `Assigned by ${currentActiveTask.manager_name || 'Manager'} • Due: ${currentActiveTask.due_date || 'No deadline'}`;
                if (submitTaskWorkTitle && !submitTaskWorkTitle.value) {
                    submitTaskWorkTitle.value = `Analysis: ${currentActiveTask.task_title || 'Assigned Work'}`;
                }
            } else {
                if (submitModalTaskTitle) submitModalTaskTitle.textContent = `Dataset #${activeDatasetId || ''}`;
                if (submitModalTaskMeta) submitModalTaskMeta.textContent = 'Active analysis dataset';
                if (submitTaskWorkTitle && !submitTaskWorkTitle.value) {
                    submitTaskWorkTitle.value = `Completed Dataset Analysis #${activeDatasetId || ''}`;
                }
            }

            if (submitTeamMembersContainer) {
                submitTeamMembersContainer.innerHTML = `
                    <div class="text-center py-3 text-secondary small">
                        <div class="spinner-border spinner-border-sm text-primary" role="status"></div> Loading team members...
                    </div>`;
            }
            fetch('/api/team_members_for_sharing')
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.members) {
                        cachedTeamMembers = data.members;
                        renderSubmitTeamMembersChecklist(cachedTeamMembers);
                    } else {
                        if (submitTeamMembersContainer) {
                            submitTeamMembersContainer.innerHTML = `<div class="text-danger small p-2">${escapeHtml(data.message || 'Failed to load team members.')}</div>`;
                        }
                    }
                })
                .catch(err => {
                    console.error('Error fetching team members:', err);
                    if (submitTeamMembersContainer) {
                        submitTeamMembersContainer.innerHTML = `<div class="text-danger small p-2">Error loading team members.</div>`;
                    }
                });
        });
    }

    if (submitTaskWorkForm) {
        submitTaskWorkForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!activeDatasetId) {
                showToast("Please select or load an active dataset first.", "warning");
                return;
            }

            const title = submitTaskWorkTitle ? submitTaskWorkTitle.value.trim() : '';
            const notes = submitTaskWorkNotes ? submitTaskWorkNotes.value.trim() : '';
            const taskId = submitWorkTaskId ? submitWorkTaskId.value : (currentActiveTask ? currentActiveTask.id : null);

            if (!title) {
                showToast("Please enter a submission title.", "warning");
                return;
            }

            const selectedMemberIds = [];
            if (submitTeamMembersContainer) {
                submitTeamMembersContainer.querySelectorAll('.dn-submit-team-member-chk:checked').forEach(chk => {
                    selectedMemberIds.push(parseInt(chk.value));
                });
            }

            const submitBtn = document.getElementById('btnSubmitTaskWorkAction');
            const origHtml = submitBtn ? submitBtn.innerHTML : 'Submit Work & Share Dashboard';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Submitting...';
            }

            fetch('/api/analyst/submit_task_work', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    task_id: taskId,
                    title: title,
                    description: notes,
                    user_ids: selectedMemberIds
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || "Work submitted and dashboard shared with the team successfully.", "success");
                        if (submitTaskWorkForm) submitTaskWorkForm.reset();
                        if (submitTaskModalInstance) submitTaskModalInstance.hide();

                        currentActiveTask = null;

                        // Refresh tasks and shared dashboards
                        if (typeof refreshAnalystTasks === 'function') refreshAnalystTasks();
                        if (typeof fetchAnalystSharedDashboards === 'function') fetchAnalystSharedDashboards();

                        if (window.DataNovaStateBus && typeof window.DataNovaStateBus.notify === 'function') {
                            window.DataNovaStateBus.notify('MUTATION_TASK_COMPLETED', { dataset_id: activeDatasetId, task_id: taskId });
                            window.DataNovaStateBus.notify('MUTATION_DASHBOARD_SHARED', { dataset_id: activeDatasetId });
                        }
                    } else {
                        showToast(data.message || "Failed to submit work.", "danger");
                    }
                })
                .catch(err => {
                    console.error("Error submitting task work:", err);
                    showToast("Network error while submitting work.", "danger");
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = origHtml;
                    }
                });
        });
    }

    // --- Shared Dashboards List & Developer Detail Modal ---
    const sharedDetailModalEl = document.getElementById('sharedDashboardDetailModal');
    let sharedDetailModalInstance = null;
    if (sharedDetailModalEl) {
        sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
    }

    function fetchAnalystSharedDashboards() {
        const loadingEl = document.getElementById('analystSharedLoading');
        const container = document.getElementById('analystSharedCardsContainer');
        const badge = document.getElementById('analystSharedBadge');

        if (loadingEl) loadingEl.style.display = 'block';

        fetch('/api/shared_dashboards/list')
            .then(res => res.json())
            .then(data => {
                if (loadingEl) loadingEl.style.display = 'none';
                if (data.success && data.dashboards) {
                    if (badge) {
                        badge.textContent = data.dashboards.length;
                        badge.style.display = data.dashboards.length > 0 ? 'inline-block' : 'none';
                    }
                    renderAnalystSharedDashboards(data.dashboards);
                } else {
                    if (container) {
                        container.innerHTML = `<div class="col-12"><div class="alert alert-warning">${escapeHtml(data.message || 'Could not load shared dashboards.')}</div></div>`;
                    }
                }
            })
            .catch(err => {
                if (loadingEl) loadingEl.style.display = 'none';
                console.error('Error fetching shared dashboards:', err);
            });
    }

    function renderAnalystSharedDashboards(dashboards) {
        const container = document.getElementById('analystSharedCardsContainer');
        if (!container) return;

        if (!dashboards || dashboards.length === 0) {
            container.innerHTML = `
                <div class="col-12">
                    <div class="p-4 text-center text-secondary border rounded bg-body-tertiary">
                        <i class="bi bi-share fs-2 mb-2 d-block text-muted"></i>
                        <div class="fw-medium">No shared dashboards yet</div>
                        <small>Click "Share Active Dataset" to share analytical findings with your team.</small>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = dashboards.map(sd => {
            let statusBadge = '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">Shared</span>';
            if (sd.status === 'Approved') {
                statusBadge = '<span class="badge bg-success text-white"><i class="bi bi-check-circle me-1"></i>Approved</span>';
            } else if (sd.status === 'Reopened') {
                statusBadge = '<span class="badge bg-warning text-dark"><i class="bi bi-arrow-counterclockwise me-1"></i>Reopened for Revision</span>';
            } else if (sd.status === 'Reviewed') {
                statusBadge = '<span class="badge bg-info text-white"><i class="bi bi-chat-left-text me-1"></i>Reviewed</span>';
            }

            const remarkHtml = sd.remark ? `
                <div class="small mt-2 p-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle">
                    <i class="bi bi-chat-left-quote-fill me-1"></i><strong>Manager Feedback:</strong> ${escapeHtml(sd.remark)}
                </div>
            ` : '';

            // Render recipient user badges
            let recipientsHtml = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle extra-small">All Team Members</span>';
            if (sd.shared_with_users && sd.shared_with_users.length > 0) {
                recipientsHtml = sd.shared_with_users.map(u => {
                    return `<span class="badge bg-primary-subtle text-primary border border-primary-subtle extra-small" title="${escapeHtml(u.email || '')}">${escapeHtml(u.name)} (${escapeHtml(u.role || 'User')})</span>`;
                }).join(' ');
            }

            return `
                <div class="col-md-6 col-lg-4">
                    <div class="dn-kpi-card h-100 d-flex flex-column justify-content-between p-3 border rounded shadow-sm">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="fw-bold mb-0 text-truncate" title="${escapeHtml(sd.title)}">${escapeHtml(sd.title)}</h6>
                                ${statusBadge}
                            </div>
                            <div class="small text-secondary mb-1"><i class="bi bi-person me-1"></i>Owner: <strong>${escapeHtml(sd.owner_name)}</strong> (${escapeHtml(sd.owner_role)})</div>
                            <div class="small text-secondary mb-2"><i class="bi bi-database me-1"></i>${escapeHtml(sd.dataset_name)} &bull; ${sd.row_count.toLocaleString()} rows</div>
                            
                            <!-- Recipient Users List -->
                            <div class="small mb-2 p-2 rounded bg-body-tertiary border">
                                <span class="text-secondary d-block fw-semibold mb-1" style="font-size:0.75rem;"><i class="bi bi-people-fill text-primary me-1"></i>Shared With:</span>
                                <div class="d-flex flex-wrap gap-1">${recipientsHtml}</div>
                            </div>

                            ${sd.description ? `<p class="small text-muted mb-2 text-truncate" style="max-height:40px;">${escapeHtml(sd.description)}</p>` : ''}
                            ${remarkHtml}
                        </div>
                        <div class="pt-3 mt-2 border-top d-flex justify-content-between align-items-center">
                            <small class="text-secondary">${escapeHtml(sd.created_at_str)}</small>
                            <button class="btn btn-sm dn-btn-primary btn-view-shared-dashboard" data-shared-id="${sd.id}">
                                <i class="bi bi-eye me-1"></i> View Full Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach View Handlers
        container.querySelectorAll('.btn-view-shared-dashboard').forEach(btn => {
            btn.addEventListener('click', function () {
                const sharedId = this.getAttribute('data-shared-id');
                if (sharedId) {
                    openSharedDashboardDetail(sharedId);
                }
            });
        });
    }

    const _sharedDashboardDetailCache = new Map();

    function openSharedDashboardDetail(sharedId, forceReload = false) {
        if (!sharedDetailModalInstance && sharedDetailModalEl) {
            sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
        }

        const cacheKey = 'dn_shared_dash_' + sharedId;

        // 1. Fast in-memory cache check
        if (!forceReload && _sharedDashboardDetailCache.has(sharedId)) {
            renderSharedDashboardDetailData(_sharedDashboardDetailCache.get(sharedId));
            if (sharedDetailModalInstance) sharedDetailModalInstance.show();
            return;
        }

        // 2. Fast sessionStorage cache check
        if (!forceReload) {
            try {
                const sessionCached = sessionStorage.getItem(cacheKey);
                if (sessionCached) {
                    const parsed = JSON.parse(sessionCached);
                    if (parsed && parsed.success && parsed.dashboard) {
                        _sharedDashboardDetailCache.set(sharedId, parsed.dashboard);
                        renderSharedDashboardDetailData(parsed.dashboard);
                        if (sharedDetailModalInstance) sharedDetailModalInstance.show();
                        return;
                    }
                }
            } catch (e) {}
        }

        if (sharedDetailModalInstance) sharedDetailModalInstance.show();

        // Fetch shared details from API
        fetch(`/api/shared_dashboard/view/${sharedId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.dashboard) {
                    _sharedDashboardDetailCache.set(sharedId, data.dashboard);
                    try {
                        sessionStorage.setItem(cacheKey, JSON.stringify(data));
                    } catch (e) {}
                    renderSharedDashboardDetailData(data.dashboard);
                }
            })
            .catch(err => {
                console.error('Error fetching shared dashboard:', err);
                showToast('Failed to load shared dashboard details.', 'danger');
            });
    }

    function renderSharedDashboardDetailData(sd) {

                    const titleEl = document.getElementById('sharedDetailTitle');
                    const metaEl = document.getElementById('sharedDetailMeta');
                    const statusBadge = document.getElementById('sharedDetailStatusBadge');
                    const domainBadge = document.getElementById('sharedDetailDomainBadge');
                    const descContainer = document.getElementById('sharedDetailDescContainer');
                    const descText = document.getElementById('sharedDetailDescText');
                    const remarkBanner = document.getElementById('sharedDetailRemarkBanner');
                    const remarkText = document.getElementById('sharedDetailRemarkText');
                    const fileText = document.getElementById('sharedDetailDatasetFile');

                    if (titleEl) titleEl.textContent = sd.title;
                    if (metaEl) metaEl.textContent = `Shared by ${sd.owner_name} (${sd.owner_role}) • ${sd.created_at_str}`;
                    if (fileText) fileText.textContent = `Dataset: ${sd.dataset_name}`;
                    if (domainBadge) domainBadge.textContent = sd.business_domain || 'General Analytics';

                    if (statusBadge) {
                        statusBadge.textContent = sd.status;
                        statusBadge.className = 'badge ' + (sd.status === 'Approved' ? 'bg-success' : sd.status === 'Reopened' ? 'bg-warning text-dark' : 'bg-primary');
                    }

                    // Populate Recipients in modal
                    const recListEl = document.getElementById('sharedDetailRecipientsList');
                    if (recListEl) {
                        if (sd.shared_with_users && sd.shared_with_users.length > 0) {
                            recListEl.innerHTML = sd.shared_with_users.map(u => `
                                <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1">
                                    <i class="bi bi-person-fill me-1"></i>${escapeHtml(u.name)} <small class="opacity-75">(${escapeHtml(u.role || 'User')})</small>
                                </span>
                            `).join('');
                        } else {
                            recListEl.innerHTML = '<span class="badge bg-secondary-subtle text-secondary">All Team Members</span>';
                        }
                    }

                    if (descContainer && descText) {
                        if (sd.description) {
                            descContainer.style.display = 'flex';
                            descText.textContent = sd.description;
                        } else {
                            descContainer.style.display = 'none';
                        }
                    }

                    if (remarkBanner && remarkText) {
                        if (sd.remark) {
                            remarkBanner.style.display = 'flex';
                            remarkText.textContent = sd.remark;
                        } else {
                            remarkBanner.style.display = 'none';
                        }
                    }

                    // 1. Overview KPIs
                    const rEl = document.getElementById('sdKpiRows');
                    const cEl = document.getElementById('sdKpiCols');
                    const mEl = document.getElementById('sdKpiMemory');
                    const qEl = document.getElementById('sdKpiQuality');
                    const miEl = document.getElementById('sdKpiMissing');
                    const dEl = document.getElementById('sdKpiDuplicates');

                    if (rEl) rEl.textContent = Number(sd.row_count || 0).toLocaleString();
                    if (cEl) cEl.textContent = Number(sd.column_count || 0).toLocaleString();
                    if (mEl) mEl.textContent = sd.memory_usage || '0 KB';
                    if (qEl) qEl.textContent = `${sd.quality_score || 100}% (${sd.quality_grade || 'A+'})`;
                    if (miEl) miEl.textContent = Number(sd.missing_count || 0).toLocaleString();
                    if (dEl) dEl.textContent = Number(sd.duplicate_count || 0).toLocaleString();

                    // Executive Summary & Quick Action Highlights
                    const execSumEl = document.getElementById('sdExecSummaryText');
                    if (execSumEl) {
                        execSumEl.textContent = sd.ai_explanation?.executive_summary || 'Comprehensive end-to-end analytics pipeline executed across all dataset attributes.';
                    }

                    const hlListEl = document.getElementById('sdQuickHighlightsList');
                    if (hlListEl) {
                        const hl = [];
                        hl.push(`<strong>Data Scale:</strong> Verified <strong>${Number(sd.row_count || 0).toLocaleString()} rows</strong> across <strong>${sd.column_count || 0} features</strong> in domain <em>${escapeHtml(sd.business_domain || 'General')}</em>.`);
                        hl.push(`<strong>Data Hygiene:</strong> Quality grade <strong>${sd.quality_grade || 'A+'}</strong> (${sd.quality_score || 100}/100) with <strong>${sd.duplicates_removed || 0} duplicates removed</strong>.`);
                        if (sd.imputation_details && sd.imputation_details.length > 0) {
                            hl.push(`<strong>Imputation:</strong> Successfully resolved null values across <strong>${sd.imputation_details.length} columns</strong>.`);
                        }
                        if (sd.dropped_columns && sd.dropped_columns.length > 0) {
                            hl.push(`<strong>Feature Optimization:</strong> Isolated <strong>${sd.dropped_columns.length} low-variance / redundant columns</strong>.`);
                        }
                        hlListEl.innerHTML = hl.map(x => `<li class="mb-1">${x}</li>`).join('');
                    }

                    // 2. Charts Showcase & Correlations
                    const topCorrsSection = document.getElementById('sdTopCorrsSection');
                    const posList = document.getElementById('sdTopPositiveList');
                    const negList = document.getElementById('sdTopNegativeList');
                    if (topCorrsSection && posList && negList) {
                        const hasPos = sd.top_positive_corrs && sd.top_positive_corrs.length > 0;
                        const hasNeg = sd.top_negative_corrs && sd.top_negative_corrs.length > 0;
                        if (hasPos || hasNeg) {
                            posList.innerHTML = (sd.top_positive_corrs || []).map(p => `
                                <li class="list-group-item d-flex justify-content-between align-items-center py-1 px-2 bg-transparent">
                                    <span>${escapeHtml(p.var1)} &harr; ${escapeHtml(p.var2)}</span>
                                    <span class="badge bg-success-subtle text-success border border-success-subtle">+${Number(p.correlation).toFixed(2)}</span>
                                </li>
                            `).join('') || '<li class="list-group-item text-muted py-1 px-2 bg-transparent">No strong positive pairs</li>';

                            negList.innerHTML = (sd.top_negative_corrs || []).map(p => `
                                <li class="list-group-item d-flex justify-content-between align-items-center py-1 px-2 bg-transparent">
                                    <span>${escapeHtml(p.var1)} &harr; ${escapeHtml(p.var2)}</span>
                                    <span class="badge bg-danger-subtle text-danger border border-danger-subtle">${Number(p.correlation).toFixed(2)}</span>
                                </li>
                            `).join('') || '<li class="list-group-item text-muted py-1 px-2 bg-transparent">No strong negative pairs</li>';
                            topCorrsSection.style.display = 'block';
                        } else {
                            topCorrsSection.style.display = 'none';
                        }
                    }

                    const chartsGrid = document.getElementById('sdChartsGridContainer');
                    if (chartsGrid) {
                        if (sd.charts_showcase && sd.charts_showcase.length > 0) {
                            chartsGrid.innerHTML = sd.charts_showcase.map(c => `
                                <div class="col-md-6">
                                    <div class="border rounded p-3 bg-body-tertiary h-100 d-flex flex-column justify-content-between">
                                        <div>
                                            <h6 class="fw-bold mb-1 text-primary">${escapeHtml(c.title || 'Analytical Visualization')}</h6>
                                            <p class="small text-muted mb-2">${escapeHtml(c.description || '')}</p>
                                        </div>
                                        <div class="text-center my-auto">
                                            <img src="data:image/png;base64,${c.plot}" alt="${escapeHtml(c.title || 'Chart')}" class="img-fluid rounded border bg-white shadow-sm" style="max-height: 280px; width: 100%; object-fit: contain;">
                                        </div>
                                    </div>
                                </div>
                            `).join('');
                        } else {
                            chartsGrid.innerHTML = '<div class="col-12"><div class="alert alert-info small mb-0">Visualizations are being rendered for this dataset.</div></div>';
                        }
                    }

                    // 3. Cleaning Audit Trail
                    const droppedTbody = document.getElementById('sdDroppedColsTbody');
                    if (droppedTbody) {
                        if (sd.dropped_columns && sd.dropped_columns.length > 0) {
                            droppedTbody.innerHTML = sd.dropped_columns.map(dc => `
                                <tr>
                                    <td class="fw-semibold text-danger">${escapeHtml(dc.column)}</td>
                                    <td><span class="badge bg-secondary-subtle text-secondary">${escapeHtml(dc.type)}</span></td>
                                    <td class="small text-muted">${escapeHtml(dc.reason)}</td>
                                    <td><span class="badge bg-danger-subtle text-danger border border-danger-subtle">${escapeHtml(dc.status)}</span></td>
                                </tr>
                            `).join('');
                        } else {
                            droppedTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted small py-3"><i class="bi bi-check-circle-fill text-success me-1"></i> No columns were dropped. All features were retained.</td></tr>';
                        }
                    }

                    const impTbody = document.getElementById('sdImputationTbody');
                    if (impTbody) {
                        if (sd.imputation_details && sd.imputation_details.length > 0) {
                            impTbody.innerHTML = sd.imputation_details.map(imp => `
                                <tr>
                                    <td class="fw-semibold text-primary">${escapeHtml(imp.column)}</td>
                                    <td class="text-danger fw-bold">${Number(imp.missing_count || 0).toLocaleString()}</td>
                                    <td><span class="badge bg-warning-subtle text-warning-emphasis">${imp.missing_percentage}%</span></td>
                                    <td class="small">${escapeHtml(imp.strategy)}</td>
                                    <td class="small fw-semibold text-dark">${escapeHtml(imp.replacement_value)}</td>
                                    <td><span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check2 me-1"></i>${escapeHtml(imp.status)}</span></td>
                                </tr>
                            `).join('');
                        } else {
                            impTbody.innerHTML = '<tr><td colspan="6" class="text-center text-success small py-3"><i class="bi bi-check-circle-fill me-1"></i> 0 missing values detected in dataset. No imputation needed.</td></tr>';
                        }
                    }

                    // 4. AI Insights & Strategic Recommendations
                    const findingsEl = document.getElementById('sdAiFindingsList');
                    if (findingsEl) {
                        const findings = sd.ai_explanation?.key_findings || sd.ai_explanation?.patterns || [];
                        if (findings.length > 0) {
                            findingsEl.innerHTML = `<ul class="mb-0 ps-3">${findings.map(f => `<li class="mb-1">${escapeHtml(f)}</li>`).join('')}</ul>`;
                        } else {
                            findingsEl.innerHTML = '<span class="text-muted">Dataset features demonstrate high integrity with consistent distributions across categories.</span>';
                        }
                    }

                    const recEl = document.getElementById('sdAiRecommendationsList');
                    if (recEl) {
                        const recs = sd.ai_explanation?.recommendations || [];
                        if (recs.length > 0) {
                            recEl.innerHTML = `<ul class="mb-0 ps-3">${recs.map(r => `<li class="mb-1">${escapeHtml(r)}</li>`).join('')}</ul>`;
                        } else {
                            recEl.innerHTML = '<span class="text-muted">Maintain current operational tracking and monitor high-volume categorical segments.</span>';
                        }
                    }

                    // 5. Dataset Q&A / FAQs (5+)
                    const qaAccordion = document.getElementById('sdQaAccordion');
                    if (qaAccordion) {
                        if (sd.dataset_qa && sd.dataset_qa.length > 0) {
                            qaAccordion.innerHTML = sd.dataset_qa.map((qa, idx) => `
                                <div class="accordion-item mb-2 border rounded overflow-hidden shadow-sm">
                                    <h2 class="accordion-header" id="sdQaHead${idx}">
                                        <button class="accordion-button ${idx === 0 ? '' : 'collapsed'} py-2 px-3 fw-semibold small bg-body-tertiary" type="button" data-bs-toggle="collapse" data-bs-target="#sdQaCollapse${idx}" aria-expanded="${idx === 0 ? 'true' : 'false'}" aria-controls="sdQaCollapse${idx}">
                                            <i class="bi ${qa.icon || 'bi-patch-question-fill'} text-primary me-2"></i>
                                            <span class="badge bg-secondary-subtle text-secondary me-2 extra-small">${escapeHtml(qa.category || 'Analysis')}</span>
                                            <span>${escapeHtml(qa.question)}</span>
                                        </button>
                                    </h2>
                                    <div id="sdQaCollapse${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" aria-labelledby="sdQaHead${idx}" data-bs-parent="#sdQaAccordion">
                                        <div class="accordion-body small bg-white text-secondary py-3 px-3 border-top" style="line-height: 1.6;">
                                            ${qa.answer}
                                        </div>
                                    </div>
                                </div>
                            `).join('');
                        } else {
                            qaAccordion.innerHTML = '<div class="alert alert-info small mb-0">Dataset Q&A analysis available.</div>';
                        }
                    }

                    // 6. Preview Table
                    const prevContainer = document.getElementById('sharedDetailPreviewContainer');
                    if (prevContainer) {
                        prevContainer.innerHTML = sd.preview_html || '<div class="p-3 text-muted">No preview table available.</div>';
                    }

                    // 7. Python Pipeline Code
                    const sdCodeContainer = document.getElementById('sdPipelineCodeContainer');
                    if (sdCodeContainer) {
                        sdCodeContainer.textContent = sd.pipeline_code || '# Pipeline code is generating for this shared dataset...';
                    }

                    // Copy code button in shared modal
                    const btnCopySdCode = document.getElementById('btnCopySdCodeSnippet');
                    if (btnCopySdCode && !btnCopySdCode._hasListener) {
                        btnCopySdCode._hasListener = true;
                        btnCopySdCode.addEventListener('click', function () {
                            const codeText = sdCodeContainer ? sdCodeContainer.textContent : '';
                            if (codeText) {
                                navigator.clipboard.writeText(codeText).then(() => {
                                    showToast('Pipeline code copied to clipboard!', 'success');
                                }).catch(() => {
                                    showToast('Could not copy code to clipboard.', 'warning');
                                });
                            }
                        });
                    }

                    // Reset to overview tab
                    const overviewTabBtn = document.getElementById('tab-sd-overview-btn');
                    if (overviewTabBtn) {
                        const tabTrigger = new bootstrap.Tab(overviewTabBtn);
                        tabTrigger.show();
                    }

                    // In Analyst dashboard, hide manager action controls
                    const mgrSection = document.getElementById('managerReviewActionContainer');
                    if (mgrSection) {
                        mgrSection.style.display = 'none';
                    }

        if (sharedDetailModalInstance) {
            sharedDetailModalInstance.show();
        }
    }

    const refreshSharedBtn = document.getElementById('refreshAnalystSharedBtn');
    if (refreshSharedBtn) {
        refreshSharedBtn.addEventListener('click', function () {
            fetchAnalystSharedDashboards();
        });
    }

    // Auto-fetch shared dashboards on load
    fetchAnalystSharedDashboards();

    /* ---------------------------------------------------------------------
       Sidebar Navigation ScrollSpy & Active Link Management
       ------------------------------------------------------------------- */
    const navLinks = document.querySelectorAll('#dnAnalystSidebarNav .dn-nav-link');
    const sectionsToTrack = [
        { id: 'main-overview', linkId: 'navAnalystDashboard' },
        { id: 'upload', linkId: 'navUploadDataset' },
        { id: 'step-preview', linkId: 'navRawPreview' },
        { id: 'step-cleaning', linkId: 'navDataCleaning' },
        { id: 'step-eda', linkId: 'navStatisticalEDA' },
        { id: 'step-correlation', linkId: 'navCorrelationMatrix' },
        { id: 'step-visualization', linkId: 'navVisualizations' },
        { id: 'step-insights', linkId: 'navAIInsights' },
        { id: 'step-reports', linkId: 'navReportsExport' },
        { id: 'assignedTasksPanel', linkId: 'navAssignedTasks' },
        { id: 'sharedDashboardsPanel', linkId: 'navSharedDashboards' }
    ];

    function updateActiveNavLink() {
        const scrollPosition = window.scrollY + 100;
        let currentSectionLinkId = 'navAnalystDashboard';

        for (let i = 0; i < sectionsToTrack.length; i++) {
            const section = document.getElementById(sectionsToTrack[i].id);
            if (section && section.style.display !== 'none' && section.offsetTop <= scrollPosition) {
                currentSectionLinkId = sectionsToTrack[i].linkId;
            }
        }

        navLinks.forEach(link => {
            if (link.id && link.id.startsWith('nav')) {
                if (link.id === currentSectionLinkId) {
                    link.classList.add('active');
                } else if (!link.classList.contains('dn-open-ask-modal') && link.getAttribute('data-bs-toggle') !== 'modal') {
                    link.classList.remove('active');
                }
            }
        });
    }

    let scrollTimeout;
    window.addEventListener('scroll', function () {
        if (!scrollTimeout) {
            scrollTimeout = setTimeout(function () {
                updateActiveNavLink();
                scrollTimeout = null;
            }, 50);
        }
    }, { passive: true });

    /* ---------------------------------------------------------------------
       Smooth Auto-Scroll & Navigation Manager for Sidebar & In-Page Anchors
       ------------------------------------------------------------------- */
    navLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            const href = link.getAttribute('href');

            // Disabled link check
            if (link.classList.contains('dn-nav-disabled')) {
                e.preventDefault();
                showToast('Please upload or load a dataset first to access this feature.', 'warning');
                return;
            }

            if (link.id === 'navCodeStudio') {
                e.preventDefault();
                openPythonCodeStudio(activeDatasetId);
                return;
            }

            // Smooth scroll for hash links
            if (href && href.startsWith('#') && href.length > 1) {
                e.preventDefault();
                const targetId = href.substring(1);
                const targetElem = document.getElementById(targetId);
                if (targetElem) {
                    smoothScrollToTarget(targetElem);

                    navLinks.forEach(l => {
                        if (!l.classList.contains('dn-open-ask-modal') && l.getAttribute('data-bs-toggle') !== 'modal') {
                            l.classList.remove('active');
                        }
                    });
                    link.classList.add('active');

                    const appShell = document.querySelector('.dn-app');
                    const overlay = document.querySelector('.dn-sidebar-overlay');
                    if (window.innerWidth <= 991.98 && appShell && appShell.classList.contains('dn-sidebar-open')) {
                        appShell.classList.remove('dn-sidebar-open');
                        if (overlay) overlay.classList.remove('is-visible');
                    }
                }
            }
        });
    });

    document.querySelectorAll('a[href^="#"]:not(.dn-nav-link):not([data-bs-toggle])').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = anchor.getAttribute('href');
            if (href && href.length > 1) {
                const targetElem = document.getElementById(href.substring(1));
                if (targetElem) {
                    e.preventDefault();
                    smoothScrollToTarget(targetElem);
                }
            }
        });
    });

    // Run once on load to sync active link
    updateActiveNavLink();

    /* =====================================================================
       PYTHON CODE STUDIO & JUPYTER NOTEBOOK (.ipynb) SUITE
       =================================================================== */
    const codeStudioModalEl = document.getElementById('pythonCodeStudioModal');
    let codeStudioModalInstance = null;
    if (codeStudioModalEl) {
        codeStudioModalInstance = new bootstrap.Modal(codeStudioModalEl);
    }

    let autoGeneratedPipelineCode = '';
    const codeEditorEl = document.getElementById('pythonStudioCodeEditor');
    const lineNumbersEl = document.getElementById('pythonStudioLineNumbers');
    const datasetBadgeEl = document.getElementById('codeStudioDatasetBadge');
    const roleBadgeEl = document.getElementById('codeStudioRoleBadge');
    const terminalOutputEl = document.getElementById('studioTerminalOutput');
    const plotsContainerEl = document.getElementById('studioPlotsContainer');
    const plotsBadgeEl = document.getElementById('studioPlotsBadge');
    const previewContainerEl = document.getElementById('studioPreviewTableContainer');
    const dfShapeBadgeEl = document.getElementById('studioDfShapeBadge');
    const execStatusBannerEl = document.getElementById('studioExecutionStatusBanner');
    const execTimeBadgeEl = document.getElementById('studioExecTimeBadge');
    const btnRunCode = document.getElementById('btnRunStudioCode');
    const btnCopyCode = document.getElementById('btnCopyStudioCode');
    const btnResetCode = document.getElementById('btnResetStudioCode');
    const btnDownloadIpynb = document.getElementById('btnDownloadIpynbStudio');
    const btnDownloadPy = document.getElementById('btnDownloadPyStudio');
    const btnHeaderOpenStudio = document.getElementById('btnOpenCodeStudio');
    const btnReportsDownloadNb = document.getElementById('btnDownloadNotebookReport');

    function updateLineNumbers() {
        if (!codeEditorEl || !lineNumbersEl) return;
        const lines = (codeEditorEl.value || '').split('\n');
        const count = Math.max(1, lines.length);
        let numStr = '';
        for (let i = 1; i <= count; i++) {
            numStr += i + '\n';
        }
        lineNumbersEl.textContent = numStr;
        const lineBadge = document.getElementById('editorLineCountBadge');
        if (lineBadge) {
            lineBadge.textContent = `${count} line${count === 1 ? '' : 's'} | Ctrl+Enter to Run`;
        }
    }

    if (codeEditorEl) {
        codeEditorEl.addEventListener('input', updateLineNumbers);
        codeEditorEl.addEventListener('scroll', function () {
            if (lineNumbersEl) lineNumbersEl.scrollTop = this.scrollTop;
        });
        codeEditorEl.addEventListener('keydown', function (e) {
            // Shortcut: Ctrl + Enter or Cmd + Enter to Run Code
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                executeStudioCode();
                return;
            }
            // Tab key support: indent with 4 spaces
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.selectionStart;
                const end = this.selectionEnd;
                this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
                this.selectionStart = this.selectionEnd = start + 4;
                updateLineNumbers();
            }
        });
    }

    function openPythonCodeStudio(dsId) {
        const targetId = dsId || activeDatasetId;
        if (!targetId) {
            showToast('Please upload or select an active dataset first to launch Python Code Studio.', 'warning');
            return;
        }

        if (!codeStudioModalInstance && codeStudioModalEl) {
            codeStudioModalInstance = new bootstrap.Modal(codeStudioModalEl);
        }

        if (datasetBadgeEl) datasetBadgeEl.textContent = 'Dataset ID: #' + targetId;
        if (codeEditorEl) {
            codeEditorEl.value = '# Fetching automated data science pipeline code...';
            updateLineNumbers();
        }
        if (terminalOutputEl) terminalOutputEl.textContent = '# Ready for execution. Click "Run Code & Sync Vis" (or press Ctrl + Enter) to execute.';

        if (codeStudioModalInstance) {
            codeStudioModalInstance.show();
        }

        fetch(`/api/dataset/${targetId}/code`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.code) {
                    autoGeneratedPipelineCode = data.code;
                    if (codeEditorEl) {
                        codeEditorEl.value = data.code;
                        codeEditorEl.readOnly = !data.can_edit;
                        updateLineNumbers();
                    }
                    if (datasetBadgeEl) datasetBadgeEl.textContent = `Dataset: ${data.dataset_name || '#' + targetId}`;
                    if (roleBadgeEl) {
                        roleBadgeEl.textContent = data.can_edit ? 'Analyst Studio (Edit & Run)' : 'Developer (Read-Only)';
                        roleBadgeEl.className = 'badge ' + (data.can_edit ? 'bg-primary-subtle text-primary border border-primary-subtle' : 'bg-secondary-subtle text-secondary border');
                    }
                    if (btnRunCode) btnRunCode.style.display = data.can_edit ? 'inline-block' : 'none';
                    if (btnResetCode) btnResetCode.style.display = data.can_edit ? 'inline-block' : 'none';
                } else {
                    if (codeEditorEl) {
                        codeEditorEl.value = '# Error generating pipeline code: ' + (data.message || 'Unknown error');
                        updateLineNumbers();
                    }
                    showToast(data.message || 'Could not load pipeline code.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error fetching pipeline code:', err);
                if (codeEditorEl) {
                    codeEditorEl.value = '# Network error while fetching code.';
                    updateLineNumbers();
                }
                showToast('Failed to load Python pipeline code.', 'danger');
            });
    }

    function executeStudioCode() {
        const targetId = activeDatasetId;
        if (!targetId) {
            showToast('No active dataset found.', 'warning');
            return;
        }

        const codeContent = codeEditorEl ? codeEditorEl.value.trim() : '';
        if (!codeContent) {
            showToast('Code cannot be empty.', 'warning');
            return;
        }

        const startTime = Date.now();
        if (btnRunCode) {
            btnRunCode.disabled = true;
            btnRunCode.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Running...';
        }

        if (execStatusBannerEl) {
            execStatusBannerEl.className = 'alert alert-primary py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
            execStatusBannerEl.innerHTML = '<span><span class="spinner-border spinner-border-sm me-2" role="status"></span> Executing Python code in sandbox...</span><span class="badge bg-primary font-monospace">Running</span>';
        }

        fetch(`/api/dataset/${targetId}/execute_code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: codeContent })
        })
            .then(res => res.json())
            .then(data => {
                const duration = ((Date.now() - startTime) / 1000).toFixed(2);
                if (execTimeBadgeEl) execTimeBadgeEl.textContent = `${duration}s`;

                if (data.success) {
                    const plotCount = data.plots ? data.plots.length : 0;
                    if (execStatusBannerEl) {
                        execStatusBannerEl.className = 'alert alert-success py-2 px-3 small mb-2';
                        execStatusBannerEl.innerHTML = `
                            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 w-100">
                                <div class="d-flex align-items-center gap-2">
                                    <i class="bi bi-check-circle-fill text-success fs-6"></i>
                                    <span class="fw-bold text-success">Execution Succeeded (${duration}s)</span>
                                </div>
                                <div class="btn-group btn-group-sm">
                                    <button type="button" class="btn btn-sm btn-outline-primary active" id="btnQuickPlots" onclick="const b=document.getElementById('tab-studio-plots-btn'); if(b) bootstrap.Tab.getOrCreateInstance(b).show();"><i class="bi bi-image me-1"></i>Visual Plots (${plotCount})</button>
                                    <button type="button" class="btn btn-sm btn-outline-success" id="btnQuickTable" onclick="const b=document.getElementById('tab-studio-preview-btn'); if(b) bootstrap.Tab.getOrCreateInstance(b).show();"><i class="bi bi-table me-1"></i>Table View</button>
                                    <button type="button" class="btn btn-sm btn-outline-secondary" id="btnQuickConsole" onclick="const b=document.getElementById('tab-studio-terminal-btn'); if(b) bootstrap.Tab.getOrCreateInstance(b).show();"><i class="bi bi-terminal me-1"></i>Console Log</button>
                                </div>
                            </div>
                        `;
                    }

                    // Console Output
                    if (terminalOutputEl) {
                        terminalOutputEl.textContent = data.stdout || '# Execution finished with no console output.';
                    }

                    // Generated Plots
                    if (plotsContainerEl) {
                        if (plotCount > 0) {
                            if (plotsBadgeEl) {
                                plotsBadgeEl.textContent = plotCount;
                                plotsBadgeEl.style.display = 'inline-block';
                            }
                            plotsContainerEl.innerHTML = data.plots.map((p, i) => `
                                <div class="border rounded-3 p-3 bg-body shadow-sm">
                                    <div class="d-flex justify-content-between align-items-center mb-2">
                                        <h6 class="small fw-bold mb-0 text-primary"><i class="bi bi-graph-up me-1"></i> Figure ${i + 1}</h6>
                                        <a href="${p}" download="figure_${i + 1}.png" class="btn btn-xs btn-outline-secondary py-0 px-2 small" style="font-size:0.75rem;"><i class="bi bi-download me-1"></i>Save PNG</a>
                                    </div>
                                    <img src="${p}" class="img-fluid rounded border bg-white shadow-sm w-100" alt="Plot ${i + 1}" style="max-height:360px; object-fit:contain;">
                                </div>
                            `).join('');

                            // Auto-switch to Visual Plots tab
                            const plotsTabBtn = document.getElementById('tab-studio-plots-btn');
                            if (plotsTabBtn) bootstrap.Tab.getOrCreateInstance(plotsTabBtn).show();
                        } else {
                            if (plotsBadgeEl) plotsBadgeEl.style.display = 'none';
                            plotsContainerEl.innerHTML = '<div class="text-center py-4 text-muted small"><i class="bi bi-image fs-2 d-block mb-1 opacity-50"></i> No figures generated by code execution.</div>';
                            
                            // If table preview is available, switch to table view
                            if (data.preview_html) {
                                const tableTabBtn = document.getElementById('tab-studio-preview-btn');
                                if (tableTabBtn) bootstrap.Tab.getOrCreateInstance(tableTabBtn).show();
                            }
                        }
                    }

                    // DataFrame Preview (Styled table)
                    if (previewContainerEl) {
                        previewContainerEl.innerHTML = data.preview_html || '<div class="p-3 text-muted">Preview not available.</div>';
                        const renderedTable = previewContainerEl.querySelector('table');
                        if (renderedTable) {
                            renderedTable.className = 'table table-hover table-striped dn-table align-middle small mb-0 font-monospace';
                        }
                    }
                    if (dfShapeBadgeEl) {
                        dfShapeBadgeEl.textContent = `${Number(data.row_count || 0).toLocaleString()} rows x ${data.column_count || 0} cols`;
                    }

                    // If DataFrame was updated, sync live dashboard visual state!
                    if (data.df_updated && data.dataset_payload) {
                        showToast('Dataset updated! Synchronizing dashboard charts and metrics...', 'success');
                        if (typeof populateDatasetWorkspace === 'function') {
                            populateDatasetWorkspace(data.dataset_payload, 'Updated Dataset', false);
                        }
                    } else {
                        showToast(`Python code executed successfully (${duration}s)!`, 'success');
                    }
                } else {
                    if (execStatusBannerEl) {
                        execStatusBannerEl.className = 'alert alert-danger py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
                        execStatusBannerEl.innerHTML = `<span><i class="bi bi-x-circle-fill text-danger me-1"></i> Execution Failed</span><span class="badge bg-danger font-monospace">Error</span>`;
                    }

                    if (terminalOutputEl) {
                        terminalOutputEl.textContent = (data.stdout ? data.stdout + '\n\n' : '') + (data.error || 'Execution error.');
                    }
                    // Switch to console to view traceback
                    const consoleTabBtn = document.getElementById('tab-studio-terminal-btn');
                    if (consoleTabBtn) bootstrap.Tab.getOrCreateInstance(consoleTabBtn).show();

                    showToast('Code execution failed. Check console output for error traceback.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error executing code:', err);
                if (execStatusBannerEl) {
                    execStatusBannerEl.className = 'alert alert-danger py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
                    execStatusBannerEl.innerHTML = `<span><i class="bi bi-wifi-off text-danger me-1"></i> Network Error</span><span class="badge bg-danger font-monospace">Failed</span>`;
                }
                showToast('Network error during code execution.', 'danger');
            })
            .finally(() => {
                if (btnRunCode) {
                    btnRunCode.disabled = false;
                    btnRunCode.innerHTML = '<i class="bi bi-play-fill me-1"></i> Run Code &amp; Sync Vis <kbd class="bg-white text-dark ms-1 px-1 py-0 rounded small fw-bold" style="font-size:0.68rem; opacity:0.9;">Ctrl+Enter</kbd>';
                }
            });
    }

    function triggerDownloadNotebook(format = 'ipynb') {
        const targetId = activeDatasetId;
        if (!targetId) {
            showToast('Please select or upload a dataset first.', 'warning');
            return;
        }
        window.location.href = `/api/dataset/${targetId}/download_notebook?format=${format}`;
        showToast(`Preparing ${format.toUpperCase()} download...`, 'info');
    }

    if (btnHeaderOpenStudio) {
        btnHeaderOpenStudio.addEventListener('click', () => openPythonCodeStudio(activeDatasetId));
    }

    if (btnRunCode) {
        btnRunCode.addEventListener('click', executeStudioCode);
    }

    if (btnCopyCode) {
        btnCopyCode.addEventListener('click', () => {
            const code = codeEditorEl ? codeEditorEl.value : '';
            if (code) {
                navigator.clipboard.writeText(code).then(() => {
                    showToast('Code copied to clipboard!', 'success');
                }).catch(() => {
                    showToast('Could not copy code.', 'warning');
                });
            }
        });
    }

    if (btnResetCode) {
        btnResetCode.addEventListener('click', () => {
            if (autoGeneratedPipelineCode && codeEditorEl) {
                codeEditorEl.value = autoGeneratedPipelineCode;
                updateLineNumbers();
                showToast('Reset code to automated baseline pipeline.', 'info');
            }
        });
    }

    if (btnDownloadIpynb) {
        btnDownloadIpynb.addEventListener('click', (e) => {
            e.preventDefault();
            triggerDownloadNotebook('ipynb');
        });
    }

    if (btnDownloadPy) {
        btnDownloadPy.addEventListener('click', (e) => {
            e.preventDefault();
            triggerDownloadNotebook('py');
        });
    }

    if (btnReportsDownloadNb) {
        btnReportsDownloadNb.addEventListener('click', () => {
            triggerDownloadNotebook('ipynb');
        });
    }

    /* ---------------------------------------------------------------------
       11. ML & PREDICTIVE INTELLIGENCE STUDIO CONTROLLER
       ------------------------------------------------------------------- */
    let currentMlModality = 'regression';
    let currentMlOptions = null;
    let currentMlResults = null;
    let currentActiveChartType = 'scatter';
    let selectedSavedModel = null;

    const mlStudioModalEl = document.getElementById('dnMlStudioModal');
    const mlNavButtons = document.querySelectorAll('#mlModalityNav [data-modality]');
    const mlTargetColSelect = document.getElementById('mlTargetColSelect');
    const mlTargetColGroup = document.getElementById('mlTargetColGroup');
    const mlTargetColLabel = document.getElementById('mlTargetColLabel');
    const mlDateColSelect = document.getElementById('mlDateColSelect');
    const mlDateColGroup = document.getElementById('mlDateColGroup');
    const mlParamGroup = document.getElementById('mlParamGroup');
    const mlParamLabel = document.getElementById('mlParamLabel');
    const mlParamInput = document.getElementById('mlParamInput');
    const mlParamUnit = document.getElementById('mlParamUnit');
    const mlFeaturePillsContainer = document.getElementById('mlFeaturePillsContainer');
    const mlSelectedFeaturesCount = document.getElementById('mlSelectedFeaturesCount');
    const btnRunMlStudio = document.getElementById('btnRunMlStudio');
    const btnResetMlDefaults = document.getElementById('btnResetMlDefaults');
    const btnSmartSelectFeatures = document.getElementById('btnSmartSelectFeatures');
    const mlExecutionSpinner = document.getElementById('mlExecutionSpinner');
    const mlResultsContainer = document.getElementById('mlResultsContainer');
    const mlStudioDatasetBadge = document.getElementById('mlStudioDatasetBadge');
    const mlStudioModelBadge = document.getElementById('mlStudioModelBadge');
    const mlSearchPredictionsInput = document.getElementById('mlSearchPredictionsInput');
    const btnExportPredictionsCsv = document.getElementById('btnExportPredictionsCsv');
    const btnSaveCurrentModel = document.getElementById('btnSaveCurrentModel');
    const btnOpenSavedModelsModal = document.getElementById('btnOpenSavedModelsModal');
    const savedModelsCountBadge = document.getElementById('savedModelsCountBadge');

    function getSelectedMlFeatures() {
        if (!mlFeaturePillsContainer) return [];
        const checked = mlFeaturePillsContainer.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checked).map(cb => cb.value);
    }

    function updateSelectedFeaturesCount() {
        if (!mlSelectedFeaturesCount) return;
        const count = getSelectedMlFeatures().length;
        mlSelectedFeaturesCount.textContent = `${count} features selected`;
    }

    function syncMlModalControls(modality) {
        currentMlModality = modality;

        mlNavButtons.forEach(btn => {
            if (btn.getAttribute('data-modality') === modality) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        const formulaCard = document.getElementById('mlFormulaCard');
        const humanExpSection = document.getElementById('mlHumanExplanationsSection');
        const chartTabButtons = document.getElementById('mlChartTabButtons');

        if (modality === 'regression') {
            if (mlTargetColGroup) mlTargetColGroup.classList.remove('d-none');
            if (mlTargetColLabel) mlTargetColLabel.textContent = 'Target Column (y - Numeric Continuous)';
            if (mlDateColGroup) mlDateColGroup.classList.add('d-none');
            if (mlParamGroup) mlParamGroup.classList.add('d-none');
            if (mlStudioModelBadge) mlStudioModelBadge.textContent = 'Linear Regression (OLS)';
            if (formulaCard) formulaCard.classList.remove('d-none');
            if (humanExpSection) humanExpSection.classList.remove('d-none');
            if (chartTabButtons) chartTabButtons.classList.remove('d-none');
        } else {
            if (formulaCard) formulaCard.classList.add('d-none');
            if (humanExpSection) humanExpSection.classList.add('d-none');
            if (chartTabButtons) chartTabButtons.classList.add('d-none');

            if (modality === 'classification') {
                if (mlTargetColGroup) mlTargetColGroup.classList.remove('d-none');
                if (mlTargetColLabel) mlTargetColLabel.textContent = 'Target Column (y - Categorical / Binary Class)';
                if (mlDateColGroup) mlDateColGroup.classList.add('d-none');
                if (mlParamGroup) mlParamGroup.classList.add('d-none');
                if (mlStudioModelBadge) mlStudioModelBadge.textContent = 'Random Forest Classifier';
            } else if (modality === 'clustering') {
                if (mlTargetColGroup) mlTargetColGroup.classList.add('d-none');
                if (mlDateColGroup) mlDateColGroup.classList.add('d-none');
                if (mlParamGroup) mlParamGroup.classList.remove('d-none');
                if (mlParamLabel) mlParamLabel.textContent = 'Number of Clusters (K)';
                if (mlParamInput) { mlParamInput.value = 3; mlParamInput.min = 2; mlParamInput.max = 8; }
                if (mlParamUnit) mlParamUnit.textContent = 'Clusters';
                if (mlStudioModelBadge) mlStudioModelBadge.textContent = 'K-Means Spatial Clustering';
            } else if (modality === 'forecasting') {
                if (mlTargetColGroup) mlTargetColGroup.classList.remove('d-none');
                if (mlTargetColLabel) mlTargetColLabel.textContent = 'Forecast Metric (Numeric Value)';
                if (mlDateColGroup) mlDateColGroup.classList.remove('d-none');
                if (mlParamGroup) mlParamGroup.classList.remove('d-none');
                if (mlParamLabel) mlParamLabel.textContent = 'Forecast Horizon';
                if (mlParamInput) { mlParamInput.value = 14; mlParamInput.min = 3; mlParamInput.max = 90; }
                if (mlParamUnit) mlParamUnit.textContent = 'Periods';
                if (mlStudioModelBadge) mlStudioModelBadge.textContent = 'Time-Series Trend & Seasonality';
            } else if (modality === 'anomaly') {
                if (mlTargetColGroup) mlTargetColGroup.classList.add('d-none');
                if (mlDateColGroup) mlDateColGroup.classList.add('d-none');
                if (mlParamGroup) mlParamGroup.classList.remove('d-none');
                if (mlParamLabel) mlParamLabel.textContent = 'Contamination Rate (%)';
                if (mlParamInput) { mlParamInput.value = 5; mlParamInput.min = 1; mlParamInput.max = 20; }
                if (mlParamUnit) mlParamUnit.textContent = '% Outliers';
                if (mlStudioModelBadge) mlStudioModelBadge.textContent = 'Isolation Forest Outlier Detection';
            }
        }

        if (currentMlOptions) {
            populateMlColumnOptions(currentMlOptions, modality);
        }
    }

    function populateMlColumnOptions(rawRes, modality) {
        if (!rawRes) return;
        const data = (rawRes.data && (rawRes.data.numeric_cols || rawRes.data.recommendations)) ? rawRes.data : rawRes;
        currentMlOptions = data;
        const recs = (data.recommendations && data.recommendations[modality]) ? data.recommendations[modality] : {};
        const correlations = data.correlations || {};
        const compatibility = data.compatibility || {};
        let numericCols = data.numeric_cols || [];
        let catCols = data.cat_cols || [];
        let dateCols = data.date_cols || [];

        if (numericCols.length === 0 && typeof fullColumnInfo !== 'undefined' && fullColumnInfo && fullColumnInfo.length > 0) {
            numericCols = fullColumnInfo.filter(c => c.type === 'Integer' || c.type === 'Float' || c.semantic_type === 'numeric' || c.semantic_type === 'measure').map(c => c.name);
            if (numericCols.length === 0) numericCols = fullColumnInfo.map(c => c.name);
        }
        if (catCols.length === 0 && typeof fullColumnInfo !== 'undefined' && fullColumnInfo && fullColumnInfo.length > 0) {
            catCols = fullColumnInfo.filter(c => c.type === 'Text' || c.semantic_type === 'categorical' || c.semantic_type === 'category').map(c => c.name);
            if (catCols.length === 0) catCols = fullColumnInfo.map(c => c.name);
        }

        // 0. Update Modality Nav Badges based on Dataset Compatibility
        mlNavButtons.forEach(btn => {
            const mKey = btn.getAttribute('data-modality');
            const mComp = compatibility[mKey] || { is_trainable: true };
            const existingBadge = btn.querySelector('.badge-incompat');
            if (mComp.is_trainable === false) {
                if (!existingBadge) {
                    const b = document.createElement('span');
                    b.className = 'badge bg-danger-subtle text-danger border ms-1 badge-incompat';
                    b.style.fontSize = '0.62rem';
                    b.textContent = 'Not Applicable';
                    btn.appendChild(b);
                }
            } else {
                if (existingBadge) existingBadge.remove();
            }
        });

        // Check active modality compatibility
        const currentComp = compatibility[modality] || { is_trainable: true };
        const warningBox = document.getElementById('mlIncompatibleWarningBox');
        const warningReason = document.getElementById('mlIncompatibleReason');
        const warningTitle = document.getElementById('mlIncompatibleTitle');

        if (currentComp.is_trainable === false) {
            if (warningBox) warningBox.classList.remove('d-none');
            if (warningTitle) warningTitle.textContent = `Model Not Trainable for Active Dataset (${modality.toUpperCase()})`;
            if (warningReason) warningReason.textContent = currentComp.reason || `Selected dataset lacks required column structures for ${modality}. Model execution is disabled.`;

            if (btnRunMlStudio) {
                btnRunMlStudio.disabled = true;
                btnRunMlStudio.className = 'btn btn-sm btn-secondary flex-grow-1 fw-semibold d-flex align-items-center justify-content-center gap-2';
                btnRunMlStudio.innerHTML = '<i class="bi bi-slash-circle me-1"></i> <span>Model Not Applicable (Training Disabled)</span>';
            }
        } else {
            if (warningBox) warningBox.classList.add('d-none');
            if (btnRunMlStudio) {
                btnRunMlStudio.disabled = false;
                btnRunMlStudio.className = 'btn btn-sm btn-primary flex-grow-1 fw-semibold d-flex align-items-center justify-content-center gap-2';
                btnRunMlStudio.innerHTML = '<i class="bi bi-play-fill fs-6"></i> <span>Run Model &amp; Predict</span>';
            }
        }

        // 1. Populate Target Column Select
        if (mlTargetColSelect) {
            const currentSelectedTarget = mlTargetColSelect.value;
            mlTargetColSelect.innerHTML = '';
            let candidateList = (modality === 'classification') ? (catCols.length ? catCols : numericCols) : numericCols;
            if (candidateList.length === 0 && typeof fullColumnInfo !== 'undefined' && fullColumnInfo) {
                candidateList = fullColumnInfo.map(c => c.name);
            }
            candidateList.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.textContent = col;
                if (currentSelectedTarget && currentSelectedTarget === col) {
                    opt.selected = true;
                } else if (!currentSelectedTarget && (recs.target === col || (modality === 'forecasting' && recs.value_col === col))) {
                    opt.selected = true;
                }
                mlTargetColSelect.appendChild(opt);
            });
            if (mlTargetColSelect.options.length > 0 && !mlTargetColSelect.value) {
                mlTargetColSelect.selectedIndex = 0;
            }
        }

        // 2. Populate Date Column Select (Forecasting)
        if (mlDateColSelect) {
            mlDateColSelect.innerHTML = '<option value="">Automatic chronological sequence</option>';
            dateCols.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.textContent = col;
                if (recs.date_col === col) opt.selected = true;
                mlDateColSelect.appendChild(opt);
            });
        }

        // 3. Populate Feature Checkbox Pills with Correlation Ratings
        if (mlFeaturePillsContainer) {
            mlFeaturePillsContainer.innerHTML = '';
            const recFeatures = recs.features || [];
            const displayFeatures = numericCols.length > 0 ? numericCols : (typeof fullColumnInfo !== 'undefined' && fullColumnInfo ? fullColumnInfo.map(c => c.name) : []);
            
            displayFeatures.forEach(col => {
                const isChecked = recFeatures.length > 0 ? recFeatures.includes(col) : true;
                const corrInfo = correlations[col] || {};
                const badgeClass = corrInfo.badge || 'secondary';
                const corrText = corrInfo.corr !== undefined ? ` (r=${corrInfo.corr >= 0 ? '+' : ''}${corrInfo.corr})` : '';

                const pillLabel = document.createElement('label');
                pillLabel.className = `btn btn-sm btn-outline-${badgeClass === 'secondary' ? 'secondary' : badgeClass} py-0.5 px-2 small d-inline-flex align-items-center gap-1.5 rounded-pill mb-0 text-body`;
                pillLabel.style.fontSize = '0.78rem';
                pillLabel.innerHTML = `
                    <input type="checkbox" class="form-check-input mt-0" value="${col}" ${isChecked ? 'checked' : ''} style="cursor:pointer;" data-badge="${badgeClass}">
                    <span class="fw-semibold">${col}</span>
                    ${corrText ? `<span class="badge bg-${badgeClass}-subtle text-${badgeClass} border font-monospace" style="font-size:0.7rem;">${corrText}</span>` : ''}
                `;
                pillLabel.querySelector('input').addEventListener('change', () => {
                    updateSelectedFeaturesCount();
                });
                mlFeaturePillsContainer.appendChild(pillLabel);
            });
            updateSelectedFeaturesCount();
        }
    }

    function fetchMlOptionsAndRun(modality, autoRun = true) {
        const dsId = activeDatasetId || (document.getElementById('datasetSelect') ? document.getElementById('datasetSelect').value : null);
        if (!dsId) {
            showToast('Please select or upload a dataset first.', 'warning');
            return;
        }

        if (mlStudioDatasetBadge) {
            const selectEl = document.getElementById('datasetSelect');
            const activeOption = selectEl ? selectEl.options[selectEl.selectedIndex] : null;
            mlStudioDatasetBadge.innerHTML = `<i class="bi bi-database me-1"></i> ${activeOption ? activeOption.text.trim() : 'Dataset #' + dsId}`;
        }

        updateSavedModelsBadge(dsId);

        fetch(`/api/ml/options?dataset_id=${encodeURIComponent(dsId)}`)
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    populateMlColumnOptions(resData, modality);
                    const isTrainable = resData.compatibility ? (resData.compatibility[modality]?.is_trainable !== false) : true;
                    if (autoRun && isTrainable) {
                        executeMlModel();
                    }
                } else {
                    showToast(resData.message || 'Could not load dataset columns for ML.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error fetching ML options:', err);
                showToast('Failed to load ML column options.', 'danger');
            });
    }

    function executeMlModel() {
        const dsId = activeDatasetId || (document.getElementById('datasetSelect') ? document.getElementById('datasetSelect').value : null);
        if (!dsId) {
            showToast('No active dataset selected for prediction.', 'warning');
            return;
        }

        const currentComp = (currentMlOptions && currentMlOptions.compatibility && currentMlOptions.compatibility[currentMlModality]) ? currentMlOptions.compatibility[currentMlModality] : { is_trainable: true };
        if (currentComp.is_trainable === false) {
            showToast(currentComp.reason || 'This dataset is not compatible with the selected model. Training is blocked.', 'danger');
            return;
        }

        const targetCol = mlTargetColSelect ? mlTargetColSelect.value : null;
        const dateCol = mlDateColSelect ? mlDateColSelect.value : null;
        const features = getSelectedMlFeatures();
        let paramVal = mlParamInput ? parseFloat(mlParamInput.value) : null;

        const payload = {
            dataset_id: dsId,
            modality: currentMlModality,
            target_col: targetCol,
            date_col: dateCol,
            feature_cols: features
        };

        if (currentMlModality === 'clustering') payload.n_clusters = parseInt(paramVal) || 3;
        if (currentMlModality === 'forecasting') {
            payload.horizon = parseInt(paramVal) || 14;
            payload.value_col = targetCol;
        }
        if (currentMlModality === 'anomaly') payload.contamination = ((parseFloat(paramVal) || 5) / 100.0);

        if (mlExecutionSpinner) mlExecutionSpinner.classList.remove('d-none');
        if (mlResultsContainer) mlResultsContainer.classList.add('opacity-50');
        if (btnRunMlStudio) {
            btnRunMlStudio.disabled = true;
            btnRunMlStudio.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> <span>Training Model...</span>';
        }

        fetch('/api/ml/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(result => {
                if (mlExecutionSpinner) mlExecutionSpinner.classList.add('d-none');
                if (mlResultsContainer) mlResultsContainer.classList.remove('opacity-50');
                if (btnRunMlStudio) {
                    btnRunMlStudio.disabled = false;
                    btnRunMlStudio.innerHTML = '<i class="bi bi-play-fill fs-6"></i> <span>Run Model &amp; Predict</span>';
                }

                if (result.success) {
                    currentMlResults = result;
                    renderMlResults(result);
                    showToast(`Successfully trained ${result.model_name || 'model'} and generated predictions!`, 'success');
                } else {
                    showToast(result.message || 'Model execution encountered an error.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error running ML model:', err);
                if (mlExecutionSpinner) mlExecutionSpinner.classList.add('d-none');
                if (mlResultsContainer) mlResultsContainer.classList.remove('opacity-50');
                if (btnRunMlStudio) {
                    btnRunMlStudio.disabled = false;
                    btnRunMlStudio.innerHTML = '<i class="bi bi-play-fill fs-6"></i> <span>Run Model &amp; Predict</span>';
                }
                showToast('Server error while executing ML model.', 'danger');
            });
    }

    function renderMlResults(result) {
        const modality = result.model_type || currentMlModality;
        const metrics = result.metrics || {};

        // 1. Update Equation & Formula Card (Regression)
        const formulaCard = document.getElementById('mlFormulaCard');
        const interceptBadge = document.getElementById('mlInterceptBadge');
        const formulaText = document.getElementById('mlFormulaText');

        if (modality === 'regression') {
            if (formulaCard) formulaCard.classList.remove('d-none');
            if (interceptBadge) interceptBadge.textContent = `Intercept (β0): ${result.intercept !== undefined ? result.intercept : '--'}`;
            if (formulaText) formulaText.textContent = result.formula || 'Target = β0 + (β1 × Feature1)...';
        } else {
            if (formulaCard) formulaCard.classList.add('d-none');
        }

        // 2. Update Top KPI Cards
        const k1Label = document.getElementById('mlKpi1Label');
        const k1Val = document.getElementById('mlKpi1Value');
        const k1Sub = document.getElementById('mlKpi1Sub');

        const k2Label = document.getElementById('mlKpi2Label');
        const k2Val = document.getElementById('mlKpi2Value');
        const k2Sub = document.getElementById('mlKpi2Sub');

        const k3Label = document.getElementById('mlKpi3Label');
        const k3Val = document.getElementById('mlKpi3Value');
        const k3Sub = document.getElementById('mlKpi3Sub');

        const k4Label = document.getElementById('mlKpi4Label');
        const k4Val = document.getElementById('mlKpi4Value');
        const k4Sub = document.getElementById('mlKpi4Sub');

        if (modality === 'regression') {
            if (k1Label) k1Label.textContent = 'R² Determination';
            if (k1Val) k1Val.textContent = (metrics.r2_score !== undefined) ? metrics.r2_score : '--';
            if (k1Sub) k1Sub.textContent = 'Model Goodness of Fit';

            if (k2Label) k2Label.textContent = 'MAE Error';
            if (k2Val) k2Val.textContent = (metrics.mae !== undefined) ? metrics.mae : '--';
            if (k2Sub) k2Sub.textContent = 'Mean Absolute Error';

            if (k3Label) k3Label.textContent = 'RMSE Error';
            if (k3Val) k3Val.textContent = (metrics.rmse !== undefined) ? metrics.rmse : '--';
            if (k3Sub) k3Sub.textContent = 'Root Mean Squared Error';

            if (k4Label) k4Label.textContent = 'Sample Size';
            if (k4Val) k4Val.textContent = (metrics.test_samples !== undefined) ? metrics.test_samples : '--';
            if (k4Sub) k4Sub.textContent = 'Evaluated Test Rows';
        } else if (modality === 'classification') {
            if (k1Label) k1Label.textContent = 'Model Accuracy';
            if (k1Val) k1Val.textContent = (metrics.accuracy !== undefined) ? `${metrics.accuracy}%` : '--';
            if (k1Sub) k1Sub.textContent = 'Correct Class Predictions';

            if (k2Label) k2Label.textContent = 'F1-Score';
            if (k2Val) k2Val.textContent = (metrics.f1_score !== undefined) ? `${metrics.f1_score}%` : '--';
            if (k2Sub) k2Sub.textContent = 'Harmonic Precision-Recall';

            if (k3Label) k3Label.textContent = 'Precision';
            if (k3Val) k3Val.textContent = (metrics.precision !== undefined) ? `${metrics.precision}%` : '--';
            if (k3Sub) k3Sub.textContent = 'Positive Predictive Value';

            if (k4Label) k4Label.textContent = 'Dataset Records';
            if (k4Val) k4Val.textContent = (metrics.total_records !== undefined) ? metrics.total_records : '--';
            if (k4Sub) k4Sub.textContent = 'Total labeled training records';
        } else if (modality === 'clustering') {
            if (k1Label) k1Label.textContent = 'Silhouette Score';
            if (k1Val) k1Val.textContent = (metrics.silhouette_score !== undefined) ? metrics.silhouette_score : '--';
            if (k1Sub) k1Sub.textContent = 'Cluster Separation Quality';

            if (k2Label) k2Label.textContent = 'Clusters Formed';
            if (k2Val) k2Val.textContent = (metrics.n_clusters !== undefined) ? metrics.n_clusters : '--';
            if (k2Sub) k2Sub.textContent = 'Distinct Customer Cohorts';

            if (k3Label) k3Label.textContent = 'Inertia (WCSS)';
            if (k3Val) k3Val.textContent = (metrics.inertia !== undefined) ? metrics.inertia : '--';
            if (k3Sub) k3Sub.textContent = 'Within-Cluster Sum of Squares';

            if (k4Label) k4Label.textContent = 'Clustered Records';
            if (k4Val) k4Val.textContent = (metrics.total_records !== undefined) ? metrics.total_records : '--';
            if (k4Sub) k4Sub.textContent = 'Segmented dataset entities';
        } else if (modality === 'forecasting') {
            if (k1Label) k1Label.textContent = 'Projected Avg';
            if (k1Val) k1Val.textContent = (metrics.avg_projected_value !== undefined) ? metrics.avg_projected_value : '--';
            if (k1Sub) k1Sub.textContent = 'Mean future forecast value';

            if (k2Label) k2Label.textContent = 'Growth Trend';
            if (k2Val) k2Val.textContent = (metrics.growth_trend_pct !== undefined) ? `${metrics.growth_trend_pct > 0 ? '+' : ''}${metrics.growth_trend_pct}%` : '--';
            if (k2Sub) k2Sub.textContent = 'Projected delta vs baseline';

            if (k3Label) k3Label.textContent = 'Horizon Periods';
            if (k3Val) k3Val.textContent = (metrics.forecast_periods !== undefined) ? metrics.forecast_periods : '--';
            if (k3Sub) k3Sub.textContent = 'Future steps projected';

            if (k4Label) k4Label.textContent = 'Historical Base';
            if (k4Val) k4Val.textContent = (metrics.historical_periods !== undefined) ? metrics.historical_periods : '--';
            if (k4Sub) k4Sub.textContent = 'Chronological historical points';
        } else if (modality === 'anomaly') {
            if (k1Label) k1Label.textContent = 'Anomalies Detected';
            if (k1Val) k1Val.textContent = (metrics.anomalies_detected !== undefined) ? metrics.anomalies_detected : '--';
            if (k1Sub) k1Sub.textContent = 'High-risk multivariate outliers';

            if (k2Label) k2Label.textContent = 'Anomaly Rate';
            if (k2Val) k2Val.textContent = (metrics.anomaly_rate_pct !== undefined) ? `${metrics.anomaly_rate_pct}%` : '--';
            if (k2Sub) k2Sub.textContent = 'Outlier percentage of dataset';

            if (k3Label) k3Label.textContent = 'Contamination';
            if (k3Val) k3Val.textContent = (metrics.contamination_parameter !== undefined) ? metrics.contamination_parameter : '--';
            if (k3Sub) k3Sub.textContent = 'Configured sensitivity';

            if (k4Label) k4Label.textContent = 'Total Analyzed';
            if (k4Val) k4Val.textContent = (metrics.total_records_analyzed !== undefined) ? metrics.total_records_analyzed : '--';
            if (k4Sub) k4Sub.textContent = 'Records scanned by Isolation Forest';
        }

        // 3. Render Multi-Chart Plotly Visualizations (Scatter, Residuals, Coefficients)
        renderMlPlotlyCharts(result);

        // 4. Render Plain-Language Human Explanations Box
        renderHumanExplanations(result);

        // 5. Render Feature Importances / Driver Ranking
        renderFeatureImportances(result);

        // 6. Render Predictions Table ("What was Predicted")
        renderPredictionsTable(result);

        // 7. Render Inline Predictions directly in Step 7 on Dashboard
        renderStep7InlinePredictions(result);
    }

    function renderStep7InlinePredictions(result) {
        const emptyState = document.getElementById('step7PredictionsEmptyState');
        const activeContent = document.getElementById('step7PredictionsActiveContent');

        if (!result || !result.success) {
            if (emptyState) emptyState.classList.remove('d-none');
            if (activeContent) activeContent.classList.add('d-none');
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');
        if (activeContent) activeContent.classList.remove('d-none');

        const modelBadge = document.getElementById('step7ModelBadge');
        const targetName = document.getElementById('step7TargetName');
        const r2Val = document.getElementById('step7R2Value');
        const r2Sub = document.getElementById('step7R2Sub');
        const maeVal = document.getElementById('step7MaeValue');
        const maeSub = document.getElementById('step7MaeSub');
        const formulaText = document.getElementById('step7FormulaText');
        const interceptText = document.getElementById('step7InterceptText');
        const countBadge = document.getElementById('step7PredCountBadge');

        const modality = result.model_type || 'regression';
        const metrics = result.metrics || {};

        if (modelBadge) modelBadge.innerHTML = `<i class="bi bi-cpu-fill me-1"></i> ${result.model_name || 'Linear Regression (OLS)'}`;
        if (targetName) targetName.textContent = result.target_column || 'Target';

        if (modality === 'regression') {
            if (r2Val) r2Val.textContent = (metrics.r2_score !== undefined) ? metrics.r2_score : '--';
            if (r2Sub) r2Sub.textContent = 'Model Goodness of Fit';
            if (maeVal) maeVal.textContent = (metrics.mae !== undefined) ? metrics.mae : '--';
            if (maeSub) maeSub.textContent = 'Mean Absolute Error';
            if (formulaText) formulaText.textContent = result.formula || 'Target = β0 + (β1 × Feature)...';
            if (interceptText) interceptText.textContent = `Intercept (β0): ${result.intercept !== undefined ? result.intercept : '--'}`;
        } else {
            if (r2Val) r2Val.textContent = (metrics.accuracy !== undefined) ? `${metrics.accuracy}%` : '--';
            if (r2Sub) r2Sub.textContent = 'Classification Accuracy';
            if (maeVal) maeVal.textContent = (metrics.f1_score !== undefined) ? `${metrics.f1_score}%` : '--';
            if (maeSub) maeSub.textContent = 'F1-Score Performance';
            if (formulaText) formulaText.textContent = `Modality: ${modality.toUpperCase()}`;
            if (interceptText) interceptText.textContent = `Evaluated on dataset`;
        }

        // Predictions Table
        const thead = document.getElementById('step7PredThead');
        const tbody = document.getElementById('step7PredTbody');
        const samplePreds = result.sample_predictions || [];

        if (countBadge) countBadge.textContent = `${samplePreds.length} Predictions`;

        if (thead && tbody) {
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (samplePreds.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No prediction rows generated.</td></tr>';
            } else if (modality === 'regression') {
                thead.innerHTML = `
                    <tr>
                        <th style="width: 70px;"># Record</th>
                        <th>Actual Value (y)</th>
                        <th>Predicted Value (&hat;y)</th>
                        <th>Difference (&Delta;)</th>
                        <th class="text-end">Status</th>
                    </tr>
                `;
                samplePreds.forEach(p => {
                    const tr = document.createElement('tr');
                    const actVal = (p.actual_value !== undefined) ? p.actual_value : ((p.actual !== undefined) ? p.actual : '--');
                    const predVal = (p.predicted_value !== undefined) ? p.predicted_value : ((p.predicted !== undefined) ? p.predicted : '--');
                    const resErr = (p.residual_error !== undefined) ? p.residual_error : ((p.error !== undefined) ? p.error : 0);
                    const varPctStr = (p.variance_pct !== undefined) ? String(p.variance_pct) : ((p.pct_error !== undefined) ? `${p.pct_error}%` : '0%');
                    const errPct = parseFloat(varPctStr) || 0;
                    const badgeClass = errPct <= 10 ? 'bg-success-subtle text-success border-success-subtle' : (errPct <= 25 ? 'bg-warning-subtle text-warning border-warning-subtle' : 'bg-danger-subtle text-danger border-danger-subtle');

                    tr.innerHTML = `
                        <td class="text-secondary font-monospace">#${p.record_id || 1}</td>
                        <td class="fw-semibold">${actVal}</td>
                        <td class="fw-bold text-primary fs-6">${predVal}</td>
                        <td class="text-secondary font-monospace">${resErr > 0 ? '+' : ''}${resErr}</td>
                        <td class="text-end"><span class="badge ${badgeClass} border">${varPctStr.includes('%') ? varPctStr : varPctStr + '%'}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                thead.innerHTML = `
                    <tr>
                        <th style="width: 70px;"># Record</th>
                        <th>Actual Class</th>
                        <th>Predicted Class</th>
                        <th>Confidence</th>
                        <th class="text-end">Match</th>
                    </tr>
                `;
                samplePreds.forEach(p => {
                    const tr = document.createElement('tr');
                    const isMatch = (p.actual_class === p.predicted_class);
                    tr.innerHTML = `
                        <td class="text-secondary font-monospace">#${p.record_id || 1}</td>
                        <td class="fw-semibold">${p.actual_class || p.actual || '--'}</td>
                        <td class="fw-bold text-primary">${p.predicted_class || p.predicted || '--'}</td>
                        <td><span class="badge bg-info-subtle text-info border">${p.confidence_pct || 85}%</span></td>
                        <td class="text-end">${isMatch ? '<span class="badge bg-success-subtle text-success border">Match</span>' : '<span class="badge bg-danger-subtle text-danger border">Mismatch</span>'}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        // Instant Single-Record Predictor Input Fields
        const instantInputsRow = document.getElementById('step7InstantInputsRow');
        const instantResultBox = document.getElementById('step7InstantPredictionResult');
        const btnCalculate = document.getElementById('btnStep7CalculatePrediction');

        if (instantResultBox) instantResultBox.classList.add('d-none');

        if (instantInputsRow) {
            instantInputsRow.innerHTML = '';
            const coefs = result.coefficients || {};
            const feats = result.feature_columns || Object.keys(coefs);

            if (feats.length === 0) {
                instantInputsRow.innerHTML = '<div class="col-12 text-muted small">No input feature parameters required for this model.</div>';
            } else {
                feats.forEach(feat => {
                    const coef = (coefs[feat] !== undefined) ? coefs[feat] : 0;
                    const col = document.createElement('div');
                    col.className = 'col-6 col-md-3';
                    col.innerHTML = `
                        <label class="form-label extra-small text-secondary mb-1 font-monospace fw-semibold text-truncate w-100" title="${feat}">
                            ${feat} ${coef !== 0 ? `<span class="badge bg-light text-secondary border font-monospace ms-1" style="font-size:0.65rem;">β: ${coef >= 0 ? '+' : ''}${coef}</span>` : ''}
                        </label>
                        <input type="number" step="any" class="form-control form-control-sm step7-instant-input" data-feature="${feat}" placeholder="Enter ${feat}">
                    `;
                    instantInputsRow.appendChild(col);
                });
            }
        }

        if (btnCalculate) {
            btnCalculate.onclick = function () {
                if (!result || !result.coefficients || result.intercept === undefined) {
                    if (instantResultBox) {
                        instantResultBox.classList.remove('d-none');
                        instantResultBox.className = 'mt-2 p-2 rounded-2 bg-info-subtle text-info border border-info-subtle fw-bold text-center';
                        instantResultBox.innerHTML = `Model evaluation complete. Model: ${result.model_name || 'Active ML Model'}.`;
                    }
                    return;
                }

                const intercept = parseFloat(result.intercept) || 0;
                let predictedVal = intercept;
                const coefs = result.coefficients || {};
                const inputElems = document.querySelectorAll('.step7-instant-input');
                let inputSummary = [];

                inputElems.forEach(inp => {
                    const featName = inp.getAttribute('data-feature');
                    const val = parseFloat(inp.value) || 0;
                    const coef = parseFloat(coefs[featName]) || 0;
                    predictedVal += (val * coef);
                    inputSummary.push(`${featName}=${val}`);
                });

                const formattedVal = Number.isInteger(predictedVal) ? predictedVal : predictedVal.toFixed(4);

                if (instantResultBox) {
                    instantResultBox.classList.remove('d-none');
                    instantResultBox.className = 'mt-2 p-2.5 rounded-2 bg-success-subtle text-success border border-success-subtle text-center shadow-sm';
                    instantResultBox.innerHTML = `
                        <div class="small fw-semibold text-secondary mb-1">Instant Single-Record Prediction Result (&hat;y)</div>
                        <div class="fs-4 fw-bold text-success mb-1">${result.target_column || 'Target'}: <span class="badge bg-success text-white fs-4 font-monospace px-3 py-1 me-1">${formattedVal}</span></div>
                        <div class="extra-small text-muted">Calculated via equation: &hat;y = ${intercept} + &sum; (&beta;<sub>i</sub> &times; X<sub>i</sub>) using inputs [${inputSummary.join(', ')}]</div>
                    `;
                }
            };
        }
    }

    function renderMlPlotlyCharts(result) {
        const chartContainer = document.getElementById('mlPlotlyContainer');
        const btnTabScatter = document.getElementById('btnTabScatter');
        const btnTabResidual = document.getElementById('btnTabResidual');
        const btnTabCoef = document.getElementById('btnTabCoef');

        if (!chartContainer || !window.Plotly) return;

        function plotChart(chartPayload) {
            if (!chartPayload || !chartPayload.data) return;
            try {
                window.Plotly.newPlot(chartContainer, chartPayload.data, chartPayload.layout, { responsive: true, displayModeBar: true });
            } catch (e) {
                console.error('Plotly ML render error:', e);
            }
        }

        // Default: Scatter Plot
        currentActiveChartType = 'scatter';
        if (btnTabScatter) btnTabScatter.classList.add('active');
        if (btnTabResidual) btnTabResidual.classList.remove('active');
        if (btnTabCoef) btnTabCoef.classList.remove('active');
        plotChart(result.plotly_chart);

        // Tab click handlers
        if (btnTabScatter) {
            btnTabScatter.onclick = () => {
                btnTabScatter.classList.add('active');
                if (btnTabResidual) btnTabResidual.classList.remove('active');
                if (btnTabCoef) btnTabCoef.classList.remove('active');
                plotChart(result.plotly_chart);
            };
        }
        if (btnTabResidual) {
            btnTabResidual.onclick = () => {
                btnTabResidual.classList.add('active');
                if (btnTabScatter) btnTabScatter.classList.remove('active');
                if (btnTabCoef) btnTabCoef.classList.remove('active');
                plotChart(result.residual_chart || result.plotly_chart);
            };
        }
        if (btnTabCoef) {
            btnTabCoef.onclick = () => {
                btnTabCoef.classList.add('active');
                if (btnTabScatter) btnTabScatter.classList.remove('active');
                if (btnTabResidual) btnTabResidual.classList.remove('active');
                plotChart(result.coef_chart || result.plotly_chart);
            };
        }
    }

    function renderHumanExplanations(result) {
        const humanExpSection = document.getElementById('mlHumanExplanationsSection');
        const expR2Text = document.getElementById('expR2Text');
        const expErrorText = document.getElementById('expErrorText');
        const expGraphGuideList = document.getElementById('expGraphGuideList');
        const expSlopesContainer = document.getElementById('expSlopesContainer');

        if (!result.human_explanations || (result.model_type && result.model_type !== 'regression')) {
            if (humanExpSection) humanExpSection.classList.add('d-none');
            return;
        }

        if (humanExpSection) humanExpSection.classList.remove('d-none');
        const hExp = result.human_explanations;

        if (expR2Text) expR2Text.innerHTML = hExp.r2_explanation || 'Variance explained calculated.';
        if (expErrorText) expErrorText.innerHTML = hExp.error_explanation || 'Average deviation metrics.';

        if (expGraphGuideList) {
            expGraphGuideList.innerHTML = '';
            const g = hExp.graph_guide || {};
            if (g.scatter) expGraphGuideList.innerHTML += `<li><i class="bi bi-graph-up text-primary me-1.5"></i> ${g.scatter}</li>`;
            if (g.residual) expGraphGuideList.innerHTML += `<li><i class="bi bi-activity text-danger me-1.5"></i> ${g.residual}</li>`;
            if (g.coefficients) expGraphGuideList.innerHTML += `<li><i class="bi bi-bar-chart-steps text-success me-1.5"></i> ${g.coefficients}</li>`;
        }

        if (expSlopesContainer) {
            expSlopesContainer.innerHTML = '';
            const slopes = hExp.slopes || [];
            if (slopes.length === 0) {
                expSlopesContainer.innerHTML = '<span class="text-muted">No individual predictor slopes available.</span>';
            } else {
                slopes.forEach(sText => {
                    const div = document.createElement('div');
                    div.className = 'py-1 border-bottom border-secondary-subtle';
                    div.innerHTML = `<i class="bi bi-caret-right-fill text-primary me-1"></i> ${sText}`;
                    expSlopesContainer.appendChild(div);
                });
            }
        }
    }

    function renderFeatureImportances(result) {
        const importanceSection = document.getElementById('mlImportanceSection');
        const importanceBars = document.getElementById('mlImportanceBars');
        const importanceTitle = document.getElementById('mlImportanceTitle');

        if (result.feature_importances && Object.keys(result.feature_importances).length > 0) {
            if (importanceSection) importanceSection.classList.remove('d-none');
            if (importanceTitle) importanceTitle.textContent = 'Key Drivers & Relative Impact Weights';
            if (importanceBars) {
                importanceBars.innerHTML = '';
                const entries = Object.entries(result.feature_importances);
                entries.forEach(([feat, imp]) => {
                    const pct = Math.round(imp * 100);
                    const row = document.createElement('div');
                    row.className = 'mb-2';
                    row.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center mb-1 small">
                            <span class="fw-semibold font-monospace">${feat}</span>
                            <span class="text-secondary fw-bold">${pct}% impact weight</span>
                        </div>
                        <div class="progress" style="height: 7px;">
                            <div class="progress-bar bg-primary" role="progressbar" style="width: ${pct}%;" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                    `;
                    importanceBars.appendChild(row);
                });
            }
        } else if (result.cluster_profiles) {
            if (importanceSection) importanceSection.classList.remove('d-none');
            if (importanceTitle) importanceTitle.textContent = 'Customer / Entity Cluster Cohort Profiles';
            if (importanceBars) {
                importanceBars.innerHTML = '<div class="row g-2">';
                result.cluster_profiles.forEach(prof => {
                    const col = document.createElement('div');
                    col.className = 'col-12 col-md-4';
                    col.innerHTML = `
                        <div class="p-2.5 rounded-2 border bg-body">
                            <div class="d-flex justify-content-between align-items-center mb-1.5">
                                <span class="badge bg-primary">${prof.cluster_name}</span>
                                <span class="small fw-semibold text-secondary">${prof.size_count} records (${prof.size_pct}%)</span>
                            </div>
                            <div class="small text-muted font-monospace" style="font-size:0.75rem;">
                                ${Object.entries(prof.feature_means || {}).slice(0, 3).map(([k, v]) => `<div>${k}: <strong>${v}</strong></div>`).join('')}
                            </div>
                        </div>
                    `;
                    importanceBars.querySelector('.row').appendChild(col);
                });
            }
        } else {
            if (importanceSection) importanceSection.classList.add('d-none');
        }
    }

    function renderPredictionsTable(result) {
        const thead = document.getElementById('mlPredictionsThead');
        const tbody = document.getElementById('mlPredictionsTbody');
        const badge = document.getElementById('mlPredictionsCountBadge');
        const tableTitle = document.getElementById('mlTableTitle');
        const modality = result.model_type || currentMlModality;
        const predictions = result.sample_predictions || [];

        if (badge) badge.textContent = `${predictions.length} Predictions`;
        if (tableTitle) {
            tableTitle.textContent = `${result.model_name || 'Model'} Predictions & Decision Table`;
        }

        if (!thead || !tbody) return;
        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (predictions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No prediction records available.</td></tr>';
            return;
        }

        if (modality === 'regression') {
            thead.innerHTML = `
                <tr>
                    <th style="width: 70px;"># Record</th>
                    <th>Actual ${result.target_column || 'Value'}</th>
                    <th>Predicted (Linear OLS)</th>
                    <th>Residual Error</th>
                    <th>Variance Error %</th>
                    <th class="text-end">Status</th>
                </tr>
            `;
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                const actVal = (p.actual_value !== undefined) ? p.actual_value : ((p.actual !== undefined) ? p.actual : '--');
                const predVal = (p.predicted_value !== undefined) ? p.predicted_value : ((p.predicted !== undefined) ? p.predicted : '--');
                const resErr = (p.residual_error !== undefined) ? p.residual_error : ((p.error !== undefined) ? p.error : 0);
                const varPctStr = (p.variance_pct !== undefined) ? String(p.variance_pct) : ((p.pct_error !== undefined) ? `${p.pct_error}%` : '0.0%');
                const errPct = parseFloat(varPctStr) || 0;
                const badgeClass = errPct <= 10 ? 'bg-success-subtle text-success' : (errPct <= 25 ? 'bg-warning-subtle text-warning' : 'bg-danger-subtle text-danger');
                const statusTag = p.status || (errPct <= 10 ? 'High Precision' : (errPct <= 25 ? 'Acceptable' : 'Evaluated'));

                tr.innerHTML = `
                    <td class="text-secondary">#${p.record_id || 1}</td>
                    <td class="fw-bold">${actVal}</td>
                    <td class="text-primary fw-bold">${predVal}</td>
                    <td class="text-secondary">${resErr > 0 ? '+' : ''}${resErr}</td>
                    <td><span class="badge ${badgeClass} border">${varPctStr.includes('%') ? varPctStr : varPctStr + '%'}</span></td>
                    <td class="text-end"><span class="badge bg-secondary-subtle text-secondary border">${statusTag}</span></td>
                `;
                tbody.appendChild(tr);
            });
        } else if (modality === 'classification') {
            thead.innerHTML = `
                <tr>
                    <th style="width: 70px;"># Record</th>
                    <th>Actual Class</th>
                    <th>Predicted Class</th>
                    <th>Model Confidence</th>
                    <th class="text-end">Prediction Status</th>
                </tr>
            `;
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                const isCorrect = (p.is_correct !== undefined) ? p.is_correct : (p.actual_class === p.predicted_class);
                const statusBadge = isCorrect
                    ? '<span class="badge bg-success-subtle text-success border"><i class="bi bi-check-circle me-1"></i> Correct Match</span>'
                    : '<span class="badge bg-danger-subtle text-danger border"><i class="bi bi-x-circle me-1"></i> Misclassified</span>';
                tr.innerHTML = `
                    <td class="text-secondary">#${p.record_id || 1}</td>
                    <td class="fw-semibold">${p.actual_class !== undefined ? p.actual_class : (p.actual || '--')}</td>
                    <td class="fw-bold text-primary">${p.predicted_class !== undefined ? p.predicted_class : (p.predicted || '--')}</td>
                    <td><span class="badge bg-info-subtle text-info border">${p.confidence_pct || 85}% Confidence</span></td>
                    <td class="text-end">${statusBadge}</td>
                `;
                tbody.appendChild(tr);
            });
        } else if (modality === 'clustering') {
            thead.innerHTML = `
                <tr>
                    <th style="width: 70px;"># Record</th>
                    <th>Assigned Cluster</th>
                    <th>Cluster Cohort</th>
                    <th>Proximity Distance</th>
                    <th class="text-end">Key Profile Features</th>
                </tr>
            `;
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                const clName = p.cluster_name || p.assigned_cluster || 'Segment 1';
                tr.innerHTML = `
                    <td class="text-secondary">#${p.record_id || 1}</td>
                    <td><span class="badge bg-primary-subtle text-primary border fw-bold">${p.assigned_cluster || clName}</span></td>
                    <td class="fw-semibold">${clName}</td>
                    <td class="text-secondary">${p.distance_to_center || 1.25}</td>
                    <td class="text-end text-muted small">${p.sample_features_summary || p.features_summary || '--'}</td>
                `;
                tbody.appendChild(tr);
            });
        } else if (modality === 'forecasting') {
            thead.innerHTML = `
                <tr>
                    <th>Future Timeline</th>
                    <th>Projected Value (${result.value_column || 'Metric'})</th>
                    <th>Lower 95% Confidence</th>
                    <th>Upper 95% Confidence</th>
                    <th>Period Growth %</th>
                    <th class="text-end">Trend Direction</th>
                </tr>
            `;
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                const isUp = p.trend_direction === 'Upward';
                const trendBadge = isUp
                    ? '<span class="badge bg-success-subtle text-success border"><i class="bi bi-arrow-up-right me-1"></i> Upward</span>'
                    : '<span class="badge bg-danger-subtle text-danger border"><i class="bi bi-arrow-down-right me-1"></i> Downward</span>';
                tr.innerHTML = `
                    <td class="fw-bold text-primary"><i class="bi bi-calendar-event me-1"></i> ${p.period}</td>
                    <td class="fw-bold fs-6 text-success">${p.projected_forecast}</td>
                    <td class="text-secondary">${p.lower_bound_95}</td>
                    <td class="text-secondary">${p.upper_bound_95}</td>
                    <td class="fw-semibold">${p.growth_trend}</td>
                    <td class="text-end">${trendBadge}</td>
                `;
                tbody.appendChild(tr);
            });
        } else if (modality === 'anomaly') {
            thead.innerHTML = `
                <tr>
                    <th style="width: 70px;"># Record</th>
                    <th>Outlier Score</th>
                    <th>Severity Rating</th>
                    <th>Primary Anomaly Driver</th>
                    <th class="text-end">Key Metric Values</th>
                </tr>
            `;
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                const isCrit = p.severity === 'Critical';
                const sevBadge = isCrit
                    ? '<span class="badge bg-danger text-white border"><i class="bi bi-fire me-1"></i> Critical Outlier</span>'
                    : '<span class="badge bg-warning text-dark border"><i class="bi bi-exclamation-triangle me-1"></i> High Risk</span>';
                tr.innerHTML = `
                    <td class="text-secondary">#${p.record_id || 1}</td>
                    <td class="fw-bold text-danger font-monospace">${p.anomaly_score}</td>
                    <td>${sevBadge}</td>
                    <td class="fw-semibold text-primary">${p.primary_driver || 'Multivariate deviation'}</td>
                    <td class="text-end text-muted small">${p.values_summary || '--'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    }

    // --- Saved Models & Instant Predictor Functions ---
    function updateSavedModelsBadge(dsId) {
        if (!dsId) return;
        fetch(`/api/ml/saved_models?dataset_id=${encodeURIComponent(dsId)}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && savedModelsCountBadge) {
                    savedModelsCountBadge.textContent = data.count || 0;
                }
            })
            .catch(err => console.error('Error updating saved models badge:', err));
    }

    function saveCurrentTrainedModel() {
        if (!currentMlResults || !currentMlResults.success) {
            showToast('Please train a regression model first before saving.', 'warning');
            return;
        }

        const dsId = activeDatasetId || (document.getElementById('datasetSelect') ? document.getElementById('datasetSelect').value : null);
        const defaultName = `Linear Model (${currentMlResults.target_column || 'Target'}) - R² ${currentMlResults.metrics?.r2_score || 0}`;
        const userCustomName = prompt('Enter a name for this saved model:', defaultName);

        if (userCustomName === null) return; // User cancelled

        const payload = {
            dataset_id: dsId,
            model_name: userCustomName.trim() || defaultName,
            model_data: currentMlResults
        };

        fetch('/api/ml/save_model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    showToast(resData.message || 'Model saved successfully!', 'success');
                    updateSavedModelsBadge(dsId);
                } else {
                    showToast(resData.message || 'Failed to save model.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error saving model:', err);
                showToast('Server error while saving model.', 'danger');
            });
    }

    function loadSavedModelsList() {
        const container = document.getElementById('savedModelsListContainer');
        const dsId = activeDatasetId || (document.getElementById('datasetSelect') ? document.getElementById('datasetSelect').value : null);
        if (!container) return;

        container.innerHTML = '<div class="text-center py-4 text-muted"><div class="spinner-border spinner-border-sm text-primary me-2"></div> Fetching saved models...</div>';

        fetch(`/api/ml/saved_models?dataset_id=${encodeURIComponent(dsId || '')}`)
            .then(res => res.json())
            .then(data => {
                if (!data.success || !data.models || data.models.length === 0) {
                    container.innerHTML = `
                        <div class="text-center py-5 text-muted">
                            <i class="bi bi-bookmark-dash fs-1 d-block mb-2 text-secondary opacity-50"></i>
                            <h6 class="fw-bold">No Saved Models Found</h6>
                            <p class="small mb-0">Train a Linear Regression model in ML Studio and click <strong>"Save Trained Model"</strong> to persist it here.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = '<div class="d-flex flex-column gap-3">';
                data.models.forEach(m => {
                    const card = document.createElement('div');
                    card.className = 'card border shadow-sm bg-body-tertiary';
                    card.innerHTML = `
                        <div class="card-body p-3">
                            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                                <div class="d-flex align-items-center gap-2">
                                    <span class="badge bg-success"><i class="bi bi-check-circle me-1"></i> Saved Model #${m.id}</span>
                                    <h6 class="fw-bold mb-0 text-body">${m.model_name}</h6>
                                </div>
                                <div class="d-flex align-items-center gap-1.5">
                                    <span class="badge bg-primary-subtle text-primary border">R² Score: ${m.metrics?.r2_score !== undefined ? m.metrics.r2_score : '--'}</span>
                                    <span class="badge bg-info-subtle text-info border">MAE: ${m.metrics?.mae !== undefined ? m.metrics.mae : '--'}</span>
                                </div>
                            </div>
                            <div class="p-2 rounded-2 bg-body font-monospace text-body small mb-2 text-break border">
                                <strong>Formula:</strong> ${m.formula_str || 'Target = β0 + β1X1...'}
                            </div>
                            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 small text-muted">
                                <div>
                                    <span class="me-3">Target: <strong class="text-body">${m.target_column}</strong></span>
                                    <span>Features (${(m.feature_columns || []).length}): <strong class="text-body">${(m.feature_columns || []).join(', ')}</strong></span>
                                </div>
                                <div class="d-flex align-items-center gap-2">
                                    <button class="btn btn-xs btn-outline-danger py-1 px-2 btn-delete-saved-model" data-model-id="${m.id}" title="Delete saved model">
                                        <i class="bi bi-trash"></i> Delete
                                    </button>
                                    <button class="btn btn-xs btn-primary py-1 px-2.5 fw-semibold btn-use-saved-model" data-model-id="${m.id}">
                                        <i class="bi bi-lightning-fill me-1"></i> Instant Predict
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    container.querySelector('.d-flex').appendChild(card);
                });

                // Attach button handlers inside saved models list
                container.querySelectorAll('.btn-use-saved-model').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const mId = parseInt(this.getAttribute('data-model-id'));
                        const mObj = data.models.find(x => x.id === mId);
                        if (mObj) {
                            loadSavedModelIntoPredictor(mObj);
                        }
                    });
                });

                container.querySelectorAll('.btn-delete-saved-model').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const mId = parseInt(this.getAttribute('data-model-id'));
                        if (confirm('Are you sure you want to delete this saved model?')) {
                            fetch(`/api/ml/saved_models/${mId}`, { method: 'DELETE' })
                                .then(r => r.json())
                                .then(res => {
                                    if (res.success) {
                                        showToast('Saved model deleted.', 'info');
                                        loadSavedModelsList();
                                        updateSavedModelsBadge(dsId);
                                    } else {
                                        showToast(res.message || 'Failed to delete model.', 'danger');
                                    }
                                });
                        }
                    });
                });
            })
            .catch(err => {
                console.error('Error fetching saved models list:', err);
                container.innerHTML = '<div class="text-danger small p-3 text-center">Failed to load saved models from server.</div>';
            });
    }

    function loadSavedModelIntoPredictor(model) {
        selectedSavedModel = model;
        const titleEl = document.getElementById('instantPredictModelTitle');
        const targetBadge = document.getElementById('instantPredictTargetBadge');
        const formulaEl = document.getElementById('instantPredictFormulaText');
        const inputsContainer = document.getElementById('instantPredictInputsContainer');
        const btnRunInstant = document.getElementById('btnRunInstantPredict');
        const resultCard = document.getElementById('instantPredictResultCard');

        if (titleEl) titleEl.textContent = `Instant Predictor: ${model.model_name}`;
        if (targetBadge) targetBadge.textContent = `Target Column: ${model.target_column}`;
        if (formulaEl) formulaEl.textContent = `Equation: ${model.formula_str}`;

        if (resultCard) resultCard.classList.add('d-none');

        if (inputsContainer) {
            inputsContainer.innerHTML = '<div class="row g-3">';
            const features = model.feature_columns || [];
            features.forEach(feat => {
                const coef = (model.coefficients || {})[feat] || 0;
                const col = document.createElement('div');
                col.className = 'col-12 col-md-6';
                col.innerHTML = `
                    <label class="form-label small fw-semibold text-secondary mb-1">
                        ${feat} <span class="badge bg-secondary-subtle text-secondary font-monospace" style="font-size:0.7rem;">Slope: ${coef >= 0 ? '+' : ''}${coef}</span>
                    </label>
                    <input type="number" step="any" class="form-control form-control-sm instant-feature-input" data-feature="${feat}" placeholder="Enter numerical value for ${feat}" required>
                `;
                inputsContainer.querySelector('.row').appendChild(col);
            });
        }

        if (btnRunInstant) btnRunInstant.disabled = false;

        // Switch Tab to Instant Predictor
        const tabEl = document.getElementById('tab-instant-predict');
        if (tabEl && typeof bootstrap !== 'undefined') {
            const bsTab = bootstrap.Tab.getOrCreateInstance(tabEl);
            bsTab.show();
        }
    }

    function runInstantPrediction(e) {
        if (e) e.preventDefault();
        if (!selectedSavedModel) {
            showToast('Please select a saved model first.', 'warning');
            return;
        }

        const inputElements = document.querySelectorAll('.instant-feature-input');
        const inputFeatures = {};
        inputElements.forEach(inp => {
            const feat = inp.getAttribute('data-feature');
            const val = parseFloat(inp.value);
            inputFeatures[feat] = isNaN(val) ? 0.0 : val;
        });

        const payload = {
            model_id: selectedSavedModel.id,
            input_features: inputFeatures
        };

        fetch('/api/ml/predict_saved', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    renderInstantPredictionResult(data);
                    showToast('Instant prediction computed successfully!', 'success');
                } else {
                    showToast(data.message || 'Instant prediction failed.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error running instant prediction:', err);
                showToast('Server error while predicting with saved model.', 'danger');
            });
    }

    function renderInstantPredictionResult(data) {
        const resultCard = document.getElementById('instantPredictResultCard');
        const targetName = document.getElementById('ipTargetName');
        const outputVal = document.getElementById('instantPredictOutputValue');
        const breakdownList = document.getElementById('instantPredictBreakdownList');

        if (!resultCard) return;

        if (targetName) targetName.textContent = data.target_column || 'Target';
        if (outputVal) outputVal.textContent = data.predicted_value;

        if (breakdownList && data.breakdown) {
            breakdownList.innerHTML = '';
            data.breakdown.forEach(b => {
                const div = document.createElement('div');
                div.className = 'd-flex justify-content-between py-1 border-bottom border-success-subtle';
                if (b.factor === 'Baseline Intercept') {
                    div.innerHTML = `<span>Baseline (β0 Intercept):</span> <strong class="text-body">${b.contribution}</strong>`;
                } else {
                    div.innerHTML = `<span>${b.factor} (${b.input_value} × ${b.coefficient}):</span> <strong class="${b.contribution >= 0 ? 'text-success' : 'text-danger'}">${b.contribution >= 0 ? '+' : ''}${b.contribution}</strong>`;
                }
                breakdownList.appendChild(div);
            });
        }

        resultCard.classList.remove('d-none');
    }

    // Attach click handlers to all 5 ML Tool Cards & Buttons
    function initMlToolCardListeners() {
        const toolCards = document.querySelectorAll('.dn-clickable-tool[data-tool]');
        toolCards.forEach(card => {
            card.addEventListener('click', function () {
                const modality = this.getAttribute('data-tool');
                if (!modality) return;

                syncMlModalControls(modality);

                if (mlStudioModalEl && typeof bootstrap !== 'undefined') {
                    const bsModal = bootstrap.Modal.getOrCreateInstance(mlStudioModalEl);
                    bsModal.show();
                }

                fetchMlOptionsAndRun(modality, true);
            });
        });

        mlNavButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const modality = this.getAttribute('data-modality');
                syncMlModalControls(modality);
                fetchMlOptionsAndRun(modality, true);
            });
        });

        if (btnRunMlStudio) {
            btnRunMlStudio.addEventListener('click', () => {
                executeMlModel();
            });
        }

        if (btnResetMlDefaults) {
            btnResetMlDefaults.addEventListener('click', () => {
                if (currentMlOptions) {
                    populateMlColumnOptions(currentMlOptions, currentMlModality);
                    showToast('Reset feature inputs to automated ML recommendations.', 'info');
                }
            });
        }

        // Smart Auto-Select Features Button
        if (btnSmartSelectFeatures) {
            btnSmartSelectFeatures.addEventListener('click', () => {
                if (!mlFeaturePillsContainer) return;
                const checkboxes = mlFeaturePillsContainer.querySelectorAll('input[type="checkbox"]');
                let selectedCount = 0;
                checkboxes.forEach(cb => {
                    const bType = cb.getAttribute('data-badge');
                    // Check if high/moderate/weak relevance (not secondary)
                    if (bType === 'success' || bType === 'primary' || bType === 'warning') {
                        cb.checked = true;
                        selectedCount++;
                    } else {
                        cb.checked = false;
                    }
                });
                updateSelectedFeaturesCount();
                showToast(`Smart-selected ${selectedCount} continuous features with logical correlation to target!`, 'success');
            });
        }

        // Target column change listener to update correlation badges
        if (mlTargetColSelect) {
            mlTargetColSelect.addEventListener('change', () => {
                if (currentMlOptions) {
                    const dsId = activeDatasetId || (document.getElementById('datasetSelect') ? document.getElementById('datasetSelect').value : null);
                    if (dsId) {
                        fetch(`/api/ml/options?dataset_id=${encodeURIComponent(dsId)}`)
                            .then(r => r.json())
                            .then(resData => {
                                if (resData.success) {
                                    populateMlColumnOptions(resData, currentMlModality);
                                }
                            });
                    }
                }
            });
        }

        // Save Current Model Button
        if (btnSaveCurrentModel) {
            btnSaveCurrentModel.addEventListener('click', () => {
                saveCurrentTrainedModel();
            });
        }

        // Saved Models Modal Opener
        if (btnOpenSavedModelsModal) {
            btnOpenSavedModelsModal.addEventListener('click', () => {
                const savedModalEl = document.getElementById('dnSavedModelsModal');
                if (savedModalEl && typeof bootstrap !== 'undefined') {
                    const bsModal = bootstrap.Modal.getOrCreateInstance(savedModalEl);
                    bsModal.show();
                    loadSavedModelsList();
                }
            });
        }

        // Instant Predictor Form Submit
        const instantPredictForm = document.getElementById('instantPredictForm');
        if (instantPredictForm) {
            instantPredictForm.addEventListener('submit', runInstantPrediction);
        }

        // Table search filter
        if (mlSearchPredictionsInput) {
            mlSearchPredictionsInput.addEventListener('input', function () {
                const filter = this.value.toLowerCase().trim();
                const rows = document.querySelectorAll('#mlPredictionsTbody tr');
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(filter) ? '' : 'none';
                });
            });
        }

        // Export Predictions CSV
        if (btnExportPredictionsCsv) {
            btnExportPredictionsCsv.addEventListener('click', () => {
                if (!currentMlResults || !currentMlResults.sample_predictions || currentMlResults.sample_predictions.length === 0) {
                    showToast('No prediction data available to export.', 'warning');
                    return;
                }
                const preds = currentMlResults.sample_predictions;
                const headers = Object.keys(preds[0]);
                const csvRows = [headers.join(',')];
                preds.forEach(p => {
                    const values = headers.map(h => {
                        const str = String(p[h] !== undefined ? p[h] : '').replace(/"/g, '""');
                        return `"${str}"`;
                    });
                    csvRows.push(values.join(','));
                });
                const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `DataNova_${currentMlModality}_Predictions_${Date.now()}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showToast('Predictions exported successfully as CSV!', 'success');
            });
        }
    }

    initMlToolCardListeners();


    // --- Topbar Global Search Activation ---
    function initAnalystTopbarSearch() {
        const searchInput = document.getElementById('analystTopbarSearchInput');
        const searchDropdown = document.getElementById('analystSearchDropdown');
        const searchDropdownContent = document.getElementById('analystSearchDropdownContent');
        const searchMatchCount = document.getElementById('analystSearchMatchCount');
        const searchClearBtn = document.getElementById('analystSearchClearBtn');

        if (!searchInput || !searchDropdown || !searchDropdownContent) return;

        const defaultSearchIndex = [
            { title: 'Dashboard Overview', subtitle: 'High-level KPIs, activity metrics, and platform status.', tag: 'Navigation', icon: 'bi-grid-1x2-fill', target: '#main-overview' },
            { title: '1. Upload Dataset', subtitle: 'Upload CSV, XLSX, JSON or SQLite database file.', tag: 'Step 1', icon: 'bi-cloud-upload', target: '#upload' },
            { title: '2. Raw Data Preview', subtitle: 'Inspect raw table data, column dtypes, summary, and head/tail records.', tag: 'Step 2', icon: 'bi-database', target: '#step-preview' },
            { title: '3. Data Cleaning & Preprocessing', subtitle: 'Handle missing values, duplicate removal, outlier IQR filter, encoding.', tag: 'Step 3', icon: 'bi-shield-check', target: '#step-cleaning' },
            { title: '4. Statistical EDA', subtitle: 'Descriptive statistics, skewness, kurtosis, distributions, quartile metrics.', tag: 'Step 4', icon: 'bi-search', target: '#step-eda' },
            { title: '5. Correlation Matrix', subtitle: 'Interactive heatmap, Pearson correlation coefficients, strong pairs.', tag: 'Step 5', icon: 'bi-grid-3x3', target: '#step-correlation' },
            { title: '6. Visualizations & Charts', subtitle: 'Plotly Bar, Line, Scatter, Pie, Histogram, Box, Heatmap visualizer.', tag: 'Step 6', icon: 'bi-bar-chart-line', target: '#step-visualization' },
            { title: '7. AI Insights & ML', subtitle: 'Automated AI anomaly detection, business insights, key drivers.', tag: 'Step 7', icon: 'bi-stars', target: '#step-insights' },
            { title: 'ML Predictive Studio', subtitle: 'Regression, Classification, Clustering, Forecasting, Anomaly detection.', tag: 'Machine Learning', icon: 'bi-cpu-fill', action: 'ml_studio' },
            { title: '8. Reports & Export', subtitle: 'Download PDF, Word docx, PowerPoint pptx, HTML, and Excel reports.', tag: 'Step 8', icon: 'bi-file-earmark-bar-graph', target: '#step-reports' },
            { title: '9. Python Code Studio (.ipynb)', subtitle: 'Interactive Jupyter code execution, visual pipelines, data exports.', tag: 'Step 9', icon: 'bi-filetype-py', target: '#step-code' },
            { title: 'Ask Your Data (AI Chat)', subtitle: 'Query dataset with natural language, generate SQL & instant answers.', tag: 'AI Assistant', icon: 'bi-chat-dots-fill', action: 'ask_data' },
            { title: 'Assigned Work & Tasks', subtitle: 'Manager task assignments, deadlines, remarks, and status updates.', tag: 'Workload', icon: 'bi-check2-square', target: '#assignedTasksPanel' },
            { title: 'Shared Dashboards', subtitle: 'Team dashboard sharing, access control, and collaborative exploration.', tag: 'Collaboration', icon: 'bi-share-fill', target: '#sharedDashboardsPanel' },
            { title: 'Help & Documentation', subtitle: 'Analyst keyboard shortcuts, analysis guides, and troubleshooting.', tag: 'Help', icon: 'bi-question-circle', action: 'help_modal' }
        ];

        let activeIndex = -1;

        function renderResults(query) {
            query = (query || '').toLowerCase().trim();
            if (!query) {
                searchDropdown.classList.add('d-none');
                if (searchClearBtn) searchClearBtn.classList.add('d-none');
                return;
            }

            if (searchClearBtn) searchClearBtn.classList.remove('d-none');
            searchDropdown.classList.remove('d-none');

            // Collect items to search
            let items = [...defaultSearchIndex];

            // Add active columns if available
            if (activeDatasetSummary && activeDatasetSummary.columns) {
                activeDatasetSummary.columns.forEach(col => {
                    const colName = typeof col === 'string' ? col : (col.name || '');
                    const colType = typeof col === 'object' && col.dtype ? col.dtype : 'feature';
                    if (colName) {
                        items.push({
                            title: `Column: ${colName}`,
                            subtitle: `Type: ${colType} &mdash; Click to view in Raw Preview & EDA`,
                            tag: 'Dataset Column',
                            icon: 'bi-layout-three-columns',
                            target: '#step-preview'
                        });
                    }
                });
            }

            const matches = items.filter(item => {
                return item.title.toLowerCase().includes(query) ||
                    item.subtitle.toLowerCase().includes(query) ||
                    item.tag.toLowerCase().includes(query);
            });

            if (searchMatchCount) {
                searchMatchCount.textContent = `${matches.length} match${matches.length === 1 ? '' : 'es'}`;
            }

            if (matches.length === 0) {
                searchDropdownContent.innerHTML = `
                    <div class="text-center py-3 text-muted">
                        <i class="bi bi-search fs-4 d-block mb-1 opacity-50"></i>
                        <small>No matches found for "<strong>${escapeHtml(query)}</strong>"</small>
                    </div>`;
                activeIndex = -1;
                return;
            }

            searchDropdownContent.innerHTML = matches.map((m, idx) => `
                <div class="dn-search-result-item d-flex align-items-center gap-2 p-2 rounded mb-1 text-decoration-none text-body" 
                     data-index="${idx}" 
                     data-target="${m.target || ''}" 
                     data-action="${m.action || ''}" 
                     style="cursor: pointer; transition: background 0.15s ease;">
                    <div class="p-2 rounded bg-primary-subtle text-primary d-flex align-items-center justify-content-center" style="width: 32px; height: 32px; font-size: 0.95rem;">
                        <i class="bi ${m.icon}"></i>
                    </div>
                    <div class="flex-grow-1 overflow-hidden">
                        <div class="d-flex align-items-center justify-content-between">
                            <strong class="small text-truncate">${highlightMatch(m.title, query)}</strong>
                            <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.65rem;">${m.tag}</span>
                        </div>
                        <div class="text-muted text-truncate" style="font-size: 0.75rem;">${m.subtitle}</div>
                    </div>
                </div>
            `).join('');

            activeIndex = -1;

            // Bind click to each result item
            searchDropdownContent.querySelectorAll('.dn-search-result-item').forEach(el => {
                el.addEventListener('click', function () {
                    executeSearchAction(this.getAttribute('data-target'), this.getAttribute('data-action'));
                });
                el.addEventListener('mouseenter', function () {
                    searchDropdownContent.querySelectorAll('.dn-search-result-item').forEach(r => r.classList.remove('bg-body-secondary'));
                    this.classList.add('bg-body-secondary');
                    activeIndex = parseInt(this.getAttribute('data-index'), 10);
                });
            });
        }

        function highlightMatch(text, query) {
            if (!query) return escapeHtml(text);
            const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            return escapeHtml(text).replace(regex, '<mark class="p-0 bg-warning-subtle fw-bold text-body">$1</mark>');
        }

        function executeSearchAction(target, action) {
            // Hide dropdown & clear input
            searchDropdown.classList.add('d-none');
            searchInput.value = '';
            if (searchClearBtn) searchClearBtn.classList.add('d-none');

            if (action === 'ml_studio') {
                if (mlStudioModalEl && typeof bootstrap !== 'undefined') {
                    const bsModal = bootstrap.Modal.getOrCreateInstance(mlStudioModalEl);
                    bsModal.show();
                    syncMlModalControls('regression');
                    fetchMlOptionsAndRun('regression', true);
                }
                return;
            }

            if (action === 'ask_data') {
                const askModal = document.getElementById('dnAskDataModal') || document.getElementById('askDataModal');
                if (askModal && typeof bootstrap !== 'undefined') {
                    const bsModal = bootstrap.Modal.getOrCreateInstance(askModal);
                    bsModal.show();
                } else {
                    const askNav = document.getElementById('navAskYourData');
                    if (askNav) askNav.click();
                }
                return;
            }

            if (action === 'help_modal') {
                const helpModal = document.getElementById('analystHelpModal');
                if (helpModal && typeof bootstrap !== 'undefined') {
                    bootstrap.Modal.getOrCreateInstance(helpModal).show();
                }
                return;
            }

            if (target) {
                // Check if target is a nav section
                const navLink = document.querySelector(`.dn-sidebar-scroll a[href="${target}"]`);
                if (navLink) {
                    navLink.click();
                } else {
                    const el = document.querySelector(target);
                    if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            }
        }

        searchInput.addEventListener('input', function () {
            renderResults(this.value);
        });

        searchInput.addEventListener('focus', function () {
            if (this.value.trim()) renderResults(this.value);
        });

        if (searchClearBtn) {
            searchClearBtn.addEventListener('click', function () {
                searchInput.value = '';
                searchDropdown.classList.add('d-none');
                searchClearBtn.classList.add('d-none');
                searchInput.focus();
            });
        }

        // Keyboard navigation
        searchInput.addEventListener('keydown', function (e) {
            const items = searchDropdownContent.querySelectorAll('.dn-search-result-item');
            if (items.length === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = (activeIndex + 1) % items.length;
                updateActiveResult(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = (activeIndex - 1 + items.length) % items.length;
                updateActiveResult(items);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (activeIndex >= 0 && activeIndex < items.length) {
                    items[activeIndex].click();
                } else if (items.length > 0) {
                    items[0].click();
                }
            } else if (e.key === 'Escape') {
                searchDropdown.classList.add('d-none');
            }
        });

        function updateActiveResult(items) {
            items.forEach((item, idx) => {
                if (idx === activeIndex) {
                    item.classList.add('bg-body-secondary');
                    item.scrollIntoView({ block: 'nearest' });
                } else {
                    item.classList.remove('bg-body-secondary');
                }
            });
        }

        // Close on click outside
        document.addEventListener('click', function (e) {
            if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.classList.add('d-none');
            }
        });
    }

    initAnalystTopbarSearch();
    fetchAnalystAnalytics();

    // Wire Quick Ask & Modal buttons
    const btnQuickAsk = document.getElementById('btnQuickAsk');
    if (btnQuickAsk) {
        btnQuickAsk.addEventListener('click', function () {
            const askModal = document.getElementById('dnAskDataModal') || document.getElementById('askDataModal');
            if (askModal && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getOrCreateInstance(askModal).show();
            } else {
                const navAsk = document.getElementById('navAskYourData');
                if (navAsk) navAsk.click();
            }
        });
    }

    const btnUploadPanelPrevious = document.getElementById('btnUploadPanelPrevious');
    if (btnUploadPanelPrevious) {
        btnUploadPanelPrevious.addEventListener('click', function () {
            if (typeof fetchPreviousDatasets === 'function') {
                fetchPreviousDatasets();
            }
        });
    }

    // Global State Bus Listener for Analyst Dashboard
    if (window.DataNovaStateBus) {
        window.DataNovaStateBus.on('*', function (eventType) {
            if (eventType === 'MUTATION_TASK_ASSIGNED' || eventType === 'MUTATION_TASK_UPDATE') {
                refreshAnalystTasks();
            }
            if (eventType === 'MUTATION_DASHBOARD_SHARED') {
                fetchAnalystSharedDashboards();
            }
        });
    }

    // --- Compare Datasets Controller for Analyst Dashboard ---
    let compareDatasetsModalInstance = null;
    const compareModalEl = document.getElementById('dnCompareDatasetsModal');
    if (compareModalEl && typeof bootstrap !== 'undefined') {
        compareDatasetsModalInstance = bootstrap.Modal.getOrCreateInstance(compareModalEl);
    }

    function showCompareDatasetsModal() {
        if (!compareDatasetsModalInstance && compareModalEl && typeof bootstrap !== 'undefined') {
            compareDatasetsModalInstance = bootstrap.Modal.getOrCreateInstance(compareModalEl);
        }
        if (compareDatasetsModalInstance) {
            const alertEl = document.getElementById('compareDatasetsAlert');
            if (alertEl) alertEl.classList.add('d-none');
            const resContainer = document.getElementById('compareResultsContainer');
            if (resContainer) resContainer.classList.add('d-none');
            compareDatasetsModalInstance.show();
        }
    }

    document.querySelectorAll('[data-action="compare-data"], #navCompareDatasets').forEach(trigger => {
        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            showCompareDatasetsModal();
        });
    });

    const compareForm = document.getElementById('dnCompareDatasetsForm');
    if (compareForm) {
        compareForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const alertEl = document.getElementById('compareDatasetsAlert');
            const btnSubmit = document.getElementById('btnSubmitCompare');
            const resContainer = document.getElementById('compareResultsContainer');

            if (alertEl) alertEl.classList.add('d-none');
            if (resContainer) resContainer.classList.add('d-none');

            const file1Input = document.getElementById('compareFile1Input');
            const file2Input = document.getElementById('compareFile2Input');
            const ds1Input = document.getElementById('compareDs1Input');
            const ds2Input = document.getElementById('compareDs2Input');
            const gsheet1Input = document.getElementById('compareGSheet1Input');
            const gsheet2Input = document.getElementById('compareGSheet2Input');

            const file1 = file1Input && file1Input.files ? file1Input.files[0] : null;
            const file2 = file2Input && file2Input.files ? file2Input.files[0] : null;
            const ds1 = ds1Input ? ds1Input.value.trim() : '';
            const ds2 = ds2Input ? ds2Input.value.trim() : '';
            const gsheet1 = gsheet1Input ? gsheet1Input.value.trim() : '';
            const gsheet2 = gsheet2Input ? gsheet2Input.value.trim() : '';

            const hasFirst = Boolean(file1 || ds1 || gsheet1);
            const hasSecond = Boolean(file2 || ds2 || gsheet2);

            if (!hasFirst || !hasSecond) {
                if (alertEl) {
                    alertEl.textContent = "Please provide two datasets to compare (upload files, paste Google Sheet URLs, or enter dataset IDs).";
                    alertEl.classList.remove('d-none');
                }
                return;
            }

            const formData = new FormData();
            if (file1) formData.append('file1', file1);
            else if (gsheet1) formData.append('gsheet_url_1', gsheet1);
            else if (ds1) formData.append('dataset_id_1', ds1);

            if (file2) formData.append('file2', file2);
            else if (gsheet2) formData.append('gsheet_url_2', gsheet2);
            else if (ds2) formData.append('dataset_id_2', ds2);

            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Comparing...';
            }

            fetch('/api/compare_datasets', {
                method: 'POST',
                body: formData
            })
                .then(res => res.json())
                .then(data => {
                    if (btnSubmit) {
                        btnSubmit.disabled = false;
                        btnSubmit.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i>Run Comparison';
                    }

                    if (data && data.success) {
                        if (resContainer) resContainer.classList.remove('d-none');

                        // Headers
                        const h1 = document.getElementById('compHeadDs1');
                        const h2 = document.getElementById('compHeadDs2');
                        if (h1) h1.textContent = data.dataset_1_name || 'Dataset 1';
                        if (h2) h2.textContent = data.dataset_2_name || 'Dataset 2';

                        const n1 = document.getElementById('compOnlyName1');
                        const n2 = document.getElementById('compOnlyName2');
                        if (n1) n1.textContent = data.dataset_1_name || 'Dataset 1';
                        if (n2) n2.textContent = data.dataset_2_name || 'Dataset 2';

                        // Metrics
                        const m1 = data.ds1_metrics || {};
                        const m2 = data.ds2_metrics || {};

                        document.getElementById('compRows1').textContent = (m1.rows || 0).toLocaleString();
                        document.getElementById('compRows2').textContent = (m2.rows || 0).toLocaleString();

                        document.getElementById('compCols1').textContent = m1.cols || 0;
                        document.getElementById('compCols2').textContent = m2.cols || 0;

                        document.getElementById('compMem1').textContent = m1.memory_str || '0 KB';
                        document.getElementById('compMem2').textContent = m2.memory_str || '0 KB';

                        document.getElementById('compMiss1').textContent = (m1.missing_count || 0).toLocaleString();
                        document.getElementById('compMiss2').textContent = (m2.missing_count || 0).toLocaleString();

                        document.getElementById('compDup1').textContent = (m1.duplicates || 0).toLocaleString();
                        document.getElementById('compDup2').textContent = (m2.duplicates || 0).toLocaleString();

                        const q1 = m1.quality_score || 100;
                        const q2 = m2.quality_score || 100;
                        document.getElementById('compGrade1').innerHTML = `<span class="badge bg-primary-subtle text-primary border border-primary-subtle">${m1.quality_grade || 'A+'} (${q1})</span>`;
                        document.getElementById('compGrade2').innerHTML = `<span class="badge bg-info-subtle text-info border border-info-subtle">${m2.quality_grade || 'A+'} (${q2})</span>`;

                        // Pills
                        const common = data.common_columns || [];
                        const only1 = data.only_in_ds1 || [];
                        const only2 = data.only_in_ds2 || [];

                        document.getElementById('compCommonCount').textContent = common.length;
                        document.getElementById('compOnlyCount1').textContent = only1.length;
                        document.getElementById('compOnlyCount2').textContent = only2.length;

                        const commonContainer = document.getElementById('compCommonPills');
                        if (commonContainer) {
                            commonContainer.innerHTML = common.length ? common.map(c => `<span class="badge bg-success-subtle text-success border border-success-subtle">${c}</span>`).join('') : '<span class="small text-muted">None</span>';
                        }

                        const only1Container = document.getElementById('compOnly1Pills');
                        if (only1Container) {
                            only1Container.innerHTML = only1.length ? only1.map(c => `<span class="badge bg-primary-subtle text-primary border border-primary-subtle">${c}</span>`).join('') : '<span class="small text-muted">None</span>';
                        }

                        const only2Container = document.getElementById('compOnly2Pills');
                        if (only2Container) {
                            only2Container.innerHTML = only2.length ? only2.map(c => `<span class="badge bg-info-subtle text-info border border-info-subtle">${c}</span>`).join('') : '<span class="small text-muted">None</span>';
                        }

                        // Schema table
                        const schemaTbody = document.getElementById('compSchemaTableBody');
                        const schemaList = data.schema_comparison || [];
                        if (schemaTbody) {
                            if (schemaList.length > 0) {
                                schemaTbody.innerHTML = schemaList.map(item => {
                                    const matchBadge = item.match ?
                                        '<span class="badge bg-success-subtle text-success"><i class="bi bi-check-circle me-1"></i>Match</span>' :
                                        '<span class="badge bg-warning-subtle text-warning"><i class="bi bi-exclamation-triangle me-1"></i>Type Mismatch</span>';
                                    return `
                                        <tr>
                                            <td class="fw-semibold">${item.column}</td>
                                            <td><code>${item.type1}</code></td>
                                            <td><code>${item.type2}</code></td>
                                            <td>${matchBadge}</td>
                                        </tr>
                                    `;
                                }).join('');
                            } else {
                                schemaTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted small py-2">No overlapping schema to compare.</td></tr>';
                            }
                        }

                    } else {
                        if (alertEl) {
                            alertEl.textContent = data ? data.message || "Failed to compare datasets." : "Failed to compare datasets.";
                            alertEl.classList.remove('d-none');
                        }
                    }
                })
                .catch(err => {
                    console.error('Error comparing datasets:', err);
                    if (btnSubmit) {
                        btnSubmit.disabled = false;
                        btnSubmit.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i>Run Comparison';
                    }
                    if (alertEl) {
                        alertEl.textContent = "Server error while comparing datasets.";
                        alertEl.classList.remove('d-none');
                    }
                });
        });
    }
});