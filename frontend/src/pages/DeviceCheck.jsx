
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const CheckIcon = ({ ok }) => (
    <span
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${ok
            ? "bg-emerald-400/15 text-emerald-400"
            : "bg-white/5 text-slate-500"
            }`}
    >
        {ok ? "✓" : "•"}
    </span>
);

function DeviceCheck() {
    const navigate = useNavigate();

    const videoRef = useRef(null);
    const streamRef = useRef(null);
    const audioContextRef = useRef(null);
    const animationRef = useRef(null);
    const faceDetectorRef = useRef(null);
    const detectingRef = useRef(false);

    const [cameraStatus, setCameraStatus] = useState("idle");
    const [micStatus, setMicStatus] = useState("idle");
    const [cameraError, setCameraError] = useState("");
    const [micError, setMicError] = useState("");
    const [micLevel, setMicLevel] = useState(0);
    const [faceStatus, setFaceStatus] = useState("unknown");
    const [faceDetectionSupported, setFaceDetectionSupported] =
        useState(false);
    const [starting, setStarting] = useState(false);

    const cameraReady = cameraStatus === "ready";
    const micReady = micStatus === "ready";
    const allReady = cameraReady && micReady;

    const stopDevices = useCallback(() => {
        if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
            animationRef.current = null;
        }

        detectingRef.current = false;

        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }

        if (audioContextRef.current) {
            audioContextRef.current.close().catch(() => { });
            audioContextRef.current = null;
        }

        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }

        setMicLevel(0);
        setFaceStatus("unknown");
        setCameraStatus("idle");
        setMicStatus("idle");
    }, []);

    useEffect(() => {
        if (!("mediaDevices" in navigator) ||
            !navigator.mediaDevices?.getUserMedia) {
            setCameraError("Camera access requires HTTPS or localhost.");
            setMicError("Microphone access requires HTTPS or localhost.");
            setCameraStatus("error");
            setMicStatus("error");
        }

        if ("FaceDetector" in window) {
            try {
                faceDetectorRef.current = new window.FaceDetector({
                    fastMode: true,
                    maxDetectedFaces: 5,
                });
                setFaceDetectionSupported(true);
            } catch {
                setFaceDetectionSupported(false);
            }
        }

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }

            if (streamRef.current) {
                streamRef.current.getTracks().forEach((track) => track.stop());
            }

            if (audioContextRef.current) {
                audioContextRef.current.close().catch(() => { });
            }
        };
    }, []);

    useEffect(() => {
        const video = videoRef.current;

        if (!cameraReady || !video || !faceDetectorRef.current) {
            return;
        }

        let active = true;
        let lastDetection = 0;

        const detectFace = async (timestamp) => {
            if (!active) return;

            if (
                timestamp - lastDetection >= 500 &&
                video.readyState >= 2 &&
                !detectingRef.current
            ) {
                lastDetection = timestamp;
                detectingRef.current = true;

                try {
                    const faces = await faceDetectorRef.current.detect(video);

                    if (active) {
                        setFaceStatus(
                            faces.length === 1
                                ? "one"
                                : faces.length > 1
                                    ? "multiple"
                                    : "none"
                        );
                    }
                } catch {
                    if (active) setFaceStatus("unsupported");
                } finally {
                    detectingRef.current = false;
                }
            }

            if (active) {
                animationRef.current = requestAnimationFrame(detectFace);
            }
        };

        animationRef.current = requestAnimationFrame(detectFace);

        return () => {
            active = false;

            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
                animationRef.current = null;
            }
        };
    }, [cameraReady]);

    const startChecks = async () => {
        setStarting(true);
        setCameraError("");
        setMicError("");
        setCameraStatus("checking");
        setMicStatus("checking");
        setFaceStatus("unknown");

        try {
            stopDevices();

            setCameraStatus("checking");
            setMicStatus("checking");

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: "user",
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });

            streamRef.current = stream;

            const videoTrack = stream.getVideoTracks()[0];
            const audioTrack = stream.getAudioTracks()[0];

            if (!videoTrack) {
                throw new Error("No camera track was detected.");
            }

            if (!audioTrack) {
                throw new Error("No microphone track was detected.");
            }

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play().catch(() => { });
            }

            setCameraStatus("ready");
            setMicStatus("ready");

            const AudioContextClass =
                window.AudioContext || window.webkitAudioContext;

            if (!AudioContextClass) {
                setMicError("Audio testing is not supported in this browser.");
                setMicStatus("error");
                return;
            }

            const audioContext = new AudioContextClass();
            audioContextRef.current = audioContext;

            await audioContext.resume();

            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();

            analyser.fftSize = 256;
            source.connect(analyser);

            const data = new Uint8Array(analyser.frequencyBinCount);
            let heardAudio = false;

            const measureAudio = () => {
                if (audioContextRef.current !== audioContext) return;

                analyser.getByteTimeDomainData(data);

                let sum = 0;

                for (const value of data) {
                    const normalized = (value - 128) / 128;
                    sum += normalized * normalized;
                }

                const rms = Math.sqrt(sum / data.length);
                const level = Math.min(100, Math.round(rms * 350));

                setMicLevel(level);

                if (level >= 3) {
                    heardAudio = true;
                    setMicStatus("ready");
                } else if (!heardAudio) {
                    setMicStatus("checking");
                }

                animationRef.current = requestAnimationFrame(measureAudio);
            };

            animationRef.current = requestAnimationFrame(measureAudio);
        } catch (error) {
            const message =
                error.name === "NotAllowedError"
                    ? "Permission denied. Allow camera and microphone access in your browser."
                    : error.name === "NotFoundError"
                        ? "Camera or microphone not found. Connect a device and retry."
                        : error.name === "NotReadableError"
                            ? "A device may be in use by another application."
                            : error.message || "Unable to access your devices.";

            setCameraError(message);
            setMicError(message);
            setCameraStatus("error");
            setMicStatus("error");

            if (streamRef.current) {
                streamRef.current.getTracks().forEach((track) => track.stop());
                streamRef.current = null;
            }
        } finally {
            setStarting(false);
        }
    };

    const startInterview = () => {
        if (!allReady) return;

        if (faceDetectionSupported && faceStatus !== "one") return;

        navigate("/interview/room");
    };

    const statusLabel = (status) => {
        if (status === "ready") return "Connected";
        if (status === "checking") return "Testing";
        if (status === "error") return "Needs attention";
        return "Not tested";
    };

    return (
        <div className="min-h-screen bg-[#080b12] text-slate-200">
            {/* Compact navigation */}
            <header className="h-10 border-b border-white/[0.07] px-4 sm:px-7">
                <div className="mx-auto flex h-full max-w-5xl items-center justify-between">
                    <button
                        onClick={() => navigate("/dashboard")}
                        className="flex items-center gap-2"
                    >
                        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[#00b88a]/15 text-[10px] font-bold text-[#00c99a]">
                            NH
                        </span>
                        <span className="text-[11px] font-semibold tracking-wide">
                            NexHire
                        </span>
                    </button>

                    <span className="text-[8px] text-slate-500">
                        PRE-INTERVIEW CHECK
                    </span>
                </div>
            </header>

            <main className="mx-auto max-w-4xl px-3 py-5 sm:px-5">
                <div className="mb-4 text-center">
                    <p className="mb-1 text-[8px] font-semibold uppercase tracking-[0.2em] text-[#00c99a]">
                        Almost ready
                    </p>

                    <h1 className="text-[17px] font-semibold tracking-tight text-white">
                        Check your devices
                    </h1>

                    <p className="mt-1 text-[9px] text-slate-400">
                        Test your camera and microphone before starting.
                    </p>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-[1.4fr_1fr]">
                    {/* Camera preview */}
                    <section className="rounded-lg border border-white/[0.08] bg-[#0b121b] p-2.5">
                        <div className="mb-2 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <CheckIcon ok={cameraReady} />
                                <div>
                                    <h2 className="text-[10px] font-semibold text-white">
                                        Camera
                                    </h2>
                                    <p className="text-[8px] text-slate-500">
                                        Live video preview
                                    </p>
                                </div>
                            </div>

                            <span
                                className={`text-[8px] ${cameraReady
                                    ? "text-emerald-400"
                                    : cameraStatus === "error"
                                        ? "text-red-400"
                                        : "text-slate-500"
                                    }`}
                            >
                                {statusLabel(cameraStatus)}
                            </span>
                        </div>

                        <div className="relative aspect-video overflow-hidden rounded-md border border-white/[0.07] bg-[#06090e]">
                            <video
                                ref={videoRef}
                                autoPlay
                                muted
                                playsInline
                                className={`h-full w-full object-cover ${cameraReady ? "block" : "hidden"
                                    }`}
                            />

                            {!cameraReady && (
                                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.04]">
                                        <svg
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="1.4"
                                            className="h-5 w-5 text-slate-500"
                                        >
                                            <rect
                                                x="3"
                                                y="6"
                                                width="13"
                                                height="12"
                                                rx="2"
                                            />
                                            <path d="m16 10 5-3v10l-5-3" />
                                        </svg>
                                    </div>
                                    <span className="text-[8px] text-slate-500">
                                        Camera preview will appear here
                                    </span>
                                </div>
                            )}

                            {cameraReady && (
                                <span className="absolute left-2 top-2 flex items-center gap-1 rounded bg-black/60 px-1.5 py-1 text-[7px] text-white">
                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                                    LIVE
                                </span>
                            )}

                            {cameraReady && faceDetectionSupported && (
                                <span className="absolute bottom-2 left-2 rounded bg-black/60 px-1.5 py-1 text-[7px] text-white">
                                    {faceStatus === "one"
                                        ? "1 face detected"
                                        : faceStatus === "multiple"
                                            ? "Multiple faces detected"
                                            : faceStatus === "none"
                                                ? "No face detected"
                                                : "Detecting face..."}
                                </span>
                            )}
                        </div>

                        <div className="mt-2 flex items-center justify-between gap-2">
                            <p className="text-[8px] text-slate-500">
                                Face the camera in a well-lit space.
                            </p>
                            {cameraReady && (
                                <button
                                    onClick={stopDevices}
                                    className="shrink-0 text-[8px] text-slate-400 hover:text-white"
                                >
                                    Stop devices
                                </button>
                            )}
                        </div>

                        {cameraError && (
                            <p className="mt-2 text-[8px] leading-relaxed text-red-400">
                                {cameraError}
                            </p>
                        )}

                        {cameraReady && !faceDetectionSupported && (
                            <p className="mt-2 text-[8px] leading-relaxed text-amber-300">
                                Native face detection is unavailable in this
                                browser. Camera access works, but face
                                verification needs the NexHire vision module.
                            </p>
                        )}
                    </section>

                    {/* Microphone and checks */}
                    <div className="flex flex-col gap-3">
                        <section className="rounded-lg border border-white/[0.08] bg-[#0b121b] p-2.5">
                            <div className="mb-3 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <CheckIcon ok={micReady} />
                                    <div>
                                        <h2 className="text-[10px] font-semibold text-white">
                                            Microphone
                                        </h2>
                                        <p className="text-[8px] text-slate-500">
                                            Speak to test your audio
                                        </p>
                                    </div>
                                </div>

                                <span
                                    className={`text-[8px] ${micStatus === "error"
                                        ? "text-red-400"
                                        : micStatus === "ready"
                                            ? "text-emerald-400"
                                            : "text-slate-500"
                                        }`}
                                >
                                    {micStatus === "checking" && micLevel < 3
                                        ? "Speak now"
                                        : statusLabel(micStatus)}
                                </span>
                            </div>

                            <div className="flex h-10 items-center justify-center gap-[3px] rounded-md bg-[#080e16] px-2">
                                {Array.from({ length: 32 }).map((_, index) => {
                                    const threshold = ((index * 17) % 37) + 8;
                                    const active =
                                        micLevel >= threshold &&
                                        micStatus !== "error";

                                    return (
                                        <div
                                            key={index}
                                            className={`w-1 rounded-full transition-[height] duration-100 ${active
                                                ? "bg-[#00c99a]"
                                                : "bg-white/10"
                                                }`}
                                            style={{
                                                height: `${4 + ((index * 7) % 9) + (active ? micLevel * (((index % 4) + 1) / 25) : 0)}px`,
                                            }}
                                        />
                                    );
                                })}
                            </div>

                            <div className="mt-2 flex items-center justify-between">
                                <span className="text-[8px] text-slate-500">
                                    Input level
                                </span>
                                <span className="text-[8px] tabular-nums text-slate-400">
                                    {micLevel}%
                                </span>
                            </div>

                            <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                                <div
                                    className="h-full rounded-full bg-[#00c99a] transition-all duration-100"
                                    style={{ width: `${micLevel}%` }}
                                />
                            </div>

                            <p className="mt-2 text-[8px] leading-relaxed text-slate-500">
                                Say: “Hello, this is my NexHire microphone
                                test.” Speak normally and watch the meter.
                            </p>

                            {micError && (
                                <p className="mt-2 text-[8px] text-red-400">
                                    {micError}
                                </p>
                            )}
                        </section>

                        <section className="rounded-lg border border-white/[0.08] bg-[#0b121b] p-2.5">
                            <h2 className="mb-2 text-[10px] font-semibold text-white">
                                Readiness checklist
                            </h2>

                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <CheckIcon ok={cameraReady} />
                                    <span className="flex-1 text-[9px] text-slate-300">
                                        Camera permission
                                    </span>
                                    <span className="text-[8px] text-slate-500">
                                        {cameraReady ? "Granted" : "Pending"}
                                    </span>
                                </div>

                                <div className="flex items-center gap-2">
                                    <CheckIcon ok={micReady} />
                                    <span className="flex-1 text-[9px] text-slate-300">
                                        Microphone permission
                                    </span>
                                    <span className="text-[8px] text-slate-500">
                                        {micReady ? "Granted" : "Pending"}
                                    </span>
                                </div>

                                <div className="flex items-center gap-2">
                                    <CheckIcon
                                        ok={
                                            faceDetectionSupported &&
                                            faceStatus === "one"
                                        }
                                    />
                                    <span className="flex-1 text-[9px] text-slate-300">
                                        Single face in frame
                                    </span>
                                    <span className="text-[8px] text-slate-500">
                                        {!faceDetectionSupported
                                            ? "Unavailable"
                                            : faceStatus === "one"
                                                ? "Detected"
                                                : faceStatus === "multiple"
                                                    ? "Multiple"
                                                    : "Pending"}
                                    </span>
                                </div>
                            </div>

                            {faceDetectionSupported &&
                                faceStatus === "multiple" && (
                                    <p className="mt-2 text-[8px] text-amber-300">
                                        Ensure only the candidate is visible.
                                    </p>
                                )}
                        </section>
                    </div>
                </div>

                {/* Footer actions */}
                <div className="mt-4 flex flex-col-reverse items-stretch justify-between gap-2 sm:flex-row sm:items-center">
                    <button
                        onClick={() => navigate("/interview/setup")}
                        className="rounded-md border border-white/10 px-3 py-2 text-[9px] text-slate-400 transition hover:bg-white/[0.04] hover:text-white"
                    >
                        ← Back to setup
                    </button>

                    <div className="flex flex-col items-stretch gap-2 sm:flex-row">
                        <button
                            onClick={startChecks}
                            disabled={starting}
                            className="rounded-md border border-white/10 px-3 py-2 text-[9px] font-medium text-slate-200 transition hover:bg-white/[0.05] disabled:opacity-50"
                        >
                            {starting ? "Checking devices..." : "Test devices / Retry"}
                        </button>

                        <button
                            onClick={startInterview}
                            disabled={
                                !allReady ||
                                (faceDetectionSupported && faceStatus !== "one")
                            }
                            className="rounded-md bg-[#00b88a] px-4 py-2 text-[9px] font-semibold text-[#03110d] transition hover:bg-[#00c99a] disabled:cursor-not-allowed disabled:opacity-35"
                        >
                            Start Interview →
                        </button>
                    </div>
                </div>

                <p className="mt-3 text-center text-[8px] leading-relaxed text-slate-600">
                    Your browser will ask for camera and microphone permission.
                    Use localhost or HTTPS to access devices.
                </p>
            </main>
        </div>
    );
}

export default DeviceCheck;
