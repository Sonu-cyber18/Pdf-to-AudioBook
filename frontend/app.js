/**
 * VoiceCraft Studio — Frontend Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------
    const state = {
        currentFileId: null,
        currentDocInfo: null,
        voicesCatalog: {},
        currentJobId: null,
        pollingInterval: null,
        currentAudiobook: null,
        activeTrackIndex: -1, // -1 means full audiobook, 0..N means chapter index
        theme: localStorage.getItem("voicecraft_theme") || "dark"
    };

    // -------------------------------------------------------------
    // DOM Elements
    // -------------------------------------------------------------
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    const moonIcon = document.getElementById("moonIcon");
    const sunIcon = document.getElementById("sunIcon");

    // Upload & Dropzone
    const uploadSection = document.getElementById("uploadSection");
    const dropzone = document.getElementById("dropzone");
    const pdfFileInput = document.getElementById("pdfFileInput");
    const browseFileBtn = document.getElementById("browseFileBtn");
    const uploadingIndicator = document.getElementById("uploadingIndicator");
    const uploadingText = document.getElementById("uploadingText");
    const dropzoneContent = dropzone.querySelector(".dropzone-content");

    // File Info & Preview
    const fileInfoSection = document.getElementById("fileInfoSection");
    const scannedAlert = document.getElementById("scannedAlert");
    const scannedAlertMsg = document.getElementById("scannedAlertMsg");
    const metaFilename = document.getElementById("metaFilename");
    const metaTitle = document.getElementById("metaTitle");
    const metaPages = document.getElementById("metaPages");
    const metaSize = document.getElementById("metaSize");
    const loadPreviewBtn = document.getElementById("loadPreviewBtn");
    const togglePreviewViewBtn = document.getElementById("togglePreviewViewBtn");
    const previewContainer = document.getElementById("previewContainer");
    const previewCharCount = document.getElementById("previewCharCount");
    const previewTextContent = document.getElementById("previewTextContent");
    const pagesBreakdown = document.getElementById("pagesBreakdown");

    // Synthesis Configuration
    const configSection = document.getElementById("configSection");
    const languageSelect = document.getElementById("languageSelect");
    const voiceSelect = document.getElementById("voiceSelect");
    const speedSlider = document.getElementById("speedSlider");
    const speedValDisplay = document.getElementById("speedValDisplay");
    const speedPresetBtns = document.querySelectorAll(".preset-btn");
    const splitChaptersCheck = document.getElementById("splitChaptersCheck");
    const startGenerationBtn = document.getElementById("startGenerationBtn");

    // Live Progress
    const progressSection = document.getElementById("progressSection");
    const progressStatusHeader = document.getElementById("progressStatusHeader");
    const jobStatusBadge = document.getElementById("jobStatusBadge");
    const jobProgressPercent = document.getElementById("jobProgressPercent");
    const jobProgressBar = document.getElementById("jobProgressBar");
    const jobProgressMessage = document.getElementById("jobProgressMessage");
    const progressSpinner = document.getElementById("progressSpinner");

    const pipeSteps = {
        extract: document.getElementById("stepExtract"),
        process: document.getElementById("stepProcess"),
        tts: document.getElementById("stepTTS"),
        combine: document.getElementById("stepCombine"),
        ready: document.getElementById("stepReady")
    };

    // Audiobook Player
    const playerSection = document.getElementById("playerSection");
    const audioElement = document.getElementById("audioElement");
    const playerBookTitle = document.getElementById("playerBookTitle");
    const playerCurrentTrack = document.getElementById("playerCurrentTrack");
    const audioVisualizer = document.getElementById("audioVisualizer");
    const currentTimeLabel = document.getElementById("currentTimeLabel");
    const totalDurationLabel = document.getElementById("totalDurationLabel");
    const seekSlider = document.getElementById("seekSlider");
    const playPauseBtn = document.getElementById("playPauseBtn");
    const playIcon = document.getElementById("playIcon");
    const pauseIcon = document.getElementById("pauseIcon");
    const prevTrackBtn = document.getElementById("prevTrackBtn");
    const nextTrackBtn = document.getElementById("nextTrackBtn");
    const skipBack10Btn = document.getElementById("skipBack10Btn");
    const skipFwd10Btn = document.getElementById("skipFwd10Btn");
    const muteBtn = document.getElementById("muteBtn");
    const volumeSlider = document.getElementById("volumeSlider");
    const playerPlaybackRateSelect = document.getElementById("playerPlaybackRateSelect");
    const playerChapterSelect = document.getElementById("playerChapterSelect");
    const downloadMasterBtn = document.getElementById("downloadMasterBtn");
    const startNewBookBtn = document.getElementById("startNewBookBtn");
    const chaptersCountBadge = document.getElementById("chaptersCountBadge");
    const chaptersList = document.getElementById("chaptersList");

    const toastContainer = document.getElementById("toastContainer");

    // -------------------------------------------------------------
    // Theme Management
    // -------------------------------------------------------------
    function applyTheme(theme) {
        state.theme = theme;
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("voicecraft_theme", theme);
        if (theme === "light") {
            moonIcon.classList.add("hidden");
            sunIcon.classList.remove("hidden");
        } else {
            moonIcon.classList.remove("hidden");
            sunIcon.classList.add("hidden");
        }
    }
    applyTheme(state.theme);

    themeToggleBtn.addEventListener("click", () => {
        applyTheme(state.theme === "dark" ? "light" : "dark");
    });

    // -------------------------------------------------------------
    // Notifications / Toasts
    // -------------------------------------------------------------
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // -------------------------------------------------------------
    // Helper: Human-readable sizes & time
    // -------------------------------------------------------------
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    function formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) return "00:00";
        const s = Math.floor(seconds);
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        const hrs = Math.floor(mins / 60);
        if (hrs > 0) {
            const remMins = mins % 60;
            return `${hrs.toString().padStart(2, "0")}:${remMins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
        }
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }

    // -------------------------------------------------------------
    // Load Voice Catalog
    // -------------------------------------------------------------
    async function loadVoices() {
        try {
            const res = await fetch("/api/voices");
            if (!res.ok) throw new Error("Failed to load voices");
            const data = await res.json();
            state.voicesCatalog = data.voices || {};

            // Populate languages
            languageSelect.innerHTML = "";
            const langNames = {
                "en": "English",
                "hi": "Hindi (हिंदी)",
                "es": "Spanish (Español)",
                "fr": "French (Français)",
                "de": "German (Deutsch)"
            };

            Object.keys(state.voicesCatalog).forEach(lang => {
                const opt = document.createElement("option");
                opt.value = lang;
                opt.textContent = langNames[lang] || lang.toUpperCase();
                languageSelect.appendChild(opt);
            });

            // Set default language
            languageSelect.value = "en";
            updateVoiceDropdown("en");
        } catch (err) {
            console.error("Voices error:", err);
            showToast("Could not load voice catalog from server.", "error");
        }
    }

    function updateVoiceDropdown(lang) {
        voiceSelect.innerHTML = "";
        const voices = state.voicesCatalog[lang] || [];
        voices.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.id;
            opt.textContent = `${v.name} [${v.gender}]`;
            if (v.is_default) opt.selected = true;
            voiceSelect.appendChild(opt);
        });
    }

    languageSelect.addEventListener("change", (e) => {
        updateVoiceDropdown(e.target.value);
    });

    // -------------------------------------------------------------
    // Speed Controls
    // -------------------------------------------------------------
    speedSlider.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        speedValDisplay.textContent = `${val.toFixed(2)}x`;
        speedPresetBtns.forEach(btn => {
            btn.classList.toggle("active", parseFloat(btn.dataset.speed) === val);
        });
    });

    speedPresetBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const speed = parseFloat(btn.dataset.speed);
            speedSlider.value = speed;
            speedValDisplay.textContent = `${speed.toFixed(2)}x`;
            speedPresetBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
        });
    });

    // -------------------------------------------------------------
    // File Upload & Drag-and-Drop
    // -------------------------------------------------------------
    browseFileBtn.addEventListener("click", () => pdfFileInput.click());

    ["dragenter", "dragover"].forEach(event => {
        dropzone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(event => {
        dropzone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove("dragover");
        });
    });

    dropzone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    pdfFileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showToast("Invalid file format. Please upload a PDF document.", "error");
            return;
        }

        // 100 MB max
        if (file.size > 100 * 1024 * 1024) {
            showToast("File size exceeds 100 MB limit.", "error");
            return;
        }

        // Show uploading state
        dropzoneContent.classList.add("hidden");
        uploadingIndicator.classList.remove("hidden");
        uploadingText.textContent = `Uploading and parsing "${file.name}"...`;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || "Upload failed");
            }

            state.currentFileId = result.file_id;
            state.currentDocInfo = result;

            // Populate Metadata Card
            metaFilename.textContent = result.filename;
            metaTitle.textContent = result.title || result.filename.replace(".pdf", "");
            metaPages.textContent = `${result.pages} page${result.pages > 1 ? "s" : ""}`;
            metaSize.textContent = formatBytes(result.size);

            // Reset preview and scanned alerts
            scannedAlert.classList.add("hidden");
            previewContainer.classList.add("hidden");
            togglePreviewViewBtn.style.display = "none";

            // Reveal step 2 & 3
            fileInfoSection.classList.remove("hidden");
            configSection.classList.remove("hidden");

            showToast("PDF uploaded and verified successfully!", "success");

            fileInfoSection.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (err) {
            console.error("Upload failed:", err);
            showToast(`Upload Error: ${err.message}`, "error");
        } finally {
            dropzoneContent.classList.remove("hidden");
            uploadingIndicator.classList.add("hidden");
            pdfFileInput.value = "";
        }
    }

    // -------------------------------------------------------------
    // Text Preview
    // -------------------------------------------------------------
    loadPreviewBtn.addEventListener("click", async () => {
        if (!state.currentFileId) return;

        loadPreviewBtn.disabled = true;
        loadPreviewBtn.innerHTML = '<span class="mini-spinner"></span> Extracting preview...';

        try {
            const res = await fetch(`/api/pdf/${state.currentFileId}/preview`);
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || "Failed to extract preview");

            // Scanned check
            if (data.is_scanned) {
                scannedAlertMsg.textContent = data.notice || "This PDF appears to contain scanned images rather than selectable text. OCR is required.";
                scannedAlert.classList.remove("hidden");
            } else {
                scannedAlert.classList.add("hidden");
            }

            // Preview Text
            previewTextContent.textContent = data.preview_text || "No selectable text found on inspected sample pages.";
            previewCharCount.textContent = `${data.total_extracted_chars_in_sample || 0} sample chars`;

            // Page breakdowns
            pagesBreakdown.innerHTML = "";
            if (data.pages_info && data.pages_info.length > 0) {
                const breakdownTitle = document.createElement("div");
                breakdownTitle.innerHTML = `<strong>Page Breakdown (First ${data.inspected_pages} pages):</strong>`;
                pagesBreakdown.appendChild(breakdownTitle);

                data.pages_info.forEach(p => {
                    const row = document.createElement("div");
                    row.style.margin = "0.35rem 0";
                    row.innerHTML = `• <em>Page ${p.page_number}</em>: ${p.char_count} chars${p.image_count ? `, ${p.image_count} image(s)` : ""} ${p.is_blank ? '<span style="color:var(--warning)">(blank)</span>' : ""}`;
                    pagesBreakdown.appendChild(row);
                });
            }

            previewContainer.classList.remove("hidden");
            togglePreviewViewBtn.style.display = "inline-flex";
            togglePreviewViewBtn.textContent = "Hide Preview";

        } catch (err) {
            showToast(`Preview Error: ${err.message}`, "error");
        } finally {
            loadPreviewBtn.disabled = false;
            loadPreviewBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                Re-extract Preview
            `;
        }
    });

    togglePreviewViewBtn.addEventListener("click", () => {
        if (previewContainer.classList.contains("hidden")) {
            previewContainer.classList.remove("hidden");
            togglePreviewViewBtn.textContent = "Hide Preview";
        } else {
            previewContainer.classList.add("hidden");
            togglePreviewViewBtn.textContent = "Show Preview";
        }
    });

    // -------------------------------------------------------------
    // Trigger Audiobook Generation
    // -------------------------------------------------------------
    startGenerationBtn.addEventListener("click", async () => {
        if (!state.currentFileId) {
            showToast("Please upload a PDF document first.", "warning");
            return;
        }

        const payload = {
            file_id: state.currentFileId,
            language: languageSelect.value,
            voice: voiceSelect.value,
            speed: parseFloat(speedSlider.value),
            format: "mp3",
            split_chapters: splitChaptersCheck.checked
        };

        startGenerationBtn.disabled = true;
        startGenerationBtn.innerHTML = '<span class="mini-spinner"></span> Queueing Job...';

        try {
            const res = await fetch("/api/audiobook/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Generation request failed");

            state.currentJobId = data.job_id;

            // Transition UI to Progress Step
            progressSection.classList.remove("hidden");
            playerSection.classList.add("hidden");
            progressSection.scrollIntoView({ behavior: "smooth", block: "start" });

            // Start Polling
            startJobPolling(data.job_id);

        } catch (err) {
            showToast(`Generation Error: ${err.message}`, "error");
            startGenerationBtn.disabled = false;
            startGenerationBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                Generate Audiobook
            `;
        }
    });

    // -------------------------------------------------------------
    // Progress Polling System
    // -------------------------------------------------------------
    function startJobPolling(jobId) {
        if (state.pollingInterval) clearInterval(state.pollingInterval);

        updatePipelineVisual("extract");

        state.pollingInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/jobs/${jobId}`);
                if (!res.ok) throw new Error("Failed to check job progress");

                const job = await res.json();
                handleJobUpdate(job);
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 1200);
    }

    function handleJobUpdate(job) {
        const { status, progress, message, current_chapter, audiobook, error } = job;

        // Update progress bar & labels
        jobStatusBadge.textContent = status;
        jobProgressPercent.textContent = `${progress}%`;
        jobProgressBar.style.width = `${progress}%`;
        jobProgressMessage.textContent = message || `Processing (${status})...`;

        // Update pipeline step highlights
        if (status === "extracting") {
            updatePipelineVisual("extract");
        } else if (status === "processing") {
            updatePipelineVisual("process");
        } else if (status === "generating_audio") {
            updatePipelineVisual("tts");
        } else if (status === "combining") {
            updatePipelineVisual("combine");
        } else if (status === "completed") {
            updatePipelineVisual("ready");
            clearInterval(state.pollingInterval);
            state.pollingInterval = null;
            onJobCompleted(audiobook);
        } else if (status === "failed") {
            clearInterval(state.pollingInterval);
            state.pollingInterval = null;
            onJobFailed(error || "Conversion failed.");
        }
    }

    function updatePipelineVisual(currentStepKey) {
        const keys = ["extract", "process", "tts", "combine", "ready"];
        const curIdx = keys.indexOf(currentStepKey);

        keys.forEach((k, idx) => {
            const el = pipeSteps[k];
            if (!el) return;
            el.classList.remove("active", "done");
            if (idx < curIdx) {
                el.classList.add("done");
            } else if (idx === curIdx) {
                el.classList.add("active");
            }
        });
    }

    function onJobFailed(errorMessage) {
        progressStatusHeader.textContent = "Conversion encountered an issue";
        jobStatusBadge.style.background = "rgba(239, 68, 68, 0.2)";
        jobStatusBadge.style.color = "var(--danger)";
        jobStatusBadge.style.borderColor = "var(--danger)";
        jobProgressMessage.textContent = errorMessage;
        progressSpinner.style.display = "none";

        startGenerationBtn.disabled = false;
        startGenerationBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Try Again
        `;

        showToast(errorMessage, "error");
    }

    function onJobCompleted(audiobook) {
        state.currentAudiobook = audiobook;

        progressStatusHeader.textContent = "Audiobook conversion finished!";
        jobProgressMessage.textContent = "Master audio tracks assembled.";
        progressSpinner.style.display = "none";

        startGenerationBtn.disabled = false;
        startGenerationBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Regenerate Audiobook
        `;

        showToast("Your audiobook is ready to listen!", "success");

        // Reveal Player Section
        playerSection.classList.remove("hidden");
        initPlayer(audiobook);
        playerSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // -------------------------------------------------------------
    // Audiobook Player Logic
    // -------------------------------------------------------------
    function initPlayer(audiobook) {
        playerBookTitle.textContent = audiobook.title || "Audiobook";
        downloadMasterBtn.href = audiobook.download_url;
        downloadMasterBtn.setAttribute("download", `${audiobook.title || "audiobook"}.mp3`);

        // Populate chapter select dropdown in player
        playerChapterSelect.innerHTML = "";
        const masterOpt = document.createElement("option");
        masterOpt.value = "master";
        masterOpt.textContent = `Master Track (Full Book: ${audiobook.duration_formatted || "Ready"})`;
        playerChapterSelect.appendChild(masterOpt);

        const chapters = audiobook.chapters || [];
        chaptersCountBadge.textContent = chapters.length;

        chapters.forEach((ch, idx) => {
            const opt = document.createElement("option");
            opt.value = idx.toString();
            opt.textContent = `Ch. ${ch.chapter_number}: ${ch.title} (${ch.duration_formatted})`;
            playerChapterSelect.appendChild(opt);
        });

        // Render chapter list items
        renderChaptersList(chapters);

        // Load master track by default
        loadTrack(-1, false);
    }

    function renderChaptersList(chapters) {
        chaptersList.innerHTML = "";
        if (!chapters || chapters.length === 0) {
            chaptersList.innerHTML = '<div style="color:var(--text-muted); padding:1rem;">Single track audiobook created.</div>';
            return;
        }

        chapters.forEach((ch, idx) => {
            const item = document.createElement("div");
            item.className = "chapter-item";
            item.id = `chapterItem_${idx}`;

            item.innerHTML = `
                <div class="chapter-info-col">
                    <span class="chapter-num-badge">${ch.chapter_number}</span>
                    <div class="chapter-meta-text">
                        <h4>${ch.title}</h4>
                        <span>Page ${ch.start_page} • ${ch.duration_formatted} • ${ch.file_size_formatted}</span>
                    </div>
                </div>
                <div class="chapter-actions-col">
                    <button type="button" class="btn btn-secondary btn-sm play-ch-btn" data-index="${idx}">
                        ▶ Play
                    </button>
                    <a href="${ch.download_url}" class="btn btn-outline btn-sm" download>
                        ⬇ MP3
                    </a>
                </div>
            `;

            const playBtn = item.querySelector(".play-ch-btn");
            playBtn.addEventListener("click", () => {
                loadTrack(idx, true);
            });

            chaptersList.appendChild(item);
        });
    }

    function loadTrack(index, autoplay = true) {
        state.activeTrackIndex = index;

        // Reset player UI
        seekSlider.value = 0;
        currentTimeLabel.textContent = "00:00";

        // Highlight in chapter list
        document.querySelectorAll(".chapter-item").forEach((el, i) => {
            el.classList.toggle("playing", i === index);
        });

        if (index === -1) {
            // Master Audiobook
            playerCurrentTrack.textContent = "Full Master Track";
            playerChapterSelect.value = "master";
            audioElement.src = state.currentAudiobook.stream_url;
        } else {
            // Individual Chapter
            const ch = state.currentAudiobook.chapters[index];
            playerCurrentTrack.textContent = `Chapter ${ch.chapter_number}: ${ch.title}`;
            playerChapterSelect.value = index.toString();
            audioElement.src = ch.stream_url;
        }

        audioElement.playbackRate = parseFloat(playerPlaybackRateSelect.value);

        if (autoplay) {
            audioElement.play().catch(e => console.log("Autoplay caught:", e));
        }
    }

    // Player Event Listeners
    playerChapterSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        if (val === "master") {
            loadTrack(-1, true);
        } else {
            loadTrack(parseInt(val, 10), true);
        }
    });

    playPauseBtn.addEventListener("click", togglePlayPause);

    function togglePlayPause() {
        if (audioElement.paused) {
            audioElement.play();
        } else {
            audioElement.pause();
        }
    }

    audioElement.addEventListener("play", () => {
        playIcon.classList.add("hidden");
        pauseIcon.classList.remove("hidden");
        audioVisualizer.classList.add("playing");
    });

    audioElement.addEventListener("pause", () => {
        playIcon.classList.remove("hidden");
        pauseIcon.classList.add("hidden");
        audioVisualizer.classList.remove("playing");
    });

    audioElement.addEventListener("loadedmetadata", () => {
        totalDurationLabel.textContent = formatTime(audioElement.duration);
        seekSlider.max = audioElement.duration || 100;
    });

    audioElement.addEventListener("timeupdate", () => {
        if (!seekSlider.matches(":active")) {
            seekSlider.value = audioElement.currentTime;
            currentTimeLabel.textContent = formatTime(audioElement.currentTime);
        }
    });

    seekSlider.addEventListener("input", (e) => {
        currentTimeLabel.textContent = formatTime(e.target.value);
    });

    seekSlider.addEventListener("change", (e) => {
        audioElement.currentTime = e.target.value;
    });

    // Skip Buttons
    skipBack10Btn.addEventListener("click", () => {
        audioElement.currentTime = Math.max(0, audioElement.currentTime - 10);
    });

    skipFwd10Btn.addEventListener("click", () => {
        audioElement.currentTime = Math.min(audioElement.duration || 0, audioElement.currentTime + 10);
    });

    // Previous / Next Chapter
    prevTrackBtn.addEventListener("click", () => {
        if (!state.currentAudiobook || !state.currentAudiobook.chapters) return;
        const total = state.currentAudiobook.chapters.length;
        if (state.activeTrackIndex > 0) {
            loadTrack(state.activeTrackIndex - 1, true);
        } else {
            loadTrack(-1, true);
        }
    });

    nextTrackBtn.addEventListener("click", () => {
        if (!state.currentAudiobook || !state.currentAudiobook.chapters) return;
        const total = state.currentAudiobook.chapters.length;
        if (state.activeTrackIndex < total - 1) {
            loadTrack(state.activeTrackIndex + 1, true);
        }
    });

    audioElement.addEventListener("ended", () => {
        // Auto-advance to next chapter if available
        if (state.currentAudiobook && state.currentAudiobook.chapters) {
            const total = state.currentAudiobook.chapters.length;
            if (state.activeTrackIndex >= 0 && state.activeTrackIndex < total - 1) {
                loadTrack(state.activeTrackIndex + 1, true);
            }
        }
    });

    // Volume & Mute
    let lastVolume = 1;
    volumeSlider.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        audioElement.volume = val;
        audioElement.muted = (val === 0);
        updateVolumeIcon(val);
    });

    muteBtn.addEventListener("click", () => {
        if (audioElement.muted || audioElement.volume === 0) {
            audioElement.muted = false;
            audioElement.volume = lastVolume > 0 ? lastVolume : 1;
            volumeSlider.value = audioElement.volume;
        } else {
            lastVolume = audioElement.volume;
            audioElement.muted = true;
            volumeSlider.value = 0;
        }
        updateVolumeIcon(audioElement.muted ? 0 : audioElement.volume);
    });

    function updateVolumeIcon(vol) {
        if (vol === 0) {
            muteBtn.style.color = "var(--danger)";
        } else {
            muteBtn.style.color = "var(--text-primary)";
        }
    }

    // Playback Speed
    playerPlaybackRateSelect.addEventListener("change", (e) => {
        audioElement.playbackRate = parseFloat(e.target.value);
    });

    // Reset for another PDF
    startNewBookBtn.addEventListener("click", () => {
        audioElement.pause();
        uploadSection.scrollIntoView({ behavior: "smooth" });
    });

    // Global spacebar keyboard shortcut for player toggle
    window.addEventListener("keydown", (e) => {
        if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "SELECT") {
            e.preventDefault();
            togglePlayPause();
        }
    });

    // Initialize voice list on startup
    loadVoices();
});
