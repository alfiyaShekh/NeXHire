import { useEffect, useState } from "react";

/* ------------------------------------------------------------------ */
/* SETUP                                                               */
/* 1. Put face-scan.png in your project's /public folder              */
/*    (so it is served at /face-scan.png).                             */
/* 2. Optional fonts, add once in index.html:                          */
/* <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"> */
/* ------------------------------------------------------------------ */

const FACE_IMG = "/face-scan.png";

const SANS =
    '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';
const MONO =
    '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

const mono = { fontFamily: MONO };

/* Compact fluid type scale: grows smoothly with the viewport. */
const type = {
    h2: {
        fontSize: "clamp(1.125rem, 0.95rem + 0.8vw, 1.5rem)",
        lineHeight: 1.12,
        letterSpacing: "-0.03em",
    },
    h2Sm: {
        fontSize: "clamp(1rem, 0.88rem + 0.6vw, 1.25rem)",
        lineHeight: 1.14,
        letterSpacing: "-0.028em",
    },
    lead: {
        fontSize: "clamp(0.6875rem, 0.66rem + 0.12vw, 0.75rem)",
        lineHeight: 1.65,
    },
    cardTitle: {
        fontSize: "clamp(0.75rem, 0.72rem + 0.1vw, 0.8125rem)",
        letterSpacing: "-0.01em",
    },
    cardBody: {
        fontSize: "clamp(0.625rem, 0.6rem + 0.08vw, 0.6875rem)",
        lineHeight: 1.6,
    },
    small: {
        fontSize: "clamp(0.5625rem, 0.55rem + 0.08vw, 0.625rem)",
    },
    tiny: {
        fontSize: "clamp(0.5rem, 0.49rem + 0.06vw, 0.5625rem)",
    },
};

const dotGrid = {
    backgroundImage:
        "radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px)",
    backgroundSize: "12px 12px",
};

/* ------------------------------------------------------------------ */
/* Keyframes (scoped with the nx- prefix, reduced-motion safe)         */
/* ------------------------------------------------------------------ */

const css = `
@keyframes nx-wave { 0%,100% { transform: scaleY(.3); } 50% { transform: scaleY(1); } }
@keyframes nx-grow { 0%,100% { transform: scaleY(.65); } 50% { transform: scaleY(1); } }
@keyframes nx-fill { 0% { transform: scaleX(0); } 55%,100% { transform: scaleX(1); } }
@keyframes nx-scan { 0% { top: 0%; opacity: 0; } 15% { opacity: 1; } 85% { opacity: 1; } 100% { top: 100%; opacity: 0; } }
@keyframes nx-pupil { 0%,100% { transform: translate(0,0); } 25% { transform: translate(4px,-1px); } 50% { transform: translate(-3px,1px); } 75% { transform: translate(2px,2px); } }
@keyframes nx-sweep { 0% { top: -20%; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { top: 105%; opacity: 0; } }
@keyframes nx-breathe { 0%,100% { transform: scale(1); } 50% { transform: scale(1.025); } }
@media (prefers-reduced-motion: reduce) {
  .nx-anim { animation: none !important; }
}
`;

/* ------------------------------------------------------------------ */
/* Hooks                                                               */
/* ------------------------------------------------------------------ */

function useReducedMotion() {
    const [reduced, setReduced] = useState(false);

    useEffect(() => {
        const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
        setReduced(mq.matches);
        const onChange = (e) => setReduced(e.matches);
        mq.addEventListener("change", onChange);
        return () => mq.removeEventListener("change", onChange);
    }, []);

    return reduced;
}

/* ------------------------------------------------------------------ */
/* Feature data                                                        */
/* ------------------------------------------------------------------ */

const features = [
    {
        title: "Eye Contact",
        description:
            "Measures visual engagement throughout the interview and highlights moments where your attention drops.",
        type: "eye",
    },
    {
        title: "Voice Analysis",
        description:
            "Analyzes speaking pace, delivery and vocal consistency to help you sound clearer and more confident.",
        type: "voice",
    },
    {
        title: "Answer Intelligence",
        description:
            "Evaluates whether your answers are relevant, structured and strong enough for the question being asked.",
        type: "answer",
    },
    {
        title: "Behavior Analysis",
        description:
            "Observes interview behavior and confidence signals while you communicate with the AI interviewer.",
        type: "behavior",
    },
    {
        title: "Resume Analysis",
        description:
            "Uses your resume to make interview questions more relevant to your skills, projects and experience.",
        type: "resume",
    },
];

/* 3 cards on the first row, 2 wider cards on the second: no empty cell. */
const spanClass = (i) =>
    i < 3
        ? "lg:col-span-2"
        : i === 3
            ? "lg:col-span-3"
            : "sm:col-span-2 lg:col-span-3";

/* ------------------------------------------------------------------ */
/* Feature icon                                                        */
/* ------------------------------------------------------------------ */

function FeatureIcon({ type: t }) {
    const common = {
        viewBox: "0 0 24 24",
        fill: "none",
        className: "h-3 w-3 text-[#00b88a]",
        "aria-hidden": true,
    };

    if (t === "eye") {
        return (
            <svg {...common}>
                <path
                    d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                />
                <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5" />
            </svg>
        );
    }

    if (t === "voice") {
        return (
            <svg {...common}>
                <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.5" />
                <path
                    d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                />
            </svg>
        );
    }

    if (t === "answer") {
        return (
            <svg {...common}>
                <path
                    d="M5 4.5h14A1.5 1.5 0 0 1 20.5 6v9A1.5 1.5 0 0 1 19 16.5H11l-4.5 3v-3H5A1.5 1.5 0 0 1 3.5 15V6A1.5 1.5 0 0 1 5 4.5Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                />
                <path d="M7.5 9h9M7.5 12h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
        );
    }

    if (t === "behavior") {
        return (
            <svg {...common}>
                <circle cx="12" cy="8" r="3" stroke="currentColor" strokeWidth="1.5" />
                <path
                    d="M5.5 20c.8-3.4 3-5 6.5-5s5.7 1.6 6.5 5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                />
                <path
                    d="m17.5 5.5 1 1 2-2"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />
            </svg>
        );
    }

    return (
        <svg {...common}>
            <path
                d="M6 3.5h8l4 4V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"
                stroke="currentColor"
                strokeWidth="1.5"
            />
            <path d="M14 3.5V8h4M8 12h8M8 15h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
    );
}

/* ------------------------------------------------------------------ */
/* Mini feature visuals (all gently animated)                          */
/* ------------------------------------------------------------------ */

function EyeVisual() {
    return (
        <div className="relative flex h-full items-center justify-center">
            <div className="absolute h-8 w-14 rounded-[50%] border border-[#00b88a]/30" />
            <div className="absolute h-5 w-5 rounded-full border border-[#00b88a]/40" />
            <span
                className="nx-anim absolute h-1 w-1 rounded-full bg-[#00b88a]"
                style={{ animation: "nx-pupil 5s ease-in-out infinite" }}
            />
            <span
                className="absolute bottom-0 right-0 text-[#00b88a]"
                style={{ ...mono, ...type.tiny }}
            >
                96%
            </span>
        </div>
    );
}

function VoiceVisual() {
    return (
        <div className="flex h-full items-center justify-center gap-[3px]">
            {[8, 14, 20, 11, 26, 16, 9, 22, 14, 19, 10, 24].map((height, index) => (
                <span
                    key={index}
                    className="nx-anim w-[2px] rounded-full bg-[#00b88a]/60"
                    style={{
                        height: `${height}px`,
                        animation: "nx-wave 1.2s ease-in-out infinite",
                        animationDelay: `${index * 70}ms`,
                    }}
                />
            ))}
        </div>
    );
}

function AnswerVisual() {
    const lines = [
        ["88%", "bg-white/[0.08]"],
        ["72%", "bg-white/[0.08]"],
        ["94%", "bg-[#00b88a]/35"],
        ["58%", "bg-white/[0.08]"],
    ];

    return (
        <div className="flex h-full flex-col justify-center">
            <div className="space-y-[3px]">
                {lines.map(([w, color], i) => (
                    <div key={i} className="h-[3px] rounded-full" style={{ width: w }}>
                        <div
                            className={`nx-anim h-full origin-left rounded-full ${color}`}
                            style={{
                                animation: "nx-fill 3.2s ease-out infinite",
                                animationDelay: `${i * 220}ms`,
                            }}
                        />
                    </div>
                ))}
            </div>

            <div className="mt-1.5 flex items-center gap-1">
                <span className="relative flex h-1.5 w-1.5">
                    <span className="nx-anim absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00b88a] opacity-50" />
                    <span className="relative h-full w-full rounded-full bg-[#00b88a]" />
                </span>
                <span className="text-[#00b88a]" style={type.tiny}>
                    Relevant response
                </span>
            </div>
        </div>
    );
}

function BehaviorVisual() {
    const bars = [
        [42, 0.25],
        [66, 0.4],
        [86, 0.7],
        [57, 0.4],
        [72, 0.5],
    ];

    return (
        <div className="flex h-full items-end justify-center gap-1.5">
            {bars.map(([h, o], i) => (
                <div
                    key={i}
                    className="nx-anim w-2 rounded-t bg-[#00b88a]"
                    style={{
                        height: `${h}%`,
                        opacity: o + 0.15,
                        transformOrigin: "bottom",
                        animation: "nx-grow 2.4s ease-in-out infinite",
                        animationDelay: `${i * 180}ms`,
                    }}
                />
            ))}
        </div>
    );
}

function ResumeVisual() {
    return (
        <div className="relative mx-auto h-full w-9 overflow-hidden rounded border border-white/[0.08] bg-[#0b1422] p-1">
            <div className="mb-1 h-[3px] w-3 rounded-full bg-[#00b88a]/60" />
            <div className="space-y-[3px]">
                <div className="h-[3px] w-full rounded bg-white/[0.08]" />
                <div className="h-[3px] w-[80%] rounded bg-white/[0.08]" />
                <div className="h-[3px] w-[92%] rounded bg-white/[0.08]" />
                <div className="h-[3px] w-[65%] rounded bg-white/[0.08]" />
            </div>

            {/* scan line */}
            <span
                className="nx-anim absolute inset-x-0 h-px bg-[#00d6a1] shadow-[0_0_6px_1px_rgba(0,214,161,0.6)]"
                style={{ animation: "nx-scan 2.6s ease-in-out infinite" }}
            />
        </div>
    );
}

function FeatureVisual({ type: t }) {
    if (t === "eye") return <EyeVisual />;
    if (t === "voice") return <VoiceVisual />;
    if (t === "answer") return <AnswerVisual />;
    if (t === "behavior") return <BehaviorVisual />;
    return <ResumeVisual />;
}

/* ------------------------------------------------------------------ */
/* Feature card                                                        */
/* ------------------------------------------------------------------ */

function FeatureCard({ feature, className = "" }) {
    /* cursor-follow glow */
    const onMove = (e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
    };

    return (
        <div
            onMouseMove={onMove}
            className={`group relative flex h-full flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-[#0b1422] p-2.5 transition-all duration-300 hover:-translate-y-0.5 hover:border-white/[0.14] hover:bg-[#0d1726] motion-reduce:transition-none lg:p-3 ${className}`}
        >
            <span
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                style={{
                    background:
                        "radial-gradient(200px circle at var(--mx, 50%) var(--my, 50%), rgba(0,184,138,0.09), transparent 70%)",
                }}
            />

            <div className="relative flex flex-1 flex-col">
                <div className="flex h-5 w-5 items-center justify-center rounded-md border border-[#00b88a]/15 bg-[#00b88a]/[0.06]">
                    <FeatureIcon type={feature.type} />
                </div>

                <h3 className="mt-2 font-medium text-[#f1f4f8]" style={type.cardTitle}>
                    {feature.title}
                </h3>

                <p className="mt-1 flex-1 text-[#7f8b9c]" style={type.cardBody}>
                    {feature.description}
                </p>

                <div
                    className="mt-2.5 h-[3.5rem] overflow-hidden rounded-lg border border-white/[0.05] bg-[#07101d] p-2"
                    style={dotGrid}
                >
                    <FeatureVisual type={feature.type} />
                </div>
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Live analysis panel                                                 */
/* ------------------------------------------------------------------ */

/* Only drives the "Candidate locked / Gaze drifted" status and the    */
/* eye-contact value. The face itself is a static image.               */
const GAZES = [true, true, true, false, true, true];

const BASE = [92, 89, 94];

const METRICS = [
    { label: "Eye Contact", icon: "eye" },
    { label: "Head Pose", icon: "head" },
    { label: "Voice Analysis", icon: "voice" },
];

/* Symmetric waveform: tall in the middle, short at the edges. */
const WAVEFORM = Array.from({ length: 41 }, (_, i) => {
    const c = 1 - Math.abs(i - 20) / 20;
    const noise = ((i * 37) % 11) / 11;
    return { h: Math.round(16 + c * 50 + noise * 34), o: 0.3 + c * 0.7 };
});

const ICON = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
};

function MetricIcon({ name }) {
    const cls = "h-3.5 w-3.5 shrink-0 text-[#00d6a1]";

    if (name === "eye") {
        return (
            <svg {...ICON} className={cls}>
                <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
                <circle cx="12" cy="12" r="2.5" />
            </svg>
        );
    }

    if (name === "head") {
        return (
            <svg {...ICON} className={cls}>
                <circle cx="12" cy="8" r="3.5" />
                <path d="M5 20c.8-3.6 3.3-5.5 7-5.5s6.2 1.9 7 5.5" />
            </svg>
        );
    }

    return (
        <svg {...ICON} className={cls}>
            <path d="M3 10v4M7.5 6.5v11M12 3.5v17M16.5 7.5v9M21 10.5v3" />
        </svg>
    );
}

function MicIcon() {
    return (
        <svg {...ICON} className="h-3 w-3 shrink-0 text-[#00d6a1]">
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" />
        </svg>
    );
}

function WifiIcon() {
    return (
        <svg {...ICON} className="h-3 w-3 shrink-0">
            <path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0" />
            <circle cx="12" cy="19" r="1" fill="currentColor" />
        </svg>
    );
}

function MonitorIcon() {
    return (
        <svg {...ICON} className="h-3 w-3 shrink-0">
            <rect x="3" y="4" width="18" height="12" rx="1.5" />
            <path d="M8 20h8M12 16v4" />
        </svg>
    );
}

/* Bright corner brackets that frame the camera view. */
function Corners() {
    const base = "pointer-events-none absolute h-3 w-3 border-[#00d6a1]";
    return (
        <>
            <span aria-hidden className={`${base} left-1.5 top-1.5 rounded-tl-sm border-l-2 border-t-2`} />
            <span aria-hidden className={`${base} right-1.5 top-1.5 rounded-tr-sm border-r-2 border-t-2`} />
            <span aria-hidden className={`${base} bottom-1.5 left-1.5 rounded-bl-sm border-b-2 border-l-2`} />
            <span aria-hidden className={`${base} bottom-1.5 right-1.5 rounded-br-sm border-b-2 border-r-2`} />
        </>
    );
}

/* Dimmer inner brackets, like the inspo. */
function InnerBrackets() {
    const base = "pointer-events-none absolute h-5 w-5 border-[#3f7ea8]/70";
    return (
        <>
            <span aria-hidden className={`${base} left-[12%] top-[18%] border-l-2 border-t-2`} />
            <span aria-hidden className={`${base} right-[12%] top-[18%] border-r-2 border-t-2`} />
            <span aria-hidden className={`${base} bottom-[16%] left-[12%] border-b-2 border-l-2`} />
            <span aria-hidden className={`${base} bottom-[16%] right-[12%] border-b-2 border-r-2`} />
        </>
    );
}

function MetricCard({ label, icon, value, active }) {
    return (
        <div
            className={`rounded-lg border bg-[#07111d] px-2.5 py-1.5 transition-colors duration-300 motion-reduce:transition-none ${active ? "border-[#00d6a1]/35" : "border-[#00d6a1]/[0.14]"
                }`}
        >
            <div className="flex items-center gap-2">
                <MetricIcon name={icon} />
                <span className="flex-1 truncate text-[#e4e9f0]" style={type.cardBody}>
                    {label}
                </span>
                <span
                    className="shrink-0 font-medium tabular-nums text-[#00e8b5]"
                    style={{ ...mono, ...type.cardBody }}
                >
                    {value}%
                </span>
            </div>

            <div className="mt-1.5 h-1 rounded-full bg-white/[0.07]">
                <div
                    className="h-full rounded-full bg-gradient-to-r from-[#00b88a] to-[#00f0bb] shadow-[0_0_8px_rgba(0,240,187,0.5)] transition-[width] duration-700 ease-out motion-reduce:transition-none"
                    style={{ width: `${value}%` }}
                />
            </div>
        </div>
    );
}

function LiveAnalysisPanel() {
    const reduced = useReducedMotion();
    const [tick, setTick] = useState(0);

    /* one clock drives status, active metric, values and timer */
    useEffect(() => {
        if (reduced) return;
        const id = setInterval(() => setTick((t) => t + 1), 1000);
        return () => clearInterval(id);
    }, [reduced]);

    const step = Math.floor(tick / 2);
    const active = step % 3;
    const gazeOn = GAZES[step % GAZES.length];

    const values = BASE.map((base, i) => {
        const wobble = ((step * 5 + i * 3) % 5) - 2;
        const penalty = i === 0 && !gazeOn ? 7 : 0;
        return Math.max(0, Math.min(99, base + wobble - penalty));
    });

    const elapsed = 268 + tick;
    const pad = (n) => String(n).padStart(2, "0");
    const timer = `${pad(Math.floor(elapsed / 3600))}:${pad(Math.floor((elapsed % 3600) / 60))}:${pad(
        elapsed % 60
    )}`;

    return (
        <div className="relative overflow-hidden rounded-xl border border-[#00d6a1]/20 bg-[#050d18] shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]">
            {/* top glow line */}
            <span
                aria-hidden
                className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-[#00d6a1]/70 to-transparent"
            />

            {/* Header */}
            <div className="flex items-center justify-between gap-2 border-b border-[#00d6a1]/10 px-2.5 py-[3px] sm:px-3">
                <div className="flex min-w-0 items-center gap-2">
                    <span
                        className="flex h-5 w-6 shrink-0 items-center justify-center rounded-md border border-[#00d6a1]/60 bg-[#00d6a1]/[0.08] text-[#00e8b5] shadow-[0_0_8px_rgba(0,214,161,0.3)]"
                        style={{ ...mono, fontSize: "0.5rem", fontWeight: 600 }}
                    >
                        &lt;NH&gt;
                    </span>
                    <div className="min-w-0 leading-[1.1]">
                        <p className="truncate font-medium text-[#f1f4f8]" style={type.small}>
                            NexHire
                        </p>
                        <p className="truncate text-[#6b7a8d]" style={type.tiny}>
                            AI Interview Session
                        </p>
                    </div>
                </div>

                <div className="flex shrink-0 items-center overflow-hidden rounded-md border border-[#00d6a1]/20 bg-[#07111d]">
                    <span
                        className="flex items-center gap-1.5 px-2 py-0.5 font-semibold text-[#00e8b5]"
                        style={type.tiny}
                    >
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00e8b5] opacity-60 motion-reduce:animate-none" />
                            <span className="relative h-full w-full rounded-full bg-[#00e8b5]" />
                        </span>
                        LIVE
                    </span>
                    <span className="h-3 w-px bg-white/10" />
                    <span className="px-2 py-0.5 text-[#aab4c2]" style={{ ...mono, ...type.tiny }}>
                        {timer}
                    </span>
                </div>
            </div>

            <div className="grid gap-2.5 p-2.5 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] sm:gap-3 sm:p-3">
                {/* Camera view */}
                <div className="flex flex-col overflow-hidden rounded-lg border border-[#00d6a1]/20 bg-[#050d18]">
                    <div
                        className="relative h-[13rem] flex-1 overflow-hidden sm:h-auto sm:min-h-[13.5rem]"
                        style={{
                            background:
                                "radial-gradient(75% 65% at 50% 40%, rgba(30,144,255,0.16), transparent 70%), #04101c",
                        }}
                    >
                        {/* face image, edges faded into the panel */}
                        <div className="absolute inset-0 flex items-center justify-center">
                            <img
                                src={FACE_IMG}
                                alt="Face tracking preview with landmark points"
                                draggable={false}
                                className="nx-anim h-full w-auto max-w-none select-none object-contain"
                                style={{
                                    animation: "nx-breathe 6s ease-in-out infinite",
                                    WebkitMaskImage:
                                        "radial-gradient(ellipse 60% 66% at 50% 46%, #000 58%, transparent 100%)",
                                    maskImage:
                                        "radial-gradient(ellipse 60% 66% at 50% 46%, #000 58%, transparent 100%)",
                                }}
                            />
                        </div>

                        {/* scan sweep */}
                        <span
                            aria-hidden
                            className="nx-anim pointer-events-none absolute inset-x-0 h-6 border-b border-[#5ad7ff]/70"
                            style={{
                                background:
                                    "linear-gradient(to bottom, transparent, rgba(80,200,255,0.14))",
                                animation: "nx-sweep 3.8s ease-in-out infinite",
                            }}
                        />

                        <InnerBrackets />
                        <Corners />

                        <span
                            className="absolute left-5 top-3 rounded border border-white/10 bg-[#07111d]/80 px-1.5 py-0.5 text-[#c9d3df]"
                            style={{ ...mono, ...type.tiny }}
                        >
                            FACE · 0.99
                        </span>
                        <span
                            className="absolute right-5 top-3 rounded border border-white/10 bg-[#07111d]/80 px-1.5 py-0.5 text-[#c9d3df]"
                            style={{ ...mono, ...type.tiny }}
                        >
                            30 FPS
                        </span>
                    </div>

                    {/* status bar */}
                    <div className="flex items-center justify-between gap-2 border-t border-[#00d6a1]/10 px-2.5 py-1.5">
                        <span
                            className={`flex min-w-0 items-center gap-1.5 transition-colors duration-300 ${gazeOn ? "text-[#00e8b5]" : "text-[#e0b363]"
                                }`}
                            style={type.tiny}
                        >
                            <span className="relative flex h-1.5 w-1.5 shrink-0">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60 motion-reduce:animate-none" />
                                <span className="relative h-full w-full rounded-full bg-current" />
                            </span>
                            <span className="truncate">{gazeOn ? "Candidate locked" : "Gaze drifted"}</span>
                        </span>

                        <span className="flex shrink-0 items-center gap-2 text-[#8d98a8]" style={type.tiny}>
                            <span className="flex items-center gap-1">
                                <WifiIcon />
                                30 FPS
                            </span>
                            <span className="h-3 w-px bg-white/10" />
                            <span className="flex items-center gap-1">
                                <MonitorIcon />
                                1080p
                            </span>
                        </span>
                    </div>
                </div>

                {/* Metrics + listening (min-h keeps the card at its original height) */}
                <div className="flex min-h-[17rem] flex-col gap-1.5">
                    {METRICS.map((m, i) => (
                        <MetricCard
                            key={m.label}
                            label={m.label}
                            icon={m.icon}
                            value={values[i]}
                            active={active === i}
                        />
                    ))}

                    <div className="relative flex min-h-0 flex-1 flex-col rounded-lg border border-[#00d6a1]/[0.14] bg-[#07111d] px-2.5 py-2">
                        <div className="flex items-center gap-2">
                            <MicIcon />
                            <span className="flex-1 text-[#aab4c2]" style={type.small}>
                                Listening...
                            </span>
                            <span className="h-3 w-px bg-white/10" />
                            <span className="text-[#8d98a8]" style={{ ...mono, ...type.tiny }}>
                                30 FPS
                            </span>
                        </div>

                        <div className="mt-2 flex flex-1 items-center justify-center gap-[2px] pb-2">
                            {WAVEFORM.map(({ h, o }, i) => (
                                <span
                                    key={i}
                                    className="nx-anim w-[2px] rounded-full"
                                    style={{
                                        height: `${h}%`,
                                        backgroundColor: `rgba(0,214,161,${o.toFixed(2)})`,
                                        animation: "nx-wave 1.3s ease-in-out infinite",
                                        animationDelay: `${i * 45}ms`,
                                    }}
                                />
                            ))}
                        </div>

                        <span
                            aria-hidden
                            className="absolute bottom-2 right-2 h-1.5 w-1.5 rounded-full bg-[#00d6a1] shadow-[0_0_8px_#00d6a1]"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Section                                                             */
/* ------------------------------------------------------------------ */

function Features() {
    return (
        <section
            id="features"
            className="relative w-full overflow-hidden bg-[#020812] px-4 py-8 sm:px-5 sm:py-12 lg:px-6 lg:py-14"
            style={{ fontFamily: SANS }}
        >
            <style>{css}</style>

            {/* ambient light */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 top-0 h-[24rem] bg-[radial-gradient(55%_60%_at_50%_0%,rgba(0,184,138,0.07),transparent)]"
            />

            <div className="relative mx-auto w-full max-w-[52rem]">
                {/* Intro */}
                <div className="max-w-lg">
                    <h2 className="font-normal text-[#f5f7fa]" style={type.h2}>
                        More than just answers.
                    </h2>
                    <p className="mt-2.5 text-[#8795a8]" style={type.lead}>
                        NexHire looks at how you communicate, think and perform, not
                        just what you say.
                    </p>
                </div>

                {/* Feature cards */}
                <div className="mt-6 grid grid-cols-1 items-stretch gap-2.5 sm:mt-7 sm:grid-cols-2 lg:grid-cols-6 lg:gap-3">
                    {features.map((feature, i) => (
                        <FeatureCard
                            key={feature.title}
                            feature={feature}
                            className={spanClass(i)}
                        />
                    ))}
                </div>

                {/* Live analysis */}
                <div className="mt-10 grid items-center gap-5 sm:mt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)] lg:gap-10">
                    <div className="max-w-md">
                        <h3 className="font-normal text-[#f5f7fa]" style={type.h2Sm}>
                            Every signal matters.
                        </h3>
                        <p className="mt-2.5 text-[#8795a8]" style={type.lead}>
                            While you focus on answering, NexHire continuously
                            evaluates the signals that are easy to miss.
                        </p>
                    </div>

                    <div className="w-full max-w-[32rem] lg:max-w-none">
                        <LiveAnalysisPanel />
                    </div>
                </div>
            </div>
        </section>
    );
}

export default Features;