
const stats = [
    {
        label: "Total Interviews",
        value: "—",
        detail: "Interviews completed",
        progress: 0,
        color: "#00c99a",
        icon: (
            <svg viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round"
                className="h-4 w-4" aria-hidden="true">
                <rect x="3" y="6" width="13" height="12" rx="2" />
                <path d="m16 10 5-3v10l-5-3" />
            </svg>
        ),
    },
    {
        label: "Average Score",
        value: "—",
        detail: "Across completed interviews",
        progress: 0,
        color: "#42a5ff",
        icon: (
            <svg viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round"
                className="h-4 w-4" aria-hidden="true">
                <path d="M3 3v18h18" />
                <path d="m7 14 4-4 4 3 6-7" />
            </svg>
        ),
    },
    {
        label: "Best Score",
        value: "—",
        detail: "Your highest interview score",
        progress: 0,
        color: "#b783ff",
        icon: (
            <svg viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round"
                className="h-4 w-4" aria-hidden="true">
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="5" />
                <circle cx="12" cy="12" r="1.5" />
            </svg>
        ),
    },
];

function ProgressRing({ progress, color }) {
    const radius = 17;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - progress / 100);

    return (
        <svg
            viewBox="0 0 44 44"
            className="h-10 w-10 shrink-0"
            aria-hidden="true"
        >
            <circle
                cx="22"
                cy="22"
                r={radius}
                fill="none"
                stroke="#202b38"
                strokeWidth="3.5"
            />

            <circle
                cx="22"
                cy="22"
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                transform="rotate(-90 22 22)"
                className="transition-all duration-500"
            />

            <circle
                cx="22"
                cy="22"
                r="2"
                fill={color}
                opacity={progress > 0 ? 1 : 0.35}
            />
        </svg>
    );
}

function StatsCards() {
    return (
        <section className="mb-5">
            <div className="mb-3">
                <h2 className="text-[12px] font-semibold text-[#e7ebf1]">
                    Your Performance
                </h2>
                <p className="mt-1 text-[9px] text-[#758194]">
                    An overview of your interview progress
                </p>
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                {stats.map((stat) => (
                    <div
                        key={stat.label}
                        className="group flex min-h-[116px] max-w-[300px] items-center justify-between gap-3 rounded-lg border border-white/[0.08] bg-[#0b121b] px-3 py-3.5 transition-colors duration-200 hover:border-white/[0.15] hover:bg-[#101923]"
                    >
                        <div className="min-w-0 flex-1">
                            <div className="mb-2 flex items-center gap-2">
                                <span
                                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                                    style={{
                                        color: stat.color,
                                        backgroundColor: `${stat.color}18`,
                                    }}
                                >
                                    {stat.icon}
                                </span>

                                <span className="text-[10px] font-medium text-[#a3afbf]">
                                    {stat.label}
                                </span>
                            </div>

                            <p className="text-[19px] font-semibold leading-tight tracking-tight text-[#f0f3f8]">
                                {stat.value}
                            </p>

                            <p className="mt-1.5 text-[9px] leading-4 text-[#788699]">
                                {stat.detail}
                            </p>
                        </div>

                        <ProgressRing
                            progress={stat.progress}
                            color={stat.color}
                        />
                    </div>
                ))}
            </div>
        </section>
    );
}

export default StatsCards;
