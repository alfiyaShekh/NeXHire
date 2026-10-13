function MovingBar() {
    const interviews = [
        {
            company: "Software Developer",
            type: "Technical Interview",
            level: "Junior",
            time: "Just now",
        },
        {
            company: "Web Developer",
            type: "AI Mock Interview",
            level: "Mid/Senior",
            time: "2m ago",
        },
        {
            company: "Data Scientist",
            type: "Technical Interview",
            level: "Mid/Senior",
            time: "4m ago",
        },
        {
            company: "Frontend Developer",
            type: "Practice Session",
            level: "Junior",
            time: "6m ago",
        },
        {
            company: "Backend Developer",
            type: "AI Interview",
            level: "Mid/Senior",
            time: "8m ago",
        },
        {
            company: "Software Engineer",
            type: "Mock Interview",
            level: "Junior",
            time: "10m ago",
        },
    ];

    // Duplicate the list so the animation can loop seamlessly.
    const items = [...interviews, ...interviews];

    return (
        <div className="fixed left-0 top-0 z-40 w-full overflow-hidden border-b border-white/[0.08] bg-[#07101d] sm:top-10">
            <div className="flex h-7 items-center">

                {/* Left fixed label */}
                <div className="relative z-10 flex h-full shrink-0 items-center bg-[#07101d] pl-4 pr-3 sm:pl-6 sm:pr-4 lg:pl-8">
                    <div className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#7c8797]" />

                        <span className="text-[9px] font-medium uppercase tracking-[0.22em] text-[#718096] sm:text-[10px]">
                            Recent
                        </span>
                    </div>

                    <div className="ml-4 h-4 w-px bg-white/[0.12]" />
                </div>

                {/* Moving area */}
                <div className="relative min-w-0 flex-1 overflow-hidden">

                    {/* Left fade */}
                    <div className="pointer-events-none absolute left-0 top-0 z-10 h-full w-12 bg-gradient-to-r from-[#07101d] to-transparent" />

                    {/* Scrolling content */}
                    <div className="moving-bar-track flex w-max items-center gap-2.5">
                        {items.map((item, index) => (
                            <div
                                key={`${item.company}-${index}`}
                                className="flex h-5 items-center gap-2 rounded-full border border-white/[0.09] bg-[#101a2a] px-3 whitespace-nowrap"
                            >
                                {/* Status dot */}
                                <span className="h-1 w-1 shrink-0 rounded-full bg-[#586577]" />

                                {/* Company / Role */}
                                <span className="text-[8px] font-semibold text-[#d7dce4]">
                                    {item.company}
                                </span>

                                {/* Separator */}
                                <span className="text-[8px] text-[#536071]">
                                    ·
                                </span>

                                {/* Interview type */}
                                <span className="text-[10px] font-medium text-[#9aa5b5]">
                                    {item.type}
                                </span>

                                {/* Level */}
                                <span
                                    className={`rounded-full px-2 py-0.5 text-[8px] font-semibold ${item.level === "Junior"
                                        ? "bg-[#00b88a]/10 text-[#00b88a]"
                                        : "bg-[#8b6500]/15 text-[#d99d00]"
                                        }`}
                                >
                                    {item.level}
                                </span>

                                {/* Time */}
                                <span className="text-[9px] text-[#596577]">
                                    {item.time}
                                </span>
                            </div>
                        ))}
                    </div>


                    {/* Right fade */}
                    <div className="pointer-events-none absolute right-0 top-0 z-10 h-full w-16 bg-gradient-to-l from-[#07101d] to-transparent" />
                </div>
            </div>
        </div>
    );
}


export default MovingBar;