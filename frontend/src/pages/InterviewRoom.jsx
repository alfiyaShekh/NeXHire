import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const MAX_WARNINGS = 3;
const GRACE_MS = 4000; // ignore focus changes right after mount (permission prompts)

const CSS = `
.ir-root,.ir-root *{box-sizing:border-box}
.ir-root{min-height:100vh;background:#080b12;color:#dce5ee;font:10px/1.45 Inter,system-ui,sans-serif}
.ir-muted{color:#78899c}
.ir-green{color:#00c99a}
.ir-top{height:46px;padding:0 16px;display:flex;align-items:center;justify-content:space-between;gap:10px;background:#0a1018;border-bottom:1px solid #202a36}
.ir-brand{font-size:14px;font-weight:750;letter-spacing:-.4px;white-space:nowrap}
.ir-brand span{color:#00c99a}
.ir-topright{display:flex;align-items:center;gap:6px}
.ir-btn{display:inline-flex;align-items:center;justify-content:center;gap:5px;border:1px solid #273442;border-radius:5px;background:#111a25;color:#d6e0ea;padding:5px 8px;font:500 10px/1.2 inherit;cursor:pointer;white-space:nowrap}
.ir-btn:hover{border-color:#00a982}
.ir-btn:disabled{opacity:.4;cursor:not-allowed}
.ir-primary{background:#00b889;color:#06130f;border-color:#00b889}
.ir-primary:hover{background:#00d19b}
.ir-danger{background:#211219;color:#ff9eaa;border-color:#63303a}
.ir-pill{display:inline-flex;align-items:center;gap:4px;padding:3px 6px;border:1px solid #293541;border-radius:20px;font-size:9px;color:#9eafbf;white-space:nowrap}
.ir-warnpill{border-color:#6b4a1e;color:#f5bf68}
.ir-warnpill.ir-critical{border-color:#63303a;color:#ff9eaa}
.ir-dot{width:5px;height:5px;border-radius:50%;background:#00c99a;display:inline-block;flex-shrink:0}
.ir-shell{width:100%;max-width:1420px;margin:auto;padding:11px 16px 16px}
.ir-alert{min-height:29px;padding:5px 8px;border:1px solid #25352f;border-radius:5px;background:#0c1715;display:flex;align-items:center;justify-content:space-between;gap:7px;margin-bottom:10px;font-size:9px;color:#a5b8b2}
.ir-alert strong{color:#00c99a}
.ir-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
.ir-eyebrow{font-size:8px;letter-spacing:1px;text-transform:uppercase;color:#00c99a}
.ir-title{font-size:15px;line-height:1.3;font-weight:700;letter-spacing:-.3px;margin:2px 0}
.ir-subtitle{font-size:9px;color:#7f90a3}
.ir-progress-wrap{width:180px;flex-shrink:0}
.ir-progress-label{display:flex;justify-content:space-between;gap:6px;color:#8392a3;font-size:9px;margin-bottom:4px}
.ir-progress{height:3px;border-radius:5px;background:#202b37;overflow:hidden}
.ir-progress>div{height:100%;background:#00c99a}
.ir-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:9px}
.ir-card{min-width:0;background:#0b121a;border:1px solid #202b37;border-radius:7px;overflow:hidden}
.ir-cardhead{height:34px;padding:0 9px;display:flex;align-items:center;justify-content:space-between;gap:6px;border-bottom:1px solid #1e2934}
.ir-cardtitle{font-size:10px;font-weight:650}
.ir-body{padding:9px}
.ir-question{min-height:105px;padding:11px;border:1px solid #203b35;border-radius:5px;background:linear-gradient(130deg,#10211e,#0b131c 75%);display:flex;flex-direction:column;justify-content:center}
.ir-qmeta{font-size:8px;color:#00c99a;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.ir-question h2{font-size:13px;line-height:1.5;letter-spacing:-.1px;font-weight:650;margin:0 0 5px}
.ir-question p{font-size:9px;line-height:1.55;color:#8b9bac;margin:0}
.ir-sectionhead{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:9px 0 5px}
.ir-sectiontitle{font-size:10px;font-weight:650}
.ir-recorder{min-height:47px;padding:7px;display:flex;align-items:center;gap:8px;border:1px solid #202b36;background:#080e15;border-radius:5px}
.ir-recicon{width:27px;height:27px;display:grid;place-items:center;background:#10271f;border-radius:5px;color:#00c99a;flex-shrink:0}
.ir-time{font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}
.ir-recstatus{font-size:9px;color:#7d8da0}
.ir-controls{display:flex;gap:5px;margin-top:6px}
.ir-controls .ir-btn{flex:1}
.ir-nav{display:flex;align-items:center;justify-content:space-between;gap:5px;margin-top:9px}
.ir-counter{font-size:9px;color:#8291a3;white-space:nowrap}
.ir-camera{aspect-ratio:16/9;max-height:260px;position:relative;display:grid;place-items:center;background:#05090e;border:1px solid #1d2833;border-radius:5px;overflow:hidden}
.ir-camera video{width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}
.ir-placeholder{text-align:center;padding:12px;color:#8090a2}
.ir-placeholder strong{display:block;font-size:10px;color:#d6e0e9;margin:5px 0 3px}
.ir-overlay{position:absolute;bottom:6px;left:6px;right:6px;display:flex;align-items:center;justify-content:space-between;gap:5px}
.ir-overlaygroup{display:flex;gap:4px}
.ir-overlay .ir-btn{padding:5px 6px;background:#080f18ed}
.ir-meter-label{display:flex;justify-content:space-between;gap:5px;margin-top:8px;font-size:9px;color:#8595a7}
.ir-meter{height:3px;margin-top:4px;border-radius:5px;background:#1b2833;overflow:hidden}
.ir-meter>div{height:100%;background:#00c99a;transition:width .1s}
.ir-device-row{display:flex;gap:5px;margin-top:7px}
.ir-device-row .ir-btn{flex:1}
.ir-note{font-size:9px;line-height:1.5;color:#708196;margin:7px 0 0}
.ir-bottom{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:9px}
.ir-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}
.ir-metric{padding:7px;border:1px solid #1d2934;background:#0a1118;border-radius:5px}
.ir-metric-label{font-size:9px;color:#8293a5;margin-bottom:3px}
.ir-metric-value{font-size:10px;font-weight:600}
.ir-loglist{display:flex;flex-direction:column;gap:6px;max-height:105px;overflow:auto}
.ir-log{display:flex;gap:6px;font-size:9px;color:#a4b2c1;line-height:1.45}
.ir-logtime{color:#687c90;white-space:nowrap;font-variant-numeric:tabular-nums}
.ir-tips{padding-left:13px;margin:0;color:#9cabb9;font-size:9px;line-height:1.85}
.ir-empty{font-size:9px;line-height:1.5;color:#738498}
.ir-footer{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:8px;color:#65768a;margin-top:10px}
.ir-backdrop{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:15px;background:#02060bdc}
.ir-modal{width:min(340px,100%);padding:15px;border:1px solid #2a3745;border-radius:8px;background:#0b121a;box-shadow:0 20px 70px #0008}
.ir-modal h3{font-size:13px;margin:0 0 6px}
.ir-modal p{font-size:10px;line-height:1.65;color:#94a4b5;margin:0 0 12px}
.ir-modalactions{display:flex;justify-content:flex-end;gap:5px;flex-wrap:wrap}
.ir-break{position:fixed;inset:0;z-index:40;background:#070b12f5;display:grid;place-content:center;justify-items:center;text-align:center;padding:20px}
.ir-break h2{font-size:18px;margin:8px 0 4px}
.ir-break p{max-width:300px;font-size:10px;line-height:1.7;color:#93a3b5;margin:0 0 12px}
@media(max-width:760px){
 .ir-shell{padding:9px}
 .ir-top{padding:0 9px}
 .ir-grid{grid-template-columns:1fr}
 .ir-bottom{grid-template-columns:1fr 1fr}
 .ir-bottom> :last-child{grid-column:1/-1}
 .ir-heading{align-items:flex-start}
}
@media(max-width:480px){
 .ir-top{height:auto;min-height:44px;flex-wrap:wrap;padding:7px}
 .ir-topright{flex-wrap:wrap;justify-content:flex-end}
 .ir-bottom{grid-template-columns:1fr}
 .ir-bottom> :last-child{grid-column:auto}
 .ir-heading{flex-direction:column}
 .ir-progress-wrap{width:100%}
 .ir-alert{align-items:flex-start}
 .ir-nav{flex-wrap:wrap}
}

/* Balanced compact layout — keep camera preview sizing unchanged */
.ir-root{font-size:9px;line-height:1.4}
.ir-top{height:42px;padding:0 13px;gap:8px}
.ir-brand{font-size:13px}
.ir-topright{gap:5px}
.ir-btn{padding:4px 7px;font-size:9px;gap:4px;border-radius:4px}
.ir-pill{padding:3px 5px;font-size:8px;gap:4px}
.ir-shell{padding:8px 13px 12px}
.ir-alert{min-height:26px;padding:4px 7px;margin-bottom:7px;font-size:8px;gap:6px}
.ir-heading{gap:10px;margin-bottom:7px}
.ir-eyebrow{font-size:7px;letter-spacing:.7px}
.ir-title{font-size:13px;line-height:1.25;margin:2px 0}
.ir-subtitle,.ir-progress-label{font-size:8px}
.ir-progress-wrap{width:155px}
.ir-progress-label{margin-bottom:3px}
.ir-grid{gap:8px}
.ir-card{border-radius:6px}
.ir-cardhead{height:30px;padding:0 8px;gap:5px}
.ir-cardtitle,.ir-sectiontitle{font-size:9px}
.ir-body{padding:7px}
.ir-question{min-height:82px;padding:8px;border-radius:5px}
.ir-qmeta{font-size:7px;letter-spacing:.5px;margin-bottom:4px}
.ir-question h2{font-size:11px;line-height:1.35;letter-spacing:0;margin:0 0 4px}
.ir-question p{font-size:8px;line-height:1.4}
.ir-sectionhead{gap:5px;margin:7px 0 4px}
.ir-recorder{min-height:40px;padding:6px;gap:7px}
.ir-recicon{width:24px;height:24px}
.ir-time{font-size:12px}
.ir-recstatus,.ir-counter{font-size:8px}
.ir-controls{gap:4px;margin-top:5px}
.ir-nav{gap:4px;margin-top:7px}
.ir-meter-label{margin-top:6px;font-size:8px}
.ir-device-row{gap:4px;margin-top:5px}
.ir-note{font-size:8px;line-height:1.4;margin-top:5px}
.ir-bottom{gap:7px;margin-top:7px}
.ir-metrics{gap:4px}
.ir-metric{padding:6px;border-radius:4px}
.ir-metric-label{font-size:8px;margin-bottom:2px}
.ir-metric-value{font-size:9px}
.ir-loglist{gap:4px;max-height:90px}
.ir-log{gap:5px;font-size:8px;line-height:1.4}
.ir-empty{font-size:8px;line-height:1.4}
.ir-tips{padding-left:12px;font-size:8px;line-height:1.65}
.ir-footer{font-size:7px;margin-top:7px;gap:6px}
.ir-modal{width:min(320px,100%);padding:12px}
.ir-modal h3{font-size:12px;margin-bottom:5px}
.ir-modal p{font-size:9px;line-height:1.5;margin-bottom:10px}
.ir-break h2{font-size:16px;margin:7px 0 4px}
.ir-break p{font-size:9px;line-height:1.5;margin-bottom:10px}

/* Candidate-safety warning shown directly over the live camera preview. */
.ir-camera-warning{position:absolute;left:8px;top:7px;z-index:4;max-width:calc(100% - 16px);padding:0;margin:0;border:0;border-radius:0;background:transparent;box-shadow:none;color:#ff3b3b;font-size:11px;font-weight:600;line-height:1.35;pointer-events:none;text-shadow:0 1px 2px rgba(0,0,0,.85)}
.ir-camera-warning.is-warning{color:#ff3b3b}
@media(max-width:480px){.ir-camera-warning{left:6px;top:6px;font-size:10px}}
/* .ir-camera and .ir-camera video are intentionally unchanged. */

/* Compact playback + transcript panels */
.ir-panel{margin-top:7px;padding:6px 7px;border:1px solid #202b37;border-radius:5px;background:#0a1118}
.ir-panel-head{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:4px;min-height:20px}
.ir-panel-title{font-size:9px;font-weight:650;color:#d6e0ea}
.ir-panel-actions{display:flex;align-items:center;gap:5px}
.ir-panel-meta{font-size:8px;color:#78899c;white-space:nowrap}
.ir-panel audio{display:block;width:100%;height:28px}
.ir-transcript-body{min-height:24px;max-height:48px;overflow-y:auto;white-space:pre-wrap;font-size:9px;line-height:1.45;color:#dce5ee}
.ir-transcript-body.is-empty{color:#78899c}
.ir-panel-error{margin-top:4px;font-size:8px;line-height:1.4;color:#ff9eaa}
.ir-panel-foot{margin-top:4px;font-size:7px;line-height:1.4;color:#65768a}
.ir-btn-sm{padding:2px 6px;font-size:8px}
`;

function Icon({ name, size = 12 }) {
    const shapes = {
        camera: <><rect x="3" y="6" width="13" height="12" rx="2" /><path d="m16 10 5-3v10l-5-3z" /></>,
        mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v4m-4 0h8" /></>,
        stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
        play: <path d="m7 4 13 8-13 8z" />,
        pause: <><path d="M7 4h4v16H7z" /><path d="M15 4h4v16h-4z" /></>,
        next: <><path d="M5 5v14l11-7z" /><path d="M19 5v14" /></>,
        clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
        eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
        expand: <><path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3" /></>,
        close: <><path d="m18 6-12 12M6 6l12 12" /></>,
        shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z" /><path d="m9 12 2 2 4-4" /></>,
        phone: <><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M11 18h2" /></>,
        monitor: <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" /></>,
        alert: <><path d="M12 3 2 21h20z" /><path d="M12 9v4m0 4h.01" /></>,
    };
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name] || shapes.monitor}</svg>;
}

const fmt = (seconds) => {
    const s = Math.max(0, seconds);
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

function loadSetup() {
    try {
        return JSON.parse(sessionStorage.getItem("nexhire_interview_setup") || "{}");
    } catch {
        return {};
    }
}

function pickMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

export default function InterviewRoom() {
    const navigate = useNavigate();
    const videoRef = useRef(null);
    const streamRef = useRef(null);
    const recorderRef = useRef(null);
    const chunksRef = useRef([]);
    const animationRef = useRef(null);
    const recordingStartedRef = useRef(0);
    const recordingSecondsRef = useRef(0);
    const blobUrlRef = useRef(null);
    const sessionStartRef = useRef(Date.now());
    const mountedAtRef = useRef(Date.now());
    const questionIndexRef = useRef(0);
    const cameraOnRef = useRef(true);
    const micOnRef = useRef(true);

    // focus-warning tracking
    const awayRef = useRef(false);
    const warningsRef = useRef(0);
    const finishedRef = useRef(false);
    const finishRef = useRef(() => { });

    const [setup] = useState(loadSetup);
    const [stream, setStream] = useState(null);
    const [questionIndex, setQuestionIndex] = useState(0);
    const [questions, setQuestions] = useState([]);
    const [questionsLoading, setQuestionsLoading] = useState(true);
    const [questionsError, setQuestionsError] = useState("");
    const [elapsed, setElapsed] = useState(0);
    const [recordingSeconds, setRecordingSeconds] = useState(0);
    const [cameraOn, setCameraOn] = useState(true);
    const [micOn, setMicOn] = useState(true);
    const [recording, setRecording] = useState(false);
    const [recordingPaused, setRecordingPaused] = useState(false);
    const [recordedBlob, setRecordedBlob] = useState(null);
    const [recordedUrl, setRecordedUrl] = useState("");
    const [showPlayback, setShowPlayback] = useState(false);
    const [showTranscript, setShowTranscript] = useState(true);
    const [liveTranscript, setLiveTranscript] = useState("");
    const [transcriptionStatus, setTranscriptionStatus] = useState("idle");
    const [transcriptionError, setTranscriptionError] = useState("");
    const recognitionRef = useRef(null);
    const transcriptBaseRef = useRef("");
    const transcriptionActiveRef = useRef(false);
    const recordingActiveRef = useRef(false);
    const [micLevel, setMicLevel] = useState(0);
    const [deviceError, setDeviceError] = useState("");
    const [logs, setLogs] = useState([]);
    const [showBreak, setShowBreak] = useState(false);
    const [showEndConfirm, setShowEndConfirm] = useState(false);
    const [showWarning, setShowWarning] = useState(false);
    const [warnings, setWarnings] = useState(0);
    const [tipsVisible, setTipsVisible] = useState(true);
    const [fullscreen, setFullscreen] = useState(false);
    const [answers, setAnswers] = useState({});
    const [visited, setVisited] = useState([]);
    const [monitorStatus, setMonitorStatus] = useState("Connecting to AI...");
    const [visionData, setVisionData] = useState(null);
    const [backendError, setBackendError] = useState("");
    const frameBusyRef = useRef(false);

    const interviewType = ["Technical", "HR", "Mixed"].includes(setup.interviewType)
        ? setup.interviewType : ["Technical", "HR", "Mixed"].includes(setup.type) ? setup.type : "Mixed";
    const role = setup.customRole || setup.role || "General Interview";
    const experience = setup.experience || setup.experienceLevel || "Entry Level";
    const difficulty = setup.difficulty || "Medium";
    const questionCount = Math.max(5, Math.min(20, Number(setup.questionCount) || 10));
    const progress = Math.round(((questionIndex + 1) / questionCount) * 100);

    // The backend tracker is the single source of truth for face count and identity state.
    const detectedFaceCount = Number(visionData?.face_count ?? visionData?.candidate?.face_count ?? 0);
    const candidateStatus = String(visionData?.candidate?.status || "");
    const cameraWarning = !cameraOn || !stream || !visionData
        ? null
        : detectedFaceCount >= 2 || candidateStatus === "MULTIPLE_FACES_DETECTED"
            ? { tone: "danger", title: `MULTIPLE FACES DETECTED (${Math.max(detectedFaceCount, 2)})`, detail: "Please ensure you are alone in the frame. Interview analysis is paused." }
            : candidateStatus === "DIFFERENT_PERSON_DETECTED"
                ? { tone: "danger", title: "DIFFERENT PERSON DETECTED", detail: "The original candidate must return. Candidate identity will not be switched." }
                : detectedFaceCount === 0 || candidateStatus === "CANDIDATE_NOT_DETECTED"
                    ? { tone: "warning", title: "FACE NOT DETECTED", detail: "Move into view of the camera." }
                    : candidateStatus === "CANDIDATE_UNCERTAIN"
                        ? { tone: "warning", title: "CANDIDATE VERIFICATION REQUIRED", detail: "Hold still while your identity is checked." }
                        : null;

    useEffect(() => { questionIndexRef.current = questionIndex; }, [questionIndex]);
    useEffect(() => { cameraOnRef.current = cameraOn; }, [cameraOn]);
    useEffect(() => { micOnRef.current = micOn; }, [micOn]);

    const addLog = useCallback((message) => {
        const time = fmt(Math.floor((Date.now() - sessionStartRef.current) / 1000));
        setLogs((old) => [{ id: `${Date.now()}-${Math.random()}`, time, message }, ...old].slice(0, 30));
    }, []);

    // Generate role-specific interview questions through the FastAPI/Gemini backend.
    useEffect(() => {
        let cancelled = false;
        const controller = new AbortController();

        async function fetchGeneratedQuestions() {
            setQuestionsLoading(true);
            setQuestionsError("");
            setQuestions([]);

            try {
                const response = await fetch(
                    "http://127.0.0.1:8000/api/interview/generate-questions",
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        signal: controller.signal,
                        body: JSON.stringify({
                            role: setup.customRole || setup.role || "General Interview",
                            experience: setup.experience || setup.experienceLevel || "Fresher",
                            interviewType,
                            difficulty,
                            questionCount,
                            skills: Array.isArray(setup.skills) ? setup.skills : [],
                        }),
                    }
                );

                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(data.detail || `Question API returned ${response.status}`);
                }
                if (!data.success || !Array.isArray(data.questions) || data.questions.length !== questionCount) {
                    throw new Error("The backend did not return the expected number of questions.");
                }

                if (!cancelled) {
                    setQuestions(data.questions);
                    setQuestionIndex(0);
                    addLog(`Generated ${data.questions.length} interview questions with Gemini`);
                }
            } catch (error) {
                if (!cancelled && error.name !== "AbortError") {
                    setQuestionsError(error.message || "Unable to generate interview questions.");
                    addLog("AI question generation failed");
                }
            } finally {
                if (!cancelled) setQuestionsLoading(false);
            }
        }

        fetchGeneratedQuestions();
        return () => {
            cancelled = true;
            controller.abort();
        };
    }, [setup, interviewType, difficulty, questionCount, addLog]);

    /* ---------- session timer ---------- */
    useEffect(() => {
        const id = window.setInterval(() => setElapsed((v) => v + 1), 1000);
        return () => window.clearInterval(id);
    }, []);

    /* ---------- device connection ---------- */
    const connectDevices = useCallback(async () => {
        if (!navigator.mediaDevices?.getUserMedia) {
            setDeviceError("Camera access is not supported by this browser.");
            return null;
        }
        try {
            const next = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            streamRef.current?.getTracks().forEach((t) => t.stop());
            next.getVideoTracks().forEach((t) => { t.enabled = cameraOnRef.current; });
            next.getAudioTracks().forEach((t) => { t.enabled = micOnRef.current; });
            streamRef.current = next;
            setStream(next);
            setDeviceError("");
            addLog("Camera and microphone connected");
            return next;
        } catch {
            setDeviceError("Camera/microphone permission failed. Allow access in your browser settings and retry.");
            addLog("Camera or microphone access failed");
            return null;
        }
    }, [addLog]);

    useEffect(() => {
        let alive = true;
        (async () => {
            if (!navigator.mediaDevices?.getUserMedia) {
                setDeviceError("Camera access is not supported by this browser.");
                return;
            }
            try {
                const next = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                if (!alive) {
                    next.getTracks().forEach((t) => t.stop());
                    return;
                }
                next.getVideoTracks().forEach((t) => { t.enabled = cameraOnRef.current; });
                next.getAudioTracks().forEach((t) => { t.enabled = micOnRef.current; });
                streamRef.current = next;
                setStream(next);
                setDeviceError("");
                addLog("Camera and microphone connected");
            } catch {
                if (alive) setDeviceError("Camera/microphone permission failed. Allow access in your browser settings and retry.");
            }
        })();

        return () => {
            alive = false;
            streamRef.current?.getTracks().forEach((t) => t.stop());
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // attach stream to <video>
    useEffect(() => {
        const v = videoRef.current;
        if (!v) return;
        v.srcObject = stream || null;
        if (stream) v.play?.().catch(() => { });
    }, [stream]);

    /* ---------- live vision backend integration ---------- */
    useEffect(() => {
        if (!cameraOn || !stream) {
            setMonitorStatus(cameraOn ? "Camera unavailable" : "Camera off");
            return;
        }
        let active = true;
        let canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        let intervalId;

        const sendFrame = async () => {
            const video = videoRef.current;
            if (!active || frameBusyRef.current || !video || !context ||
                video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
                !video.videoWidth || !video.videoHeight) return;
            frameBusyRef.current = true;
            try {
                const width = Math.min(video.videoWidth, 480);
                const height = Math.round(video.videoHeight * width / video.videoWidth);
                canvas.width = width;
                canvas.height = height;
                context.drawImage(video, 0, 0, width, height);
                const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.75));
                if (!active || !blob) return;
                const formData = new FormData();
                formData.append("file", blob, "frame.jpg");
                const response = await fetch("http://127.0.0.1:8000/api/vision/frame", { method: "POST", body: formData });
                if (!response.ok) throw new Error(`Vision API returned ${response.status}`);
                const payload = await response.json();
                if (!active) return;
                if (!payload.success || !payload.result) throw new Error("The vision API returned no analysis result.");
                setVisionData(payload.result);
                setBackendError("");
                const candidate = payload.result.candidate;
                setMonitorStatus(candidate?.analysis_allowed ? "AI monitoring active" : candidate?.status || "Detecting candidate...");
            } catch (error) {
                if (!active) return;
                setBackendError(error?.message || "Could not connect to the vision backend.");
                setMonitorStatus("Backend unavailable");
            } finally {
                frameBusyRef.current = false;
            }
        };

        setMonitorStatus("Connecting to AI...");
        intervalId = window.setInterval(sendFrame, 500);
        sendFrame();

        return () => {
            active = false;
            window.clearInterval(intervalId);
            canvas = null;
            frameBusyRef.current = false;
        };
    }, [cameraOn, stream]);

    useEffect(() => {
        stream?.getVideoTracks().forEach((t) => { t.enabled = cameraOn; });
    }, [cameraOn, stream]);

    useEffect(() => {
        stream?.getAudioTracks().forEach((t) => { t.enabled = micOn; });
        if (!micOn) setMicLevel(0);
    }, [micOn, stream]);

    /* ---------- mic level meter ---------- */
    useEffect(() => {
        if (!micOn || !stream || !stream.getAudioTracks().length) return;
        let cancelled = false;
        let context;
        try {
            context = new (window.AudioContext || window.webkitAudioContext)();
            if (context.state === "suspended") context.resume().catch(() => { });
            const analyser = context.createAnalyser();
            analyser.fftSize = 256;
            const source = context.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
            source.connect(analyser);
            const data = new Uint8Array(analyser.frequencyBinCount);
            const tick = () => {
                if (cancelled) return;
                analyser.getByteTimeDomainData(data);
                let sum = 0;
                for (const value of data) sum += (value - 128) ** 2;
                setMicLevel(Math.min(100, Math.round(Math.sqrt(sum / data.length) * 2.5)));
                animationRef.current = requestAnimationFrame(tick);
            };
            tick();
        } catch {
            setMicLevel(0);
        }
        return () => {
            cancelled = true;
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            if (context && context.state !== "closed") context.close().catch(() => { });
        };
    }, [micOn, stream]);

    /* ---------- tab / window focus warnings (max 3 → auto end) ---------- */
    useEffect(() => {
        const handleLeave = () => {
            if (awayRef.current || finishedRef.current) return;
            if (Date.now() - mountedAtRef.current < GRACE_MS) return;
            awayRef.current = true;
            warningsRef.current += 1;
            const n = warningsRef.current;
            setWarnings(n);
            addLog(`Left interview tab/window — warning ${n}/${MAX_WARNINGS}`);
        };

        const handleReturn = () => {
            if (!awayRef.current || finishedRef.current) return;
            awayRef.current = false;
            if (warningsRef.current >= MAX_WARNINGS) {
                finishRef.current(`Interview ended automatically after ${MAX_WARNINGS} tab/window warnings.`);
            } else {
                setShowWarning(true);
            }
        };

        const onVisibility = () => (document.hidden ? handleLeave() : handleReturn());

        document.addEventListener("visibilitychange", onVisibility);
        window.addEventListener("blur", handleLeave);
        window.addEventListener("focus", handleReturn);
        return () => {
            document.removeEventListener("visibilitychange", onVisibility);
            window.removeEventListener("blur", handleLeave);
            window.removeEventListener("focus", handleReturn);
        };
    }, [addLog]);

    useEffect(() => {
        const fn = () => setFullscreen(Boolean(document.fullscreenElement));
        document.addEventListener("fullscreenchange", fn);
        return () => document.removeEventListener("fullscreenchange", fn);
    }, []);

    /* ---------- live speech transcription (browser Web Speech API) ---------- */
    const stopLiveTranscription = () => {
        transcriptionActiveRef.current = false;
        const recognition = recognitionRef.current;
        recognitionRef.current = null;
        if (recognition) {
            try { recognition.onend = null; recognition.stop(); } catch { /* already stopped */ }
        }
        setTranscriptionStatus("stopped");
    };

    const startLiveTranscription = () => {
        const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognitionAPI) {
            setTranscriptionStatus("unsupported");
            setTranscriptionError("Live transcription is not supported by this browser. Try the latest Google Chrome, or continue recording and add API-based transcription later.");
            return;
        }

        if (recognitionRef.current) {
            try { recognitionRef.current.onend = null; recognitionRef.current.stop(); } catch { /* ignore */ }
            recognitionRef.current = null;
        }

        setTranscriptionError("");
        setTranscriptionStatus("listening");
        transcriptionActiveRef.current = true;

        const recognition = new SpeechRecognitionAPI();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-IN";

        recognition.onresult = (event) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const result = event.results[i];
                const phrase = result[0]?.transcript?.trim();
                if (!phrase) continue;
                if (result.isFinal) {
                    transcriptBaseRef.current = `${transcriptBaseRef.current} ${phrase}`.trim();
                } else {
                    interim += `${phrase} `;
                }
            }
            setLiveTranscript(`${transcriptBaseRef.current}${interim ? ` ${interim.trim()}` : ""}`.trim());
        };

        recognition.onerror = (event) => {
            if (event.error === "no-speech") return;
            if (event.error === "aborted" && !transcriptionActiveRef.current) return;
            setTranscriptionError(event.error === "not-allowed"
                ? "Microphone access for live transcription was denied. Check your browser's microphone permission."
                : `Live transcription error: ${event.error}. Audio recording can still continue.`);
            setTranscriptionStatus("error");
        };

        recognition.onend = () => {
            if (recognitionRef.current === recognition) recognitionRef.current = null;
            if (transcriptionActiveRef.current && recordingActiveRef.current) {
                startLiveTranscription();
            } else if (!transcriptionActiveRef.current) {
                setTranscriptionStatus("stopped");
            }
        };

        recognitionRef.current = recognition;
        try {
            recognition.start();
        } catch {
            recognitionRef.current = null;
            transcriptionActiveRef.current = false;
            setTranscriptionStatus("error");
            setTranscriptionError("Could not start live transcription. You can still record and play back your answer.");
        }
    };

    /* ---------- recording ---------- */
    const startRecording = async () => {
        if (!micOn) {
            setDeviceError("Turn on the microphone before recording.");
            return;
        }
        if (typeof MediaRecorder === "undefined") {
            setDeviceError("Recording is not supported in this browser.");
            return;
        }

        let active = streamRef.current;
        let audioTracks = active ? active.getAudioTracks().filter((t) => t.readyState === "live") : [];

        // stream missing or mic track ended → reconnect automatically
        if (!audioTracks.length) {
            active = await connectDevices();
            audioTracks = active ? active.getAudioTracks().filter((t) => t.readyState === "live") : [];
        }
        if (!audioTracks.length) {
            setDeviceError("Connect your devices: no active microphone was found. Retry device access.");
            return;
        }
        audioTracks.forEach((t) => { t.enabled = true; });

        try {
            const audioStream = new MediaStream(audioTracks);
            const mimeType = pickMimeType();
            let recorder;
            try {
                recorder = mimeType ? new MediaRecorder(audioStream, { mimeType }) : new MediaRecorder(audioStream);
            } catch {
                recorder = new MediaRecorder(audioStream);
            }

            chunksRef.current = [];
            transcriptBaseRef.current = "";
            setLiveTranscript("");
            setTranscriptionError("");
            setTranscriptionStatus("starting");
            recorderRef.current = recorder;
            const qIndex = questionIndexRef.current;

            recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data); };
            recorder.onerror = () => {
                setDeviceError("Recording error occurred. Retry device access.");
                setRecording(false);
                setRecordingPaused(false);
            };
            recorder.onstop = () => {
                recordingActiveRef.current = false;
                stopLiveTranscription();
                const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || "audio/webm" });
                if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
                const url = URL.createObjectURL(blob);
                blobUrlRef.current = url;
                setRecordedBlob(blob);
                setRecordedUrl(url);
                setShowPlayback(true);
                setRecording(false);
                setRecordingPaused(false);
                setAnswers((old) => ({
                    ...old,
                    [qIndex]: {
                        ...(old[qIndex] || {}),
                        audioSize: blob.size,
                        audioType: blob.type,
                        duration: recordingSecondsRef.current,
                        savedAt: new Date().toISOString(),
                    },
                }));
                addLog(`Answer recording saved for question ${qIndex + 1}`);
            };

            recorder.start(250);
            recordingActiveRef.current = true;
            startLiveTranscription();
            recordingStartedRef.current = Date.now();
            recordingSecondsRef.current = 0;
            setRecordingSeconds(0);
            setRecordedBlob(null);
            setRecordedUrl("");
            setShowPlayback(false);
            setRecording(true);
            setRecordingPaused(false);
            setDeviceError("");
            addLog(`Started recording answer ${qIndex + 1}`);
        } catch (err) {
            setDeviceError("Could not start recording. Retry device access.");
            addLog(`Recording failed to start${err?.name ? ` (${err.name})` : ""}`);
        }
    };

    useEffect(() => {
        if (!recording || recordingPaused) return;
        const id = window.setInterval(() => {
            const seconds = Math.floor((Date.now() - recordingStartedRef.current) / 1000);
            recordingSecondsRef.current = seconds;
            setRecordingSeconds(seconds);
        }, 250);
        return () => window.clearInterval(id);
    }, [recording, recordingPaused]);

    const stopRecording = () => {
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            try { recorder.requestData(); } catch { /* ignore */ }
            recorder.stop();
        }
    };

    const togglePause = () => {
        const recorder = recorderRef.current;
        if (!recorder) return;
        if (recorder.state === "recording") {
            recorder.pause();
            recordingActiveRef.current = false;
            stopLiveTranscription();
            setRecordingPaused(true);
            addLog("Answer recording paused");
        } else if (recorder.state === "paused") {
            recordingStartedRef.current = Date.now() - recordingSecondsRef.current * 1000;
            recorder.resume();
            recordingActiveRef.current = true;
            startLiveTranscription();
            setRecordingPaused(false);
            addLog("Answer recording resumed");
        }
    };

    const discardRecording = () => {
        recordingActiveRef.current = false;
        stopLiveTranscription();
        transcriptBaseRef.current = "";
        setLiveTranscript("");
        setTranscriptionError("");

        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.onstop = null;
            recorder.stop();
        }
        const qIndex = questionIndexRef.current;
        setRecording(false);
        setRecordingPaused(false);
        setRecordedBlob(null);
        setRecordedUrl("");
        setRecordingSeconds(0);
        recordingSecondsRef.current = 0;
        setShowPlayback(false);
        setAnswers((old) => {
            const next = { ...old };
            if (next[qIndex]) {
                next[qIndex] = { ...next[qIndex] };
                delete next[qIndex].audioSize;
                delete next[qIndex].audioType;
                delete next[qIndex].duration;
                delete next[qIndex].savedAt;
            }
            return next;
        });
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
        addLog(`Discarded recording for question ${qIndex + 1}`);
    };

    const moveQuestion = (nextIndex) => {
        if (recording) {
            setDeviceError("Stop your recording before changing questions.");
            return;
        }
        if (nextIndex < 0 || nextIndex >= questionCount) return;
        setVisited((old) => (old.includes(questionIndex) ? old : [...old, questionIndex]));
        setQuestionIndex(nextIndex);
        setRecordedBlob(null);
        setRecordedUrl("");
        setRecordingSeconds(0);
        recordingSecondsRef.current = 0;
        setShowPlayback(false);
        transcriptBaseRef.current = "";
        setLiveTranscript("");
        setTranscriptionStatus("idle");
        setTranscriptionError("");
        setDeviceError("");
        addLog(`Moved to question ${nextIndex + 1}`);
    };

    const toggleFullscreen = async () => {
        try {
            if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
            else await document.exitFullscreen();
        } catch {
            setDeviceError("Fullscreen is unavailable in this browser.");
        }
    };

    const takeBreak = () => {
        if (recording) {
            setDeviceError("Stop recording before taking a break.");
            return;
        }
        setShowBreak(true);
        addLog("Candidate took a break");
    };

    const finishInterview = (reason = "") => {
        if (finishedRef.current) return;
        finishedRef.current = true;

        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.onstop = null;
            try { recorder.stop(); } catch { /* ignore */ }
        }

        const report = {
            role,
            experience,
            interviewType,
            difficulty,
            totalQuestions: questions.length,
            completedQuestions: visited.includes(questionIndex) ? visited.length : visited.length + 1,
            durationSeconds: elapsed,
            answers: Object.entries(answers).map(([index, answer]) => ({
                questionNumber: Number(index) + 1,
                question: questions[Number(index)] || "Question unavailable",
                ...answer,
            })),
            attentionEvents: logs,
            warnings: warningsRef.current,
            maxWarnings: MAX_WARNINGS,
            endReason: reason || "Completed by candidate",
            monitoringStatus: monitorStatus,
            visionResults: visionData,
            visionBackendError: backendError || null,
            finishedAt: new Date().toISOString(),
            note: "Questions generated by Gemini. Audio recordings remain browser-local; resume parsing and AI answer evaluation are not yet integrated.",
        };

        sessionStorage.setItem("nexhire_interview_report", JSON.stringify(report));
        if (document.fullscreenElement) document.exitFullscreen().catch(() => { });
        navigate("/interview/report");
    };

    // always point to the latest closure so event listeners never use stale state
    finishRef.current = finishInterview;

    const needsRetry =
        deviceError.toLowerCase().includes("retry") ||
        deviceError.toLowerCase().includes("permission") ||
        deviceError.toLowerCase().includes("connect your devices");

    return (
        <div className="ir-root">
            <style>{CSS}</style>

            <header className="ir-top">
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    <div className="ir-brand">Nex<span>Hire</span></div>
                    <div style={{ height: 21, width: 1, background: "#293441" }} />
                    <div>
                        <div style={{ fontSize: 10, fontWeight: 600 }}>Assessment Workspace</div>
                        <div className="ir-muted" style={{ fontSize: 8 }}>Interview session</div>
                    </div>
                </div>
                <div className="ir-topright">
                    <span className={`ir-pill ir-warnpill ${warnings >= MAX_WARNINGS - 1 && warnings > 0 ? "ir-critical" : ""}`}>
                        <Icon name="alert" size={10} /> Warnings {warnings}/{MAX_WARNINGS}
                    </span>
                    <span className="ir-pill"><span className="ir-dot" /> Active</span>
                    <span className="ir-pill"><Icon name="clock" size={10} /> {fmt(elapsed)}</span>
                    <button className="ir-btn ir-danger" onClick={() => setShowEndConfirm(true)} disabled={questionsLoading || Boolean(questionsError) || !questions.length}>
                        <Icon name="close" size={10} /> End
                    </button>
                </div>
            </header>

            <main className="ir-shell">
                <div className="ir-alert">
                    <div>
                        <strong>Interview in progress</strong>
                        <span style={{ marginLeft: 6 }}>
                            Switching tabs or windows gives a warning. After {MAX_WARNINGS} warnings the interview ends automatically.
                        </span>
                    </div>
                    <button className="ir-btn" onClick={toggleFullscreen}><Icon name="expand" size={10} /> {fullscreen ? "Exit full" : "Fullscreen"}</button>
                </div>

                <section className="ir-heading">
                    <div>
                        <div className="ir-eyebrow">Assessment session</div>
                        <h1 className="ir-title">{role}</h1>
                        <div className="ir-subtitle">{experience} · {interviewType} · {difficulty}</div>
                    </div>
                    <div className="ir-progress-wrap">
                        <div className="ir-progress-label"><span>Question {questionIndex + 1} / {questionCount}</span><span>{progress}%</span></div>
                        <div className="ir-progress"><div style={{ width: `${progress}%` }} /></div>
                    </div>
                </section>

                <section className="ir-grid">
                    <article className="ir-card">
                        <div className="ir-cardhead">
                            <span className="ir-cardtitle">Interview question</span>
                            <div style={{ display: "flex", gap: 4 }}>
                                <span className="ir-pill">{interviewType}</span>
                                <span className="ir-pill">{difficulty}</span>
                            </div>
                        </div>
                        <div className="ir-body">
                            <div className="ir-question">
                                <div className="ir-qmeta">
                                    {questionsLoading ? "Generating questions..." : `AI-generated question · ${questionIndex + 1}`}
                                </div>

                                {questionsLoading ? (
                                    <p role="status">Gemini is preparing your personalized interview questions. Please wait...</p>
                                ) : questionsError ? (
                                    <div role="alert" style={{ color: "#ffadb4" }}>
                                        <p>{questionsError}</p>
                                        <button className="ir-btn ir-primary" onClick={() => window.location.reload()}>
                                            Retry
                                        </button>
                                    </div>
                                ) : (
                                    <>
                                        <h2>{questions[questionIndex]}</h2>
                                        <p>Explain your approach clearly. Give a relevant example and structure your answer with key steps and reasoning.</p>
                                    </>
                                )}
                            </div>

                            <div className="ir-sectionhead">
                                <span className="ir-sectiontitle">Your answer</span>
                                <span className="ir-muted">Suggested: 2–3 min</span>
                            </div>

                            <div className="ir-recorder">
                                <div className="ir-recicon"><Icon name="mic" size={15} /></div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div className="ir-time">{fmt(recordingSeconds)}</div>
                                    <div className="ir-recstatus">
                                        {recording ? (recordingPaused ? "Paused" : "Recording…") : recordedBlob ? "Recording saved in this session" : "Ready to record"}
                                    </div>
                                </div>
                                {recording ? (
                                    <button className="ir-btn ir-danger" onClick={stopRecording}><Icon name="stop" size={10} /> Stop</button>
                                ) : recordedBlob ? (
                                    <button className="ir-btn" onClick={() => setShowPlayback((v) => !v)}>{showPlayback ? "Hide audio" : "Review"}</button>
                                ) : (
                                    <button className="ir-btn ir-primary" onClick={startRecording}><Icon name="mic" size={10} /> Record</button>
                                )}
                            </div>

                            {recordedBlob && recordedUrl && showPlayback && (
                                <div className="ir-panel">
                                    <div className="ir-panel-head">
                                        <span className="ir-panel-title">Answer recording</span>
                                        <span className="ir-panel-meta">
                                            {fmt(recordingSeconds)} · {Math.max(1, Math.round((recordedBlob.size || 0) / 1024))} KB
                                        </span>
                                    </div>
                                    <audio controls preload="metadata" src={recordedUrl} />
                                </div>
                            )}

                            <div className="ir-panel">
                                <div className="ir-panel-head">
                                    <span className="ir-panel-title">Live transcript</span>
                                    <div className="ir-panel-actions">
                                        <span className="ir-pill" style={transcriptionStatus === "listening" ? { color: "#00c99a", borderColor: "#1d4a3f" } : undefined}>
                                            {transcriptionStatus === "listening" ? "Listening" :
                                                transcriptionStatus === "starting" ? "Starting" :
                                                    transcriptionStatus === "unsupported" ? "Unsupported" :
                                                        transcriptionStatus === "error" ? "Issue" :
                                                            transcriptionStatus === "stopped" ? "Stopped" : "Ready"}
                                        </span>
                                        <button className="ir-btn ir-btn-sm" onClick={() => setShowTranscript((v) => !v)}>
                                            {showTranscript ? "Hide" : "Show"}
                                        </button>
                                    </div>
                                </div>
                                {showTranscript && (
                                    <>
                                        <div
                                            aria-live="polite"
                                            className={`ir-transcript-body ${liveTranscript ? "" : "is-empty"}`}
                                        >
                                            {liveTranscript || (recording ? "Listening… recognized words appear here." : "Start recording to see your transcript.")}
                                        </div>
                                        {transcriptionError && <div className="ir-panel-error">{transcriptionError}</div>}
                                        <div className="ir-panel-foot">Browser speech recognition (prototype). Accuracy and privacy depend on your browser.</div>
                                    </>
                                )}
                            </div>

                            {deviceError && (
                                <div style={{ marginTop: 6, padding: 6, borderRadius: 4, border: "1px solid #59313a", color: "#ffadb4", fontSize: 9 }}>
                                    {deviceError}
                                    {needsRetry && (
                                        <button className="ir-btn" style={{ marginLeft: 5 }} onClick={connectDevices}>Retry</button>
                                    )}
                                </div>
                            )}

                            <div className="ir-controls">
                                {recording ? (
                                    <button className="ir-btn" onClick={togglePause}><Icon name={recordingPaused ? "play" : "pause"} size={10} /> {recordingPaused ? "Resume" : "Pause"}</button>
                                ) : (
                                    <button className="ir-btn" onClick={startRecording} disabled={Boolean(recordedBlob) || questionsLoading || Boolean(questionsError) || !questions.length}><Icon name="mic" size={10} /> {recordedBlob ? "Recorded" : "Start answer"}</button>
                                )}
                                <button className="ir-btn" onClick={discardRecording} disabled={!recording && !recordedBlob}><Icon name="close" size={10} /> Discard</button>
                            </div>

                            <div className="ir-nav">
                                <button className="ir-btn" onClick={() => moveQuestion(questionIndex + 1)} disabled={questionsLoading || Boolean(questionsError) || !questions.length || recording || questionIndex >= questions.length - 1}>Skip <Icon name="next" size={10} /></button>
                                <span className="ir-counter">{questionIndex + 1} / {questionCount}</span>
                                {questionIndex < questions.length - 1 ? (
                                    <button className="ir-btn ir-primary" onClick={() => moveQuestion(questionIndex + 1)} disabled={questionsLoading || Boolean(questionsError) || !questions.length || recording}>Next <Icon name="next" size={10} /></button>
                                ) : (
                                    <button className="ir-btn ir-primary" onClick={() => setShowEndConfirm(true)} disabled={questionsLoading || Boolean(questionsError) || !questions.length}>Finish</button>
                                )}
                            </div>
                        </div>
                    </article>

                    <article className="ir-card">
                        <div className="ir-cardhead">
                            <span className="ir-cardtitle">Camera preview</span>
                            <span className="ir-pill"><span className="ir-dot" />{cameraOn && stream ? "Live" : "Off"}</span>
                        </div>
                        <div className="ir-body">
                            <div className="ir-camera">
                                {/* video is always mounted so the stream stays attached */}
                                <video
                                    ref={videoRef}
                                    autoPlay
                                    playsInline
                                    muted
                                    style={{ display: cameraOn && stream ? "block" : "none" }}
                                />
                                {!(cameraOn && stream) && (
                                    <div className="ir-placeholder">
                                        <Icon name="camera" size={23} />
                                        <strong>{cameraOn ? "Connecting camera…" : "Camera is off"}</strong>
                                        <span>{deviceError || "Enable camera access to preview video"}</span>
                                    </div>
                                )}
                                {cameraWarning && (
                                    <div
                                        className="ir-camera-warning"
                                        role="alert"
                                        aria-live="assertive"
                                    >
                                        {cameraWarning.tone === "danger" && cameraWarning.title.startsWith("MULTIPLE")
                                            ? "Multiple faces detected — please stay alone in the frame."
                                            : cameraWarning.title === "DIFFERENT PERSON DETECTED"
                                                ? "Different person detected — original candidate must return."
                                                : cameraWarning.title === "FACE NOT DETECTED"
                                                    ? "Face not detected — move into camera view."
                                                    : "Please hold still while your identity is verified."}
                                    </div>
                                )}
                                <div className="ir-overlay">
                                    <div className="ir-overlaygroup">
                                        <button className="ir-btn" title="Toggle camera" onClick={() => setCameraOn((v) => !v)}><Icon name="camera" size={11} /></button>
                                        <button className="ir-btn" title="Toggle microphone" onClick={() => setMicOn((v) => !v)}><Icon name="mic" size={11} /></button>
                                    </div>
                                    <button className="ir-btn ir-danger" onClick={takeBreak}><Icon name="pause" size={10} /> Break</button>
                                </div>
                            </div>

                            <div className="ir-meter-label"><span>Microphone level</span><span className="ir-green">{micOn ? `${micLevel}%` : "Muted"}</span></div>
                            <div className="ir-meter"><div style={{ width: `${micOn ? micLevel : 0}%` }} /></div>
                            <div className="ir-device-row">
                                <button className="ir-btn" onClick={connectDevices}><Icon name="monitor" size={10} /> Reconnect devices</button>
                                <button className="ir-btn" onClick={toggleFullscreen}><Icon name="expand" size={10} /> Fullscreen</button>
                            </div>
                            <p className="ir-note">Local camera preview. Visual AI analysis will be connected to your backend modules later.</p>
                        </div>
                    </article>
                </section>

                <section className="ir-bottom">
                    <article className="ir-card">
                        <div className="ir-cardhead">
                            <span className="ir-cardtitle"><Icon name="monitor" size={11} /> Live monitoring</span>
                            <span className="ir-pill">{monitorStatus}</span>
                        </div>
                        <div className="ir-body">
                            <div className="ir-metrics">
                                <div className="ir-metric"><div className="ir-metric-label"><Icon name="eye" size={10} /> Eye contact</div><div className="ir-metric-value">{visionData?.eye_contact?.state || "Waiting for face"}</div></div>
                                <div className="ir-metric"><div className="ir-metric-label">Head pose</div><div className="ir-metric-value">{visionData?.head_pose?.valid ? (visionData.head_pose.facing_camera ? "Facing camera" : "Looking away") : "Awaiting analysis"}</div></div>
                                <div className="ir-metric"><div className="ir-metric-label"><Icon name="shield" size={10} /> Liveness</div><div className="ir-metric-value">{visionData?.liveness?.status || "Awaiting analysis"}</div></div>
                                <div className="ir-metric"><div className="ir-metric-label"><Icon name="phone" size={10} /> Phone</div><div className="ir-metric-value">Not connected</div></div>
                            </div>
                            <p className="ir-note">{backendError ? `Vision backend: ${backendError}` : visionData?.candidate?.message || "Results update as webcam frames are analyzed."}</p>
                        </div>
                    </article>

                    <article className="ir-card">
                        <div className="ir-cardhead">
                            <span className="ir-cardtitle">Attention log</span>
                            <span className="ir-pill">{logs.length} events</span>
                        </div>
                        <div className="ir-body">
                            {logs.length ? (
                                <div className="ir-loglist">
                                    {logs.map((log) => <div className="ir-log" key={log.id}><span className="ir-logtime">{log.time}</span><span>{log.message}</span></div>)}
                                </div>
                            ) : (
                                <div className="ir-empty">No focus events recorded. Browser focus changes alone do not prove misconduct.</div>
                            )}
                        </div>
                    </article>

                    <article className="ir-card">
                        <div className="ir-cardhead">
                            <span className="ir-cardtitle">Interview guidance</span>
                            <button className="ir-btn" onClick={() => setTipsVisible((v) => !v)}>{tipsVisible ? "Hide" : "Show"}</button>
                        </div>
                        {tipsVisible && <div className="ir-body">
                            <ul className="ir-tips">
                                <li>Maintain natural eye contact.</li>
                                <li>Speak clearly and steadily.</li>
                                <li>Structure answers with examples.</li>
                                <li>Pause briefly if needed.</li>
                                <li>Check your microphone level.</li>
                                <li>Do not switch tabs — {MAX_WARNINGS} warnings end the interview.</li>
                            </ul>
                        </div>}
                    </article>
                </section>

                <footer className="ir-footer">
                    <span>NexHire · Interview workspace</span>
                    <span>AI-generated questions · Browser-local recording</span>
                </footer>
            </main>

            {showWarning && (
                <div className="ir-backdrop" role="dialog" aria-modal="true">
                    <div className="ir-modal">
                        <div style={{ color: "#f5bf68", marginBottom: 7 }}><Icon name="alert" size={19} /></div>
                        <h3>Warning {warnings} of {MAX_WARNINGS}</h3>
                        <p>
                            You left the interview tab/window. This has been logged.
                            {warnings === MAX_WARNINGS - 1
                                ? " This is your final warning — leaving again will end the interview automatically."
                                : ` You have ${MAX_WARNINGS - warnings} warning(s) remaining before the interview is ended automatically.`}
                        </p>
                        <div className="ir-modalactions"><button className="ir-btn ir-primary" onClick={() => setShowWarning(false)}>Return to interview</button></div>
                    </div>
                </div>
            )}

            {showBreak && (
                <div className="ir-break">
                    <div className="ir-green"><Icon name="pause" size={26} /></div>
                    <h2>Take a moment</h2>
                    <p>The interview timer continues during this break. Resume when you are ready.</p>
                    <button className="ir-btn ir-primary" onClick={() => { setShowBreak(false); addLog("Interview resumed after break"); }}>Resume interview</button>
                </div>
            )}

            {showEndConfirm && (
                <div className="ir-backdrop" role="dialog" aria-modal="true">
                    <div className="ir-modal">
                        <h3>End this interview?</h3>
                        <p>Your temporary session summary will be saved to session storage and you will be redirected to the report page. An active recording will be stopped.</p>
                        <div className="ir-modalactions">
                            <button className="ir-btn" onClick={() => setShowEndConfirm(false)}>Continue</button>
                            <button className="ir-btn ir-danger" onClick={() => finishInterview("Ended by candidate")}>End interview</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}