import { useEffect, useState } from "react";

const interviews = [
    {
        question: "Tell me about yourself.",
        answer:
            "I'm a Computer Science student passionate about building practical software and AI-powered applications.",
        followUp: "What kind of problems do you enjoy solving?",
    },
    {
        question: "Tell me about one of your projects.",
        answer:
            "I recently worked on an AI-based system that combines computer vision, speech processing and intelligent evaluation.",
        followUp: "What was the most challenging part?",
    },
    {
        question: "How do you handle a difficult technical problem?",
        answer:
            "I first break the problem into smaller parts, understand the constraints and then test possible solutions systematically.",
        followUp: "How do you decide between different approaches?",
    },
];

/* Shared text styles (also used by the invisible "height reservers") */
const questionText = "text-[12px] font-medium leading-snug text-[#edf1f5]";
const answerText = "text-[11px] leading-[1.55] text-[#9ba6b5]";
const followUpText = "text-[11px] leading-snug text-[#9ba6b5]";

function InterviewPreview() {
    const [current, setCurrent] = useState(0);
    const [showAnswer, setShowAnswer] = useState(false);
    const [showFollowUp, setShowFollowUp] = useState(false);
    const [typedAnswer, setTypedAnswer] = useState("");

    const interview = interviews[current];

    useEffect(() => {
        setShowAnswer(false);
        setShowFollowUp(false);
        setTypedAnswer("");

        const answerTimer = setTimeout(() => setShowAnswer(true), 1100);
        const followTimer = setTimeout(() => setShowFollowUp(true), 3600);
        const nextTimer = setTimeout(
            () => setCurrent((prev) => (prev + 1) % interviews.length),
            7000
        );

        return () => {
            clearTimeout(answerTimer);
            clearTimeout(followTimer);
            clearTimeout(nextTimer);
        };
    }, [current]);

    useEffect(() => {
        if (!showAnswer) return;

        let index = 0;

        const interval = setInterval(() => {
            setTypedAnswer(interview.answer.slice(0, index));
            index++;

            if (index > interview.answer.length) {
                clearInterval(interval);
            }
        }, 22);

        return () => clearInterval(interval);
    }, [showAnswer, interview.answer]);

    const metrics = [
        {
            label: "Eye Contact",
            value: current === 1 ? "94%" : current === 2 ? "91%" : "96%",
            width: current === 1 ? "94%" : current === 2 ? "91%" : "96%",
        },
        {
            label: "Head Pose",
            value: current === 2 ? "88%" : "92%",
            width: current === 2 ? "88%" : "92%",
        },
        {
            label: "Voice Analysis",
            value: current === 1 ? "89%" : "93%",
            width: current === 1 ? "89%" : "93%",
        },
    ];

    return (
        <div className="relative mx-auto w-full max-w-[380px] lg:max-w-[350px]">
            {/* GLOW */}
            <div className="pointer-events-none absolute -inset-3 rounded-[2rem] bg-[#00b88a]/[0.035] blur-3xl" />

            {/* MAIN CARD */}
            <div className="relative w-full overflow-hidden rounded-xl border border-white/[0.1] bg-[#07101d] shadow-2xl shadow-black/40">
                {/* TOP SHINE */}
                <div className="pointer-events-none absolute left-0 top-0 h-px w-full overflow-hidden">
                    <div className="preview-shine h-full w-[20%] bg-gradient-to-r from-transparent via-[#00b88a]/60 to-transparent" />
                </div>

                {/* HEADER */}
                <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-3.5 py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[#00b88a]/20 bg-[#00b88a]/[0.07]">
                            <span className="text-[8px] font-bold text-[#00b88a]">
                                &lt;NH&gt;
                            </span>
                        </div>

                        <div className="min-w-0 leading-tight">
                            <p className="truncate text-[11px] font-semibold text-white">
                                NexHire
                            </p>
                            <p className="truncate text-[9px] text-[#667386]">
                                AI Interview Session
                            </p>
                        </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-[#00b88a]/15 bg-[#00b88a]/[0.06] px-2 py-0.5">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00b88a] opacity-60" />
                            <span className="relative h-full w-full rounded-full bg-[#00b88a]" />
                        </span>
                        <span className="text-[8px] font-semibold uppercase tracking-wider text-[#00b88a]">
                            Live
                        </span>
                    </div>
                </div>

                {/* CONTENT */}
                <div className="flex flex-col gap-2.5 p-3.5">
                    {/* QUESTION */}
                    <div className="rounded-lg border border-white/[0.07] bg-[#0b1422] px-3 py-2.5">
                        <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-[8px] font-semibold uppercase tracking-[0.16em] text-[#667386]">
                                AI Interviewer
                            </span>
                            <span className="shrink-0 text-[9px] text-[#596577]">
                                Question {current + 1}/3
                            </span>
                        </div>

                        {/* grid trick: invisible copies reserve the tallest height */}
                        <div className="mt-1.5 grid">
                            {interviews.map((item, i) => (
                                <p
                                    key={i}
                                    aria-hidden="true"
                                    className={`invisible col-start-1 row-start-1 ${questionText}`}
                                >
                                    {item.question}
                                </p>
                            ))}
                            <p
                                key={current}
                                className={`question-enter col-start-1 row-start-1 ${questionText}`}
                            >
                                {interview.question}
                            </p>
                        </div>
                    </div>

                    {/* ANSWER */}
                    <div className="rounded-lg border border-[#00b88a]/10 bg-[#00b88a]/[0.025] px-3 py-2.5">
                        <div className="flex items-center justify-between gap-2">
                            <div className="flex min-w-0 items-center gap-1.5">
                                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-white/[0.06]">
                                    <span className="text-[6px] text-[#aab4c2]">
                                        You
                                    </span>
                                </span>
                                <span className="truncate text-[10px] font-medium text-[#8d98a8]">
                                    Candidate
                                </span>
                            </div>

                            {showAnswer && (
                                <span className="response-live shrink-0 text-[8px] uppercase tracking-wider text-[#00b88a]">
                                    Responding
                                </span>
                            )}
                        </div>

                        <div className="mt-1.5 grid">
                            {interviews.map((item, i) => (
                                <p
                                    key={i}
                                    aria-hidden="true"
                                    className={`invisible col-start-1 row-start-1 ${answerText}`}
                                >
                                    {item.answer}
                                </p>
                            ))}

                            {!showAnswer ? (
                                <div className="col-start-1 row-start-1 flex items-start gap-1 pt-1">
                                    <span className="h-1 w-1 animate-bounce rounded-full bg-[#00b88a]/50" />
                                    <span className="h-1 w-1 animate-bounce rounded-full bg-[#00b88a]/70 [animation-delay:-0.15s]" />
                                    <span className="h-1 w-1 animate-bounce rounded-full bg-[#00b88a] [animation-delay:-0.3s]" />
                                </div>
                            ) : (
                                <p
                                    key={current}
                                    className={`answer-enter col-start-1 row-start-1 ${answerText}`}
                                >
                                    {typedAnswer}
                                    <span className="ml-0.5 inline-block h-[1.1em] w-px animate-pulse bg-[#00b88a] align-middle" />
                                </p>
                            )}
                        </div>
                    </div>

                    {/* FOLLOW UP */}
                    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                        <div
                            key={current}
                            className={`flex min-w-0 items-center gap-2 ${showFollowUp ? "follow-up-enter" : "invisible"
                                }`}
                        >
                            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[#00b88a]/10">
                                <span className="text-[8px] text-[#00b88a]">
                                    AI
                                </span>
                            </div>

                            <div className="min-w-0 flex-1">
                                <p className="truncate text-[8px] uppercase tracking-wider text-[#596577]">
                                    AI Follow-up
                                </p>

                                <div className="mt-0.5 grid">
                                    {interviews.map((item, i) => (
                                        <p
                                            key={i}
                                            aria-hidden="true"
                                            className={`invisible col-start-1 row-start-1 ${followUpText}`}
                                        >
                                            {item.followUp}
                                        </p>
                                    ))}
                                    <p
                                        className={`col-start-1 row-start-1 ${followUpText}`}
                                    >
                                        {interview.followUp}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* METRICS */}
                    <div className="grid grid-cols-3 gap-1.5">
                        {metrics.map((metric, index) => (
                            <div
                                key={metric.label}
                                className="metric-card min-w-0 overflow-hidden rounded-md border border-white/[0.06] bg-[#0b1422] px-2 py-2"
                            >
                                <div className="flex items-center justify-between gap-1">
                                    <span className="min-w-0 truncate text-[8px] text-[#667386]">
                                        {metric.label}
                                    </span>
                                    <span className="shrink-0 text-[8px] font-semibold text-[#aab4c2]">
                                        {metric.value}
                                    </span>
                                </div>

                                <div className="mt-1.5 h-[3px] overflow-hidden rounded-full bg-white/[0.05]">
                                    <div
                                        className="metric-progress h-full rounded-full bg-[#00b88a]/70"
                                        style={{
                                            width: metric.width,
                                            animationDelay: `${index * 150}ms`,
                                        }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* STATUS + WAVEFORM */}
                    <div className="flex items-center justify-between gap-3 border-t border-white/[0.06] pt-2.5">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-1">
                                <span className="h-1 w-1 rounded-full bg-[#00b88a]" />
                                <span className="text-[9px] text-[#667386]">
                                    Tracking
                                </span>
                            </div>

                            <div className="flex items-center gap-1">
                                <span className="h-1 w-1 rounded-full bg-[#00b88a]" />
                                <span className="text-[9px] text-[#667386]">
                                    Liveness
                                </span>
                            </div>
                        </div>

                        <div className="flex h-5 items-center gap-[2px]">
                            {Array.from({ length: 22 }).map((_, index) => (
                                <span
                                    key={index}
                                    className="wave-bar w-[2px] shrink-0 rounded-full bg-[#00b88a]/50"
                                    style={{
                                        height: `${5 + ((index * 17) % 12)}px`,
                                        animationDelay: `${index * 45}ms`,
                                    }}
                                />
                            ))}
                        </div>
                    </div>
                </div>

                {/* PROGRESS */}
                <div className="absolute bottom-0 left-0 h-0.5 w-full bg-white/[0.04]">
                    <div
                        key={current}
                        className="interview-progress h-full bg-[#00b88a]/60"
                    />
                </div>
            </div>



        </div>
    );
}

export default InterviewPreview;