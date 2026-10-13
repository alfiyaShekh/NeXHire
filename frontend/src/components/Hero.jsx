import InterviewPreview from "./InterviewPreview";

function Hero() {
    return (
        <section
            className="
                relative
                flex
                min-h-[100svh]
                w-full
                items-center
                overflow-x-clip
                px-4
                pb-16
                pt-28
                sm:px-6
                sm:pb-16
                sm:pt-32
                md:px-8
                lg:px-10
                lg:pb-20
                lg:pt-32
                xl:px-12
            "
        >
            {/* ================= BACKGROUND GLOW ================= */}
            <div
                className="
                    pointer-events-none
                    absolute
                    left-1/2
                    top-[15%]
                    h-[280px]
                    w-[280px]
                    -translate-x-1/2
                    rounded-full
                    bg-black
                    blur-[100px]
                    sm:h-[400px]
                    sm:w-[400px]
                    lg:left-[25%]
                    lg:top-[20%]
                    lg:h-[500px]
                    lg:w-[500px]
                    lg:translate-x-0
                "
            />

            {/* ================= MAIN HERO ================= */}
            <div
                className="
                    relative
                    mx-auto
                    w-full
                    max-w-7xl
                    md:grid
                    md:grid-cols-[0.95fr_1.05fr]
                    md:items-center
                    md:gap-3
                    lg:gap-8
                    xl:gap-10
                "
            >
                {/* =================================================
                    LEFT CONTENT
                    ================================================= */}
                <div
                    className="
                        mx-auto
                        w-full
                        max-w-xl
                        text-center
                        md:mx-0
                        md:pr-2
                        md:text-left
                    "
                >
                    {/* Eyebrow */}
                    <div
                        className="
                            mb-5
                            flex
                            items-center
                            justify-center
                            gap-2
                            md:justify-start
                        "
                    >
                        <span
                            className="
                                h-1.5
                                w-1.5
                                shrink-0
                                rounded-full
                                bg-[#00b88a]
                            "
                        />

                        <span
                            className="
                                text-[8px]
                                font-semibold
                                uppercase
                                tracking-[0.2em]
                                text-[#00b88a]
                                sm:text-[10px]
                            "
                        >
                            AI-Powered Mock Interviews
                        </span>
                    </div>

                    {/* Heading */}
                    <h1
                        className="
                            text-[clamp(1.5rem,4vw,2rem)]
                            font-semibold
                            leading-[1.1]
                            tracking-[-0.03em]
                            text-[#f5f7fa]
                            sm:text-[1.8rem]
                            lg:text-[2.1rem]
                            xl:text-[2.4rem]
                        "
                    >
                        Train for the Interview.
                        <br />

                        <span
                            className="
                                font-normal
                                italic
                                text-[1.2rem]
                                text-[#8d98a8]
                                sm:text-[1.3rem]
                                lg:text-[1.35rem]
                            "
                        >
                            Perform like you're ready.
                        </span>
                    </h1>

                    {/* Description */}
                    <p
                        className="
                            mx-auto
                            mt-5
                            max-w-lg
                            text-[12px]
                            leading-5
                            text-[#8d98a8]
                            sm:mt-6
                            sm:text-[13px]
                            sm:leading-6
                            md:mx-0
                        "
                    >
                        NexHire simulates realistic AI interviews and analyzes
                        your answers, communication, eye contact, and interview
                        behavior to help you become a stronger candidate.
                    </p>

                    {/* ================= BUTTONS ================= */}
                    <div
                        className="
                            mt-5
                            flex
                            flex-col
                            items-center
                            gap-3
                            sm:mt-8
                            sm:flex-row
                            sm:justify-center
                            md:justify-start
                        "
                    >
                        <a
                            href="#start"
                            className="
                                inline-flex
                                h-9
                                w-fit
                                shrink-0
                                items-center
                                justify-center
                                gap-2
                                whitespace-nowrap
                                rounded-lg
                                bg-[#00b88a]
                                px-4
                                text-[11px]
                                font-semibold
                                leading-none
                                tracking-[-0.01em]
                                text-white
                                shadow-[0_4px_20px_rgba(0,184,138,0.12)]
                                transition-all
                                duration-300
                                hover:bg-[#08c99a]
                                hover:shadow-[0_6px_28px_rgba(0,184,138,0.22)]
                                active:scale-[0.98]
                            "
                        >
                            Start Mock Interview

                            <span className="text-[12px]">→</span>
                        </a>

                        <a
                            href="#how-it-works"
                            className="
                                inline-flex
                                h-9
                                w-fit
                                shrink-0
                                items-center
                                justify-center
                                whitespace-nowrap
                                rounded-lg
                                border
                                border-white/[0.1]
                                px-4
                                text-[12px]
                                font-medium
                                leading-none
                                tracking-[-0.01em]
                                text-[#aab4c2]
                                transition-all
                                duration-300
                                hover:border-white/[0.18]
                                hover:bg-white/[0.03]
                                hover:text-white
                            "
                        >
                            See How It Works
                        </a>
                    </div>

                    {/* ================= CAPABILITIES ================= */}
                    <div
                        className="
                            mt-7
                            flex
                            flex-wrap
                            items-center
                            justify-center
                            gap-x-3
                            gap-y-2
                            text-[9px]
                            text-[#667386]
                            sm:mt-8
                            sm:gap-x-4
                            sm:text-[10px]
                            md:justify-start
                        "
                    >
                        <span>AI Questions</span>
                        <span className="text-[#334052]">•</span>
                        <span>Eye Contact</span>
                        <span className="text-[#334052]">•</span>
                        <span>Voice Analysis</span>
                        <span className="text-[#334052]">•</span>
                        <span>Behavior</span>
                    </div>
                </div>

                {/* =================================================
                    RIGHT INTERVIEW PREVIEW
                    ================================================= */}
                <div
                    className="
                        relative
                        mt-12
                        flex
                        w-full
                        justify-center
                        pb-6
                        md:mt-0
                        md:justify-end
                        md:pb-0
                    "
                >
                    <InterviewPreview />
                </div>
            </div>
        </section>
    );
}

export default Hero;