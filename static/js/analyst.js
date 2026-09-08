document.addEventListener('DOMContentLoaded', function () {

    /* ---------------------------------------------------------------------
       1. "Ask Your Data" Modal & Form Logic
       ------------------------------------------------------------------- */
    const askDataModal = document.getElementById("askDataModal");
    const askDataOverlay = document.getElementById("askDataOverlay");
    const closeAskDataBtn = document.getElementById("closeAskData");
    const openAskDataBtns = document.querySelectorAll(".dn-open-ask-modal");
    var askInput = document.getElementById('dnAskInput');

    function openAskModal(e) {
        e.preventDefault();
        if (askDataModal) askDataModal.classList.add("active");
        if (askDataOverlay) askDataOverlay.classList.add("active");
        setTimeout(() => {
            if (askInput) askInput.focus();
        }, 200);
        document.body.style.overflow = "hidden";
    }

    function closeAskModal() {
        if (askDataModal) askDataModal.classList.remove("active");
        if (askDataOverlay) askDataOverlay.classList.remove("active");
        document.body.style.overflow = "";
    }

    openAskDataBtns.forEach(btn => btn.addEventListener("click", openAskModal));
    if (closeAskDataBtn) closeAskDataBtn.addEventListener("click", closeAskModal);
    if (askDataOverlay) askDataOverlay.addEventListener("click", closeAskModal);

    // Suggested questions
    document.querySelectorAll('.dn-suggested-q').forEach(function (chip) {
        chip.addEventListener('click', function (e) {
            e.preventDefault(); // Prevent any default button behavior, especially if inside a form
            if (askInput) {
                askInput.value = chip.textContent.trim();
                askInput.focus();
            }
        });
    });

    // Close modal with ESC key
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && askDataModal && askDataModal.classList.contains("active")) {
            closeAskModal();
        }
    });

    var askForm = document.getElementById('dnAskForm');
    if (askForm) {
        askForm.addEventListener('submit', function (e) {
            e.preventDefault();
            // Placeholder only — chatbot is not connected to an API yet.
            const question = askInput.value.trim();
            if (!question) {
                showToast("Please enter a question.", "warning");
                return;
            }
            if (!activeDatasetId) {
                showToast("Please upload and select a dataset first.", "warning");
                return;
            }

            const askResultContainer = document.getElementById('dnAskResultContainer');
            const askButton = askForm.querySelector('button[type="submit"]');

            if (askButton) {
                askButton.disabled = true;
                askButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Asking...';
            }
            if (askResultContainer) {
                askResultContainer.style.display = 'block';
                askResultContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p class="text-muted mt-2">Getting answer from AI...</p></div>';
            }

            const langSelect = document.getElementById('dnAskLanguage');
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
                if (askResultContainer) {
                    if (data.success) {
                        // Add a copy button to the AI response
                        askResultContainer.innerHTML = `
                            <div class="dn-alert dn-alert-info position-relative">
                                <button class="btn btn-sm dn-btn-icon-only dn-copy-ai-answer-btn" title="Copy answer"><i class="bi bi-clipboard"></i></button>
                                <span class="dn-ai-answer-text">${data.answer}</span>
                            </div>
                        `;
                    } else {
                        askResultContainer.innerHTML = `<div class="dn-alert dn-alert-danger">${data.message || 'Failed to get an answer.'}</div>`
                    }
                }
            })
            .catch(err => {
                showFetchError('Ask Data AI', err);
                if (askResultContainer) {
                    askResultContainer.innerHTML = `<div class="dn-alert dn-alert-danger">Could not reach the server. Please try again.</div>`;
                }
            })
            .finally(() => {
                if (askButton) {
                    askButton.disabled = false;
                    askButton.innerHTML = '<i class="bi bi-send"></i> Ask';
                }
            });
        });
    }

    // Event listener for the dynamic "Copy AI Answer" button
    document.body.addEventListener('click', function(e) {
        const copyBtn = e.target.closest('.dn-copy-ai-answer-btn');
        if (copyBtn) {
            const answerContainer = copyBtn.closest('.dn-alert');
            const answerTextElement = answerContainer ? answerContainer.querySelector('.dn-ai-answer-text') : null;
            if (answerTextElement) {
                const textToCopy = answerTextElement.innerText;
                navigator.clipboard.writeText(textToCopy).then(() => {
                    // Temporarily change icon and text to show success
                    const icon = copyBtn.querySelector('i');
                    if (icon) icon.className = 'bi bi-clipboard-check-fill';
                    copyBtn.setAttribute('title', 'Copied!');
                    setTimeout(() => {
                        if (icon) icon.className = 'bi bi-clipboard';
                        copyBtn.setAttribute('title', 'Copy answer');
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy text: ', err);
                    showToast('Failed to copy answer.', 'danger');
                });
            }
        }
    });

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
                targetId = 'dnMissingValuePanel';
            } else if (actionText.includes('run eda')) {
                targetId = 'dnAutoEDAPanel';
            } else if (actionText.includes('ask ai')) {
                // This is handled by a different class, but we can add it here for consistency
                const openModalBtn = document.querySelector('.dn-open-ask-modal');
                if (openModalBtn) openModalBtn.click();
                return;
            }

            if (targetId) {
                const targetElement = document.getElementById(targetId);
                if (targetElement && targetElement.style.display !== 'none') {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else if (targetElement) {
                    showToast('Please upload a dataset to access this feature.', 'info');
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
    var correlationResultContainer = document.getElementById('dnCorrelationResultContainer');
    var correlationHeatmap = document.getElementById('dnCorrelationHeatmap');
    var scatterXSelect = document.getElementById('dnScatterX');
    var scatterYSelect = document.getElementById('dnScatterY');
    var generateScatterBtn = document.getElementById('dnGenerateScatterBtn');
    var scatterPlotResult = document.getElementById('dnScatterPlotResult');

    const processingLoader = document.getElementById('dnProcessingLoader');
    // Initialize activeDatasetId from a hidden input field, allowing persistence across reloads
    let activeDatasetId = document.getElementById('initialActiveDatasetId')?.value || null;
    let fullColumnInfo = []; // To store the complete list of columns
    let missingColumnInfo = []; // To store info about columns with missing values

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

        if (overviewPanel) overviewPanel.style.display = 'block';

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
                    const checkboxHtml = `
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" value="${col.name}" id="dup-check-${col.name}">
                            <label class="form-check-label" for="dup-check-${col.name}">
                                ${col.name}
                            </label>
                        </div>`;
                    duplicateColumnSelect.insertAdjacentHTML('beforeend', checkboxHtml);
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
                row.innerHTML = `
                    <td>${col.name}</td>
                    <td class="text-end">${col.count.toLocaleString()}</td>
                    <td class="text-end">${col.percentage}%</td>
                `;
                missingValueContent.appendChild(row);
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
        } else {
            if (missingValuePanel) missingValuePanel.style.display = 'none';
            if (missingValueActions) missingValueActions.style.display = 'none';
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

    function loadCurrentDataset() {
        fetch('/api/current_dataset')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.has_dataset !== false) {
                    populateDatasetWorkspace(data, data.file_name, false);
                }
            })
            .catch(error => showFetchError('loadCurrentDataset', error));
    }

    // Handle Drop Columns Confirmation
    const confirmDropBtn = document.getElementById('dnConfirmDropColumnsBtn');
    if (confirmDropBtn) {
        confirmDropBtn.addEventListener('click', function () {
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }

            const dropGrid = document.getElementById('dnDropColumnsGrid');
            if (!dropGrid) return;

            const selectedCols = Array.from(dropGrid.querySelectorAll('.dn-col-drop-check:checked')).map(chk => chk.value);
            if (selectedCols.length === 0) { alert('Please select at least one column to drop.'); return; }

            if (!confirm(`Are you sure you want to drop the following ${selectedCols.length} column(s)?\n\n${selectedCols.join(', ')}\n\nThis will update your dataset snapshot.`)) {
                return;
            }

            confirmDropBtn.disabled = true;
            confirmDropBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Dropping...';

            fetch('/api/drop_columns', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dataset_id: activeDatasetId,
                    columns: selectedCols
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Columns dropped successfully!', 'success');
                        populateDatasetWorkspace(data, data.file_name, false);
                        addTooltipsToStatsTable();
                        // Show download button after successful drop
                        const downloadBtn = document.getElementById('dnDownloadAfterDropBtn');
                        if (downloadBtn) {
                            downloadBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}?format=csv`;
                            downloadBtn.style.display = 'inline-flex';
                        }
                        if(confirmDropBtn) {
                            confirmDropBtn.style.display = 'none'; // Hide the drop button
                        }
                        if (data.recommended_charts) renderEdaCharts(data.recommended_charts);
                    } else {
                        showToast('Error dropping columns: ' + (data.message || 'Unknown error'), 'danger');
                    }
                })
                .catch(err => {
                    showFetchError('confirmDropBtn', err);
                    alert('An error occurred while dropping columns.');
                })
                .finally(() => {
                    confirmDropBtn.disabled = false;
                    confirmDropBtn.innerHTML = '<i class="bi bi-trash"></i> Drop Selected Columns';
                });
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

        // Handle "Upload Another" button click
        if (uploadAnotherBtn) {
            uploadAnotherBtn.addEventListener('click', function () {
                previewPanel.style.display = 'none';
                previewContent.innerHTML = '';
                overviewPanel.style.display = 'none'; // Hide overview as well
                columnInfoPanel.style.display = 'none'; // Hide column info
                columnInfoFooter.style.display = 'none'; // Hide button footer
                columnInfoContent.innerHTML = ''; // Clear the table body
                missingValuePanel.style.display = 'none'; // Hide missing values panel
                missingValueActions.style.display = 'none'; // Hide missing value actions
                missingValueContent.innerHTML = '';
                duplicatePanel.style.display = 'none'; // Hide duplicate panel
                if (subDuplicatesContainer) {
                    subDuplicatesContainer.style.display = 'none'; // Also hide the advanced section
                }
                subDuplicateResult.style.display = 'none'; // Hide subset results
                if (duplicatePreviewContent) {
                    duplicatePreviewContent.style.display = 'none';
                    duplicatePreviewContent.innerHTML = '';
                }
                if (statsPanel) {
                    statsPanel.style.display = 'none';
                }
                // Clear and hide AI suggestions panel
                if (aiSuggestionsPanel) {
                    aiSuggestionsPanel.style.display = 'none';
                    aiSuggestionsResult.style.display = 'none';
                    aiUnwantedColumnsList.innerHTML = '';
                    applyAIRemovalBtn.style.display = 'none';
                    aiLoadingSpinner.style.display = 'none';
                }
                if (autoEDAPanel) {
                    autoEDAPanel.style.display = 'none';
                    edaResultContainer.innerHTML = '';
                    edaLoadingSpinner.style.display = 'none';
                }
                if (correlationPanel) {
                    correlationPanel.style.display = 'none';
                    correlationResultContainer.style.display = 'none';
                    correlationLoadingSpinner.style.display = 'none';
                    scatterPlotResult.style.display = 'none';
                }
                // Deactivate sidebar links that require a dataset
                document.querySelectorAll('.dn-requires-dataset').forEach(link => {
                    link.classList.add('dn-nav-disabled');
                });

                missingCustomValueContainer.style.display = 'none'; // Hide custom input
                missingCustomValueInput.value = '';

                activeDatasetId = null; // Clear dataset ID
                missingColumnInfo = []; // Clear missing column info
                fullColumnInfo = []; // Clear the stored columns
                viewAllColsBtn.textContent = 'View All Columns'; // Reset button text
                viewAllColsBtn.setAttribute('data-state', 'more'); // Reset button state
                uploadForm.style.display = 'flex'; // Show dropzone again
                progressBar.classList.remove('bg-success', 'bg-danger');
                fileInput.value = ''; // Reset file input

                // Also reset the cleaned data preview panel
                if (cleanedPreviewPanel) {
                    cleanedPreviewPanel.style.display = 'none';
                    const downloadBtn = cleanedPreviewPanel.querySelector('#dnDownloadCleanedBtn');
                    if (downloadBtn) {
                        downloadBtn.remove(); // Remove the download button
                    }
                }

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

        // Handle "Find Duplicates by Specific Columns" button click
        if (findSubDuplicatesBtn) {
            findSubDuplicatesBtn.addEventListener('click', function () {
                const selectedColumns = Array.from(duplicateColumnSelect.querySelectorAll('input:checked')).map(cb => cb.value);

                if (selectedColumns.length === 0) {
                    alert('Please select at least one column to check for duplicates.');
                    return;
                }

                findSubDuplicatesBtn.disabled = true;
                findSubDuplicatesBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Finding...';

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
                            <div class="dn-alert dn-alert-info"><i class="bi bi-info-circle-fill"></i> Found <strong>${data.count}</strong> rows across groups that share the same values for the selected columns.</div>
                            <div class="table-responsive">${data.preview_html}</div>
                        `;
                        } else if (data.success) {
                            subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-ok"><i class="bi bi-check-circle-fill"></i> ${data.message || 'No rows found sharing the same values in the selected columns.'}</div>`;
                        } else {
                            subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Failed to check for duplicates.'}</div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('findSubDuplicatesBtn', err);
                        subDuplicateResult.style.display = 'block';
                        subDuplicateResult.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> Could not reach the server. Please try again.</div>`;
                    })
                    .finally(() => {
                        findSubDuplicatesBtn.disabled = false;
                        findSubDuplicatesBtn.innerHTML = '<i class="bi bi-search"></i> Analyze Groups';
                    });
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
                        duplicateSummary.className = 'dn-alert dn-alert-ok';
                        duplicateSummary.innerHTML = `<i class="bi bi-check-circle-fill"></i> ${data.message}`;

                        if (duplicatePreviewContent) duplicatePreviewContent.style.display = 'none';
                        if (removeFullDuplicatesBtn) removeFullDuplicatesBtn.style.display = 'none';
                        if (subDuplicatesContainer) subDuplicatesContainer.style.display = 'none';

                        const panelFooter = removeFullDuplicatesBtn.closest('.dn-panel-footer');
                        if (panelFooter) {
                            let downloadBtn = panelFooter.querySelector('#dnDownloadDedupedBtn');
                            if (!downloadBtn) {
                                downloadBtn = document.createElement('a');
                                downloadBtn.id = 'dnDownloadDedupedBtn';
                                downloadBtn.className = 'btn dn-btn-success btn-sm mt-2';
                                downloadBtn.innerHTML = '<i class="bi bi-download"></i> Download Cleaned Dataset (CSV)';
                                panelFooter.appendChild(downloadBtn);
                            }
                            downloadBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}`;
                        }

                        if (missingValuePanel) {
                            missingValuePanel.style.display = 'none';
                        }
                    } else {
                        alert('Error removing duplicates: ' + (data.message || 'Unknown error'));
                    }
                })
                .catch(err => {
                    showFetchError('handleRemoveFullDuplicates', err);
                    alert('Could not remove duplicates — the server could not be reached. Please try again.');
                })
                .finally(() => {
                    removeFullDuplicatesBtn.disabled = false;
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
                            missingValueActions.style.display = 'none';

                            const cleanedData = data.cleaned_data;
                            const summary = data.cleaning_summary;

                            if (cleanedData && summary) {
                                if (missingBefore) missingBefore.textContent = summary.missing_before.toLocaleString();
                                if (missingAfter) missingAfter.textContent = summary.missing_after.toLocaleString();
                                if (valuesFixed) valuesFixed.textContent = summary.values_fixed.toLocaleString();
                                if (rowsRemoved) rowsRemoved.textContent = summary.rows_removed.toLocaleString();

                                cleanedPreviewContent.innerHTML = cleanedData.preview_html;

                                cleanedRows.textContent = cleanedData.row_count.toLocaleString();
                                cleanedCols.textContent = cleanedData.column_count.toLocaleString();

                                cleanedPreviewPanel.style.display = 'block';
                                cleanedPreviewPanel.scrollIntoView({ behavior: 'smooth' });

                                const cleanedPanelFooter = cleanedPreviewPanel.querySelector('.dn-panel-footer');
                                if (cleanedPanelFooter) {
                                    let downloadBtn = cleanedPanelFooter.querySelector('#dnDownloadCleanedBtn');
                                    if (!downloadBtn) {
                                        downloadBtn = document.createElement('a');
                                        downloadBtn.id = 'dnDownloadCleanedBtn';
                                        downloadBtn.className = 'btn dn-btn-success btn-sm mt-3';
                                        downloadBtn.innerHTML = '<i class="bi bi-download"></i> Download Cleaned Dataset (CSV)';
                                        cleanedPanelFooter.appendChild(downloadBtn);
                                    }
                                    downloadBtn.href = `/api/download_cleaned_dataset/${activeDatasetId}`;
                                    downloadBtn.style.display = 'inline-flex';
                                }
                            } else {
                                console.warn('[DataNova] clean_data succeeded but response missing cleaned_data/cleaning_summary:', data);
                            }
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
                            edaResultContainer.innerHTML = '';
                            if (data.recommended_charts.length === 0) {
                                edaResultContainer.innerHTML = `<div class="col-12"><div class="dn-alert dn-alert-info"><i class="bi bi-info-circle-fill"></i> No specific chart recommendations could be generated for this dataset.</div></div>`;
                                return;
                            }
                            data.recommended_charts.forEach(chart => {
                                const cardHtml = `
                                <div class="col-lg-6">
                                    <div class="dn-eda-card">
                                        <div class="dn-eda-card-header">
                                            <div>
                                                <h5 class="dn-eda-card-title">${chart.title}</h5>
                                                <p class="dn-eda-card-sub">${chart.description}</p>
                                            </div>
                                        </div>
                                        <div class="dn-eda-card-body">
                                            <div class="dn-eda-plot">
                                                <img src="data:image/png;base64,${chart.plot}" alt="${chart.title}">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                                edaResultContainer.insertAdjacentHTML('beforeend', cardHtml);
                            });
                            autoEDAPanel.style.display = 'block';
                            autoEDAPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
                if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }

                correlationResultContainer.style.display = 'none';
                scatterPlotResult.style.display = 'none';
                correlationLoadingSpinner.style.display = 'block';
                generateCorrelationBtn.disabled = true;
                generateCorrelationBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Analyzing...';

                fetch('/api/get_correlation_matrix', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId })
                })
                    .then(res => res.json())
                    .then(data => {
                        correlationLoadingSpinner.style.display = 'none';
                        if (data.success) {
                            correlationHeatmap.src = `data:image/png;base64,${data.heatmap_plot}`;

                            scatterXSelect.innerHTML = '';
                            scatterYSelect.innerHTML = '';
                            data.numeric_columns.forEach(col => {
                                scatterXSelect.add(new Option(col, col));
                                scatterYSelect.add(new Option(col, col));
                            });
                            if (data.numeric_columns.length > 1) {
                                scatterYSelect.selectedIndex = 1;
                            }

                            correlationResultContainer.style.display = 'block';

                            // --- New: Populate Top Correlations ---
                            const topCorrelationsContainer = document.getElementById('dnTopCorrelationsContainer');
                            const topPositiveList = document.getElementById('dnTopPositiveCorrelations');
                            const topNegativeList = document.getElementById('dnTopNegativeCorrelations');

                            if (topCorrelationsContainer && topPositiveList && topNegativeList) {
                                topPositiveList.innerHTML = '';
                                topNegativeList.innerHTML = '';

                                data.top_positive.forEach(item => {
                                    const li = `<li class="list-group-item d-flex justify-content-between align-items-center small"><span>${item.var1} &harr; ${item.var2}</span><span class="badge bg-success-subtle text-success rounded-pill">${item.correlation.toFixed(3)}</span></li>`;
                                    topPositiveList.insertAdjacentHTML('beforeend', li);
                                });

                                data.top_negative.forEach(item => {
                                    const li = `<li class="list-group-item d-flex justify-content-between align-items-center small"><span>${item.var1} &harr; ${item.var2}</span><span class="badge bg-danger-subtle text-danger rounded-pill">${item.correlation.toFixed(3)}</span></li>`;
                                    topNegativeList.insertAdjacentHTML('beforeend', li);
                                });

                                topCorrelationsContainer.style.display = 'block';
                            }
                        } else {
                            correlationResultContainer.style.display = 'block';
                            correlationResultContainer.innerHTML = `<div class="dn-alert dn-alert-warn"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Failed to generate correlation matrix.'}</div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('generateCorrelationBtn', err);
                        correlationLoadingSpinner.style.display = 'none';
                        correlationResultContainer.style.display = 'block';
                        correlationResultContainer.innerHTML = `<div class="dn-alert dn-alert-danger"><i class="bi bi-exclamation-triangle-fill"></i> Could not reach the server. Please try again.</div>`;
                    })
                    .finally(() => {
                        generateCorrelationBtn.disabled = false;
                        generateCorrelationBtn.innerHTML = '<i class="bi bi-play-circle"></i> Analyze Correlations';
                    });
            });
        }

        if (generateScatterBtn) {
            generateScatterBtn.addEventListener('click', function () {
                const xCol = scatterXSelect.value;
                const yCol = scatterYSelect.value;
                if (!xCol || !yCol) { alert('Please select variables for both axes.'); return; }

                const scatterSpinner = document.getElementById('dnScatterLoadingSpinner');
                const scatterImg = document.getElementById('dnScatterPlotImg');

                scatterPlotResult.style.display = 'block';
                scatterSpinner.style.display = 'inline-block';
                scatterImg.style.display = 'none';
                generateScatterBtn.disabled = true;

                fetch('/api/get_scatter_plot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: activeDatasetId, x_col: xCol, y_col: yCol })
                })
                    .then(res => res.json())
                    .then(data => {
                        scatterSpinner.style.display = 'none';
                        if (data.success) {
                            scatterImg.src = `data:image/png;base64,${data.scatter_plot}`;
                            scatterImg.style.display = 'block';
                        } else {
                            scatterPlotResult.innerHTML = `<div class="dn-alert dn-alert-danger">${data.message || 'Failed to generate scatter plot.'}</div>`;
                        }
                    })
                    .catch(err => {
                        showFetchError('generateScatterBtn', err);
                        scatterSpinner.style.display = 'none';
                        scatterPlotResult.innerHTML = `<div class="dn-alert dn-alert-danger">Could not reach the server. Please try again.</div>`;
                    })
                    .finally(() => {
                        generateScatterBtn.disabled = false;
                    });
            });
        }

        // Trigger file input click when the dropzone is clicked
        uploadForm.addEventListener('click', function () {
            fileInput.click();
        });

        // Handle file selection from the dialog
        fileInput.addEventListener('change', function () {
            if (fileInput.files.length > 0) {
                uploadFile(fileInput.files[0]);
            }
        });

        // Drag and drop events
        ['dragenter', 'dragover'].forEach(function (evt) {
            uploadForm.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                uploadForm.classList.add('is-dragover');
            });
        });
        ['dragleave', 'drop'].forEach(function (evt) {
            uploadForm.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                uploadForm.classList.remove('is-dragover');
            });
        });

        uploadForm.addEventListener('drop', function (e) {
            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Helper function to render charts (used by both EDA generation and drop-columns re-render)
    function renderEdaCharts(charts) {
        if (edaResultContainer) {
            edaResultContainer.innerHTML = '';
            charts = charts || [];
            if (charts.length === 0) {
                edaResultContainer.innerHTML = `<div class="col-12"><div class="dn-alert dn-alert-info"><i class="bi bi-info-circle-fill"></i> No specific chart recommendations could be generated for this dataset.</div></div>`;
                return;
            }
            charts.forEach((chart, idx) => {
                const chartContainerId = `dnPlotlyChart_${idx}_${Date.now()}`;
                const badge3d = chart.is_3d ? `<span class="badge bg-primary-subtle text-primary me-2"><i class="bi bi-box me-1"></i>3D Dynamic</span>` : `<span class="badge bg-secondary-subtle text-secondary me-2"><i class="bi bi-bar-chart me-1"></i>2D Interactive</span>`;

                const cardHtml = `
                    <div class="col-lg-6">
                        <div class="dn-eda-card">
                            <div class="dn-eda-card-header d-flex justify-content-between align-items-start">
                                <div>
                                    <h5 class="dn-eda-card-title">${chart.title}</h5>
                                    <p class="dn-eda-card-sub mb-0">${chart.description}</p>
                                </div>
                                <div>${badge3d}</div>
                            </div>
                            <div class="dn-eda-card-body">
                                <div class="dn-eda-plot position-relative">
                                    <div id="${chartContainerId}" style="width: 100%; min-height: 340px;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                edaResultContainer.insertAdjacentHTML('beforeend', cardHtml);

                if (chart.plotly_json && window.Plotly) {
                    try {
                        const layout = chart.plotly_json.layout || {};
                        layout.autosize = true;
                        Plotly.newPlot(chartContainerId, chart.plotly_json.data || [], layout, { responsive: true, displayModeBar: true, displaylogo: false });
                    } catch (e) {
                        console.warn("Plotly render failed, using fallback img:", e);
                        const el = document.getElementById(chartContainerId);
                        if (el) el.innerHTML = `<img src="data:image/png;base64,${chart.plot}" alt="${chart.title}" class="img-fluid">`;
                    }
                } else {
                    const el = document.getElementById(chartContainerId);
                    if (el) el.innerHTML = `<img src="data:image/png;base64,${chart.plot}" alt="${chart.title}" class="img-fluid">`;
                }
            });
            if (autoEDAPanel) {
                autoEDAPanel.style.display = 'block';
            }
        }
    }

    function loadEdaResults(datasetId) {
        if (!datasetId) return;
        fetch(`/api/get_eda_results/${datasetId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.recommended_charts && edaResultContainer) {
                    renderEdaCharts(data.recommended_charts);
                }
            })
            .catch(error => showFetchError('loadEdaResults', error));
    }

    const exportReportBtn = document.getElementById('dnExportReportBtn');
    if (exportReportBtn) {
        exportReportBtn.addEventListener('click', function () {
            if (!activeDatasetId) { alert('Please upload a dataset first.'); return; }
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
                            customChartImg.src = `data:image/png;base64,${data.plot}`;
                            customChartImg.style.display = 'inline-block';
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
            'count': 'Number of non-null observations in the column.',
            'unique_count': 'The number of distinct or unique non-null values in the column.',
            'unique_ratio': 'The ratio of unique values to the total count, indicating the level of uniqueness or cardinality.',
            'mean': 'The average value of the column.',
            'median': 'The middle value when data is ordered (50th percentile), separating the upper and lower halves.',
            'std': 'The standard deviation, measuring the amount of variation or dispersion of values.',
            'variance': 'The average of the squared differences from the mean, representing overall data spread.',
            'min': 'The minimum value in the column.',
            '25%': 'The 25th percentile (first quartile), meaning 25% of values are below this point.',
            '50%': 'The 50th percentile (median), meaning half of the values are below this point.',
            '75%': 'The 75th percentile (third quartile), meaning 75% of values are below this point.',
            'max': 'The maximum value in the column.',
            'range': 'The difference between the maximum and minimum values in the column.',
            'skewness': 'A measure of asymmetry in the data distribution around its mean (indicating left or right tilt).',
            'kurtosis': 'A measure of the "tailedness" or sharpness of the peak in the distribution, indicating potential outliers.'
        };

        const statsPanel = document.getElementById('dnStatsPanel');
        if (!statsPanel) return;

        const existingTooltips = statsPanel.querySelectorAll('[data-bs-toggle="tooltip"]');
        existingTooltips.forEach(el => {
            const tooltipInstance = bootstrap.Tooltip.getInstance(el);
            if (tooltipInstance) {
                tooltipInstance.dispose();
            }
        });

        const statsTableHeaders = statsPanel.querySelectorAll('#dnStatsContent table thead th'); // Correct selector for transposed table

        statsTableHeaders.forEach(header => {
            if (!header || !header.textContent) return;
            let metricName = header.textContent.trim().toLowerCase();
            let description = metricDescriptions[metricName];

            if (!description && metricName.startsWith('pct')) {
                const numericPart = parseFloat(metricName);
                if (!isNaN(numericPart) && metricDescriptions[`${numericPart}%`]) {
                    description = metricDescriptions[`${numericPart}%`];
                }
            }

            if (description && metricName !== 'column') { // Don't add tooltip to the 'Column' header
                header.setAttribute('data-bs-toggle', 'tooltip');
                header.setAttribute('data-bs-placement', 'top');
                header.setAttribute('title', description);
                header.style.cursor = 'help';
                try {
                    new bootstrap.Tooltip(header);
                } catch (e) {
                    // If Bootstrap Tooltip fails, ignore
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

        if (data.viz_preview) {
            if (data.viz_preview.bar) renderBarPreviewChart(data.viz_preview.bar);
            if (data.viz_preview.line) renderLinePreviewChart(data.viz_preview.line);
            if (data.viz_preview.hist) renderHistPreviewChart(data.viz_preview.hist);
            if (data.viz_preview.heatmap) renderHeatmapPreviewChart(data.viz_preview.heatmap);
        } else {
            renderDefaultAnalystPlotly();
        }
    }

    function renderBarPreviewChart(barData) {
        const container = document.getElementById('analystBarPreviewChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: barData.labels || ['A', 'B', 'C', 'D'],
            y: barData.values || [40, 70, 55, 90],
            type: 'bar',
            marker: { color: '#4F46E5', cornerradius: 4 }
        };

        const layout = {
            margin: { t: 5, r: 5, l: 25, b: 20 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8', tickfont: { size: 9 } },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8', tickfont: { size: 9 } },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderLinePreviewChart(lineData) {
        const container = document.getElementById('analystLinePreviewChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: lineData.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            y: lineData.values || [15, 28, 22, 45, 38, 62],
            type: 'scatter',
            mode: 'lines',
            line: { color: '#7C3AED', width: 2.5, shape: 'spline' }
        };

        const layout = {
            margin: { t: 5, r: 5, l: 25, b: 20 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8', tickfont: { size: 9 } },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8', tickfont: { size: 9 } },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderHistPreviewChart(histData) {
        const container = document.getElementById('analystHistPreviewChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: histData.values || [12, 19, 25, 32, 28, 18, 14, 8],
            type: 'histogram',
            marker: { color: '#06B6D4' }
        };

        const layout = {
            margin: { t: 5, r: 5, l: 25, b: 20 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8', tickfont: { size: 9 } },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8', tickfont: { size: 9 } },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderHeatmapPreviewChart(heatData) {
        const container = document.getElementById('analystHeatmapPreviewChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: heatData.x || ['V1', 'V2', 'V3'],
            y: heatData.y || ['V1', 'V2', 'V3'],
            z: heatData.z || [[1, 0.8, -0.2], [0.8, 1, 0.3], [-0.2, 0.3, 1]],
            type: 'heatmap',
            colorscale: 'Viridis',
            showscale: false
        };

        const layout = {
            margin: { t: 5, r: 5, l: 25, b: 20 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { color: '#94A3B8', tickfont: { size: 9 } },
            yaxis: { color: '#94A3B8', tickfont: { size: 9 } },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderDefaultAnalystPlotly() {
        renderBarPreviewChart({});
        renderLinePreviewChart({});
        renderHistPreviewChart({});
        renderHeatmapPreviewChart({});
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

    fetchAnalystAnalytics();

    // Restore the active/latest dataset after a page refresh.
    loadCurrentDataset();
});