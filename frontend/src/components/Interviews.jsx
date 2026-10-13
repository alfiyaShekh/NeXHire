import { useEffect, useState } from "react";

/* ------------------------------------------------------------------ */
/* Design tokens                                                       */
/* Add this once in index.html for the intended look (falls back to    */
/* system fonts if you skip it):                                       */
/* <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"> */
/* ------------------------------------------------------------------ */

const SANS =
    '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';
const MONO =
    '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

const mono = { fontFamily: MONO };

/* Compact fluid type scale: grows smoothly with the viewport. */
const type = {
    h2: {
        fontSize: "clamp(1.25rem, 1rem + 1vw, 1.75rem)",
        lineHeight: 1.12,
        letterSpacing: "-0.03em",
    },
    h2Sm: {
        fontSize: "clamp(1.125rem, 0.95rem + 0.75vw, 1.5rem)",
        lineHeight: 1.14,
        letterSpacing: "-0.028em",
    },
    lead: {
        fontSize: "clamp(0.75rem, 0.71rem + 0.14vw, 0.8125rem)",
        lineHeight: 1.65,
    },
    cardTitle: {
        fontSize: "clamp(0.8125rem, 0.78rem + 0.12vw, 0.9375rem)",
        letterSpacing: "-0.01em",
    },
    cardBody: {
        fontSize: "clamp(0.6875rem, 0.66rem + 0.1vw, 0.75rem)",
        lineHeight: 1.6,
    },
    code: {
        fontFamily: MONO,
        fontSize: "clamp(0.5rem, 0.46rem + 0.14vw, 0.59375rem)",
        lineHeight: 1.45,
    },
    small: {
        fontSize: "clamp(0.625rem, 0.6rem + 0.1vw, 0.6875rem)",
    },
};

/* ------------------------------------------------------------------ */
/* Data                                                                */
/* ------------------------------------------------------------------ */

const interviewTypes = [
    {
        id: "coding",
        title: "Coding",
        description:
            "Real editor, syntax highlighting, live execution in Python, Java, C++, JavaScript, C#, Scala and Go. Talk through it while you type.",
        dims: "communication, problem-solving, code quality, language proficiency",
        evaluation: {
            context: "google · reverse string in place",
            verdict: "Hire",
            score: 4.2,
            delta: "+0.6",
            metrics: [
                ["Technical communication", 4.5],
                ["Problem solving", 4.0],
                ["Code quality", 4.0],
                ["Language proficiency", 4.3],
            ],
            feedback:
                "you jumped into code before stating complexity. Say it up front, interviewers score the narration, not just the solution.",
        },
    },
    {
        id: "system",
        title: "System design",
        description:
            'Whiteboard canvas, you sketch, the interviewer challenges your trade-offs out loud. "Why a queue there?"',
        dims: "requirements, architecture, trade-offs, scalability",
        evaluation: {
            context: "meta · design a URL shortener",
            verdict: "Lean hire",
            score: 3.8,
            delta: "+0.4",
            metrics: [
                ["Requirements scoping", 4.0],
                ["Architecture & components", 3.8],
                ["Trade-off reasoning", 3.5],
                ["Scalability & reliability", 3.9],
            ],
            feedback:
                "you added a queue without naming the failure it prevents. State the problem first, then draw the box.",
        },
    },
    {
        id: "behavioral",
        title: "Behavioral",
        description:
            'Structured STAR discussion with follow-ups that dig into the same "tell me more about that decision" you\'ll actually get.',
        dims: "structure, ownership, impact, reflection",
        evaluation: {
            context: "amazon · disagreement with a teammate",
            verdict: "Hire",
            score: 4.0,
            delta: "+0.3",
            metrics: [
                ["STAR structure", 4.3],
                ["Ownership", 4.0],
                ["Impact & metrics", 3.6],
                ["Reflection", 4.0],
            ],
            feedback:
                "your result had no number. Quantify the outcome, then say what you would do differently.",
        },
    },
];

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

/* Reveals `total` steps one by one while `active`; shows all when idle. */
function useStepReveal(total, active, delay = 280) {
    const reduced = useReducedMotion();
    const [count, setCount] = useState(total);

    useEffect(() => {
        if (!active || reduced) {
            setCount(total);
            return;
        }
        setCount(0);
        let i = 0;
        const id = setInterval(() => {
            i += 1;
            setCount(i);
            if (i >= total) clearInterval(id);
        }, delay);
        return () => clearInterval(id);
    }, [active, total, delay, reduced]);

    return count;
}

function useCountUp(target, duration = 800) {
    const reduced = useReducedMotion();
    const [value, setValue] = useState(target);

    useEffect(() => {
        if (reduced) {
            setValue(target);
            return;
        }
        let raf;
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min((now - start) / duration, 1);
            setValue(target * (1 - Math.pow(1 - t, 3)));
            if (t < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [target, duration, reduced]);

    return value;
}

/* ------------------------------------------------------------------ */
/* Card previews                                                       */
/* ------------------------------------------------------------------ */

const fade = (visible) =>
    `transition-opacity duration-300 motion-reduce:transition-none ${visible ? "opacity-100" : "opacity-0"
    }`;

function CodingPreview({ active }) {
    const shown = useStepReveal(6, active);

    return (
        <div style={type.code} className="text-[#9aa7b8]">
            <p className={fade(shown >= 1)}>
                <span className="text-[#00b88a]">def</span>{" "}
                <span className="text-[#e4e9f0]">reverse</span>(s):
            </p>
            <p className={`pl-3 ${fade(shown >= 2)}`}>
                l, r = <span className="text-[#00b88a]">0</span>, len(s) -{" "}
                <span className="text-[#00b88a]">1</span>
            </p>
            <p className={`pl-3 ${fade(shown >= 3)}`}>
                <span className="text-[#00b88a]">while</span> l &lt; r:
            </p>
            <p className={`pl-6 ${fade(shown >= 4)}`}>
                s[l], s[r] = s[r], s[l]
            </p>
            <p className={`pl-6 ${fade(shown >= 5)}`}>
                l, r = l + <span className="text-[#00b88a]">1</span>, r -{" "}
                <span className="text-[#00b88a]">1</span>
            </p>
            <p className={`text-[#00b88a] ${fade(shown >= 6)}`}>
                ✓ 4/4 tests passed · 0.02s
            </p>
        </div>
    );
}

function SystemDesignPreview({ active }) {
    const shown = useStepReveal(5, active, 320);

    const node =
        "absolute rounded border border-[#00b88a]/60 bg-[#0a1a24] px-2 py-0.5 text-[#d9e0e8]";

    return (
        <div className="relative h-full w-full" style={type.code}>
            {/* connectors */}
            <span
                className={`absolute inset-x-[8%] top-[17%] h-px bg-[#2a3a4e] ${fade(
                    shown >= 2
                )}`}
            />
            <span
                className={`absolute left-1/2 top-[34%] h-[34%] w-px bg-[#2a3a4e] ${fade(
                    shown >= 4
                )}`}
            />

            <span className={`left-0 top-0 ${node} ${fade(shown >= 1)}`}>
                Client
            </span>
            <span
                className={`left-1/2 top-0 -translate-x-1/2 ${node} ${fade(
                    shown >= 2
                )}`}
            >
                LB
            </span>
            <span className={`right-0 top-0 ${node} ${fade(shown >= 3)}`}>
                API ×3
            </span>

            <span
                className={`bottom-0 left-[4%] rounded border border-dashed border-[#00b88a]/45 bg-[#0a1a24] px-2 py-0.5 text-[#9aa7b8] absolute ${fade(
                    shown >= 4
                )}`}
            >
                Queue?
            </span>
            <span
                className={`bottom-0 left-1/2 -translate-x-1/2 ${node} ${fade(
                    shown >= 4
                )}`}
            >
                Postgres
            </span>
            <span className={`bottom-0 right-0 ${node} ${fade(shown >= 5)}`}>
                Cache
            </span>
        </div>
    );
}

function BehavioralPreview({ active }) {
    const shown = useStepReveal(4, active, 360);

    const rows = [
        ["S", "Our checkout was timing out on Black Friday..."],
        ["T", "I owned the payment path, 40k rps peak..."],
        ["A", "Profiled it, found the N+1, shipped a fix..."],
        ["R", "p99 dropped 82%. We kept every order."],
    ];

    return (
        <div style={type.code} className="space-y-0.5 text-[#9aa7b8]">
            {rows.map(([letter, text], i) => (
                <p key={letter} className={`flex gap-2 ${fade(shown > i)}`}>
                    <span className="font-semibold text-[#00b88a]">{letter}</span>
                    <span className="truncate">{text}</span>
                </p>
            ))}
        </div>
    );
}

function InterviewVisual({ id, active }) {
    if (id === "coding") return <CodingPreview active={active} />;
    if (id === "system") return <SystemDesignPreview active={active} />;
    return <BehavioralPreview active={active} />;
}

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

function InterviewCard({ item, active, onSelect }) {
    /* cursor-follow glow */
    const onMove = (e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
    };

    return (
        <button
            type="button"
            role="tab"
            aria-selected={active}
            onClick={onSelect}
            onMouseMove={onMove}
            className={`group relative flex h-full flex-col overflow-hidden rounded-xl border text-left transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#00b88a]/60 motion-reduce:transition-none ${active
                ? "border-[#00b88a]/35 bg-[#0d1726] shadow-[0_14px_36px_-16px_rgba(0,184,138,0.25)]"
                : "border-white/[0.07] bg-[#0b1422] hover:-translate-y-0.5 hover:border-white/[0.14]"
                }`}
        >
            {/* cursor glow */}
            <span
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                style={{
                    background:
                        "radial-gradient(200px circle at var(--mx, 50%) var(--my, 50%), rgba(0,184,138,0.09), transparent 70%)",
                }}
            />

            {/* active hairline */}
            <span
                aria-hidden
                className={`absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-[#00b88a] to-transparent transition-opacity duration-300 ${active ? "opacity-100" : "opacity-0"
                    }`}
            />

            {/* preview */}
            <div
                className="relative h-[6.5rem] shrink-0 overflow-hidden border-b border-white/[0.06] bg-[#08101c] p-3 sm:h-[6.25rem] sm:p-2.5 md:h-[6.75rem] md:p-3 lg:h-[7rem]"
                style={{
                    backgroundImage:
                        "radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px)",
                    backgroundSize: "12px 12px",
                }}
            >
                <InterviewVisual id={item.id} active={active} />
            </div>

            {/* text */}
            <div className="relative flex flex-1 flex-col gap-1.5 p-3 lg:p-3.5">
                <div className="flex items-center justify-between gap-2">
                    <h3
                        className="font-medium text-[#f1f4f8]"
                        style={type.cardTitle}
                    >
                        {item.title}
                    </h3>
                    <span
                        aria-hidden
                        className={`h-1 w-1 shrink-0 rounded-full transition-all duration-300 ${active
                            ? "bg-[#00b88a] shadow-[0_0_8px_2px_rgba(0,184,138,0.55)]"
                            : "bg-[#243044]"
                            }`}
                    />
                </div>
                <p className="text-[#7f8b9c]" style={type.cardBody}>
                    {item.description}
                </p>
            </div>
        </button>
    );
}

/* ------------------------------------------------------------------ */
/* Evaluation panel                                                    */
/* ------------------------------------------------------------------ */

function EvaluationMetric({ label, value, index }) {
    const [width, setWidth] = useState(0);

    useEffect(() => {
        setWidth(0);
        const t = setTimeout(() => setWidth((value / 5) * 100), 60 + index * 90);
        return () => clearTimeout(t);
    }, [value, index]);

    return (
        <div>
            <div
                className="mb-1 flex items-center justify-between gap-2"
                style={type.small}
            >
                <span className="truncate font-medium text-[#e4e9f0]">{label}</span>
                <span className="shrink-0 tabular-nums text-[#8d98a8]" style={mono}>
                    {value.toFixed(1)}
                </span>
            </div>
            <div className="h-[3px] overflow-hidden rounded-full bg-[#18263a]">
                <div
                    className="h-full rounded-full bg-gradient-to-r from-[#00a07a] to-[#00d6a1] transition-[width] duration-700 ease-out motion-reduce:transition-none"
                    style={{ width: `${width}%` }}
                />
            </div>
        </div>
    );
}

function EvaluationPanel({ item }) {
    const { evaluation: ev, title } = item;
    const score = useCountUp(ev.score);
    const isHire = ev.verdict === "Hire";

    return (
        <div
            role="region"
            aria-live="polite"
            aria-label={`${title} evaluation preview`}
            className="w-full overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b1422] shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]"
        >
            <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-3 py-2 sm:px-3.5">
                <span
                    className="truncate text-[#667386]"
                    style={{ ...mono, ...type.small }}
                >
                    evaluation · {ev.context}
                </span>
                <span
                    className={`shrink-0 rounded-full border px-2 py-px text-[0.5625rem] font-semibold uppercase tracking-wider ${isHire
                        ? "border-[#00b88a]/30 bg-[#00b88a]/10 text-[#00d6a1]"
                        : "border-[#d4a24c]/30 bg-[#d4a24c]/10 text-[#e0b363]"
                        }`}
                    style={mono}
                >
                    {ev.verdict}
                </span>
            </div>

            <div className="p-3 sm:p-3.5">
                <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
                    <div className="flex items-baseline gap-1.5">
                        <span
                            className="font-semibold tabular-nums text-white"
                            style={{
                                ...mono,
                                fontSize: "clamp(1.25rem, 1rem + 0.8vw, 1.75rem)",
                                lineHeight: 1,
                                letterSpacing: "-0.02em",
                            }}
                        >
                            {score.toFixed(1)}
                        </span>
                        <span className="text-[#596577]" style={type.small}>
                            / 5 overall
                        </span>
                    </div>
                    <span className="text-[#00d6a1]" style={{ ...mono, ...type.small }}>
                        ▲ {ev.delta} vs your last session
                    </span>
                </div>

                <div className="mt-3.5 space-y-2.5">
                    {ev.metrics.map(([label, value], i) => (
                        <EvaluationMetric
                            key={`${item.id}-${label}`}
                            label={label}
                            value={value}
                            index={i}
                        />
                    ))}
                </div>

                <div className="mt-3.5 rounded-md border-l-2 border-[#00b88a] bg-[#00b88a]/[0.07] px-2.5 py-2">
                    <p className="text-[#aab4c2]" style={{ ...type.small, lineHeight: 1.6 }}>
                        <span className="font-semibold text-white">Work on:</span>{" "}
                        {ev.feedback}
                    </p>
                </div>
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Section                                                             */
/* ------------------------------------------------------------------ */

function Interviews() {
    const [activeId, setActiveId] = useState(interviewTypes[0].id);
    const activeItem = interviewTypes.find((t) => t.id === activeId);

    return (
        <section
            id="interviews"
            className="relative w-full overflow-hidden bg-[#020812] px-4 py-10 sm:px-5 sm:py-14 lg:px-6 lg:py-16"
            style={{ fontFamily: SANS }}
        >
            {/* ambient light */}
            <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 top-0 h-[24rem] bg-[radial-gradient(55%_60%_at_50%_0%,rgba(0,184,138,0.07),transparent)]"
            />

            <div className="relative mx-auto w-full max-w-[56rem]">
                {/* Intro */}
                <div className="max-w-lg">
                    <h2 className="font-normal text-[#f5f7fa]" style={type.h2}>
                        Pick your interview type.
                    </h2>
                    <p className="mt-2.5 text-[#8795a8]" style={type.lead}>
                        Not a chat window with a prompt. Each format gets the actual
                        environment you'll face, with the interviewer talking to you
                        the whole way through.
                    </p>
                </div>

                {/* Cards */}
                <div
                    role="tablist"
                    aria-label="Interview type"
                    className="mt-7 grid grid-cols-1 items-stretch gap-3 sm:mt-8 sm:grid-cols-3 lg:gap-3.5"
                >
                    {interviewTypes.map((item) => (
                        <InterviewCard
                            key={item.id}
                            item={item}
                            active={item.id === activeId}
                            onSelect={() => setActiveId(item.id)}
                        />
                    ))}
                </div>

                {/* Evaluation */}
                <div className="mt-12 grid items-center gap-7 sm:mt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,21rem)] lg:gap-10">
                    <div className="max-w-[26rem]">
                        <h2 className="font-normal text-[#f5f7fa]" style={type.h2Sm}>
                            Then it tells you the truth.
                        </h2>

                        <p className="mt-2.5 text-[#8795a8]" style={type.lead}>
                            Every session ends with a scored evaluation:{" "}
                            <strong className="font-semibold text-[#e4e9f0]">
                                {activeItem.dims}
                            </strong>
                            , a verdict, and the specific thing to fix before the next
                            one.
                        </p>

                        <p className="mt-2 text-[#667386]" style={type.cardBody}>
                            Compared against your last session, so you can watch
                            yourself get better. Scoring dimensions match the
                            interview type.
                        </p>

                        {/* quick switch, right next to the report */}
                        <div
                            role="tablist"
                            aria-label="Preview report for"
                            className="mt-4 inline-flex max-w-full overflow-x-auto rounded-full border border-white/[0.08] bg-[#0b1422] p-0.5"
                        >
                            {interviewTypes.map((item) => {
                                const active = item.id === activeId;
                                return (
                                    <button
                                        key={item.id}
                                        type="button"
                                        role="tab"
                                        aria-selected={active}
                                        onClick={() => setActiveId(item.id)}
                                        style={type.small}
                                        className={`whitespace-nowrap rounded-full px-2.5 py-1 font-medium transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#00b88a]/60 motion-reduce:transition-none ${active
                                            ? "bg-[#00b88a]/15 text-[#00d6a1]"
                                            : "text-[#7f8b9c] hover:text-[#d9e0e8]"
                                            }`}
                                    >
                                        {item.title}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="w-full lg:justify-self-end">
                        <EvaluationPanel item={activeItem} />
                    </div>
                </div>
            </div>
        </section>
    );
}

export default Interviews;