
import { Link } from "react-router-dom";

function RecentInterviews() {
    // Empty until connected to real interview history from the backend.
    const interviews = [];

    return (
        <section className="mb-5">
            {/* Section heading */}
            <div className="mb-3 flex items-center justify-between">
                <div>
                    <h2 className="text-[12px] font-semibold text-[#e7ebf1]">
                        Recent Interviews
                    </h2>
                    <p className="mt-1 text-[9px] text-[#758194]">
                        Review your previous interview sessions
                    </p>
                </div>

                <Link
                    to="/interviews"
                    className="inline-flex items-center gap-1 text-[9px] font-medium text-[#00b88a] transition-colors hover:text-[#08c99a]"
                >
                    View all
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-3 w-3"
                        aria-hidden="true"
                    >
                        <path d="M5 12h14" />
                        <path d="m12 5 7 7-7 7" />
                    </svg>
                </Link>
            </div>

            {/* Interview history or empty state */}
            {interviews.length === 0 ? (
                <div className="flex min-h-[145px] flex-col items-center justify-center rounded-lg border border-dashed border-white/[0.09] bg-[#0b111a] px-4 py-5 text-center">
                    <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-md border border-[#00b88a]/15 bg-[#00b88a]/[0.06] text-[#00b88a]">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="h-4 w-4"
                            aria-hidden="true"
                        >
                            <rect x="3" y="5" width="18" height="14" rx="2" />
                            <path d="m10 9 5 3-5 3z" />
                        </svg>
                    </div>

                    <h3 className="text-[11px] font-medium text-[#dce2ea]">
                        No interviews yet
                    </h3>

                    <p className="mt-1 max-w-xs text-[9px] leading-4 text-[#758194]">
                        Your completed interviews and performance reports will
                        appear here.
                    </p>

                    <Link
                        to="/interview/setup"
                        className="mt-3 inline-flex h-7 items-center gap-1.5 rounded-md border border-[#00b88a]/25 bg-[#00b88a]/[0.07] px-2.5 text-[9px] font-medium text-white transition-colors hover:bg-[#00b88a]/[0.13]"
                    >
                        Start your first interview
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.7"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="h-3 w-3"
                            aria-hidden="true"
                        >
                            <path d="M5 12h14" />
                            <path d="m12 5 7 7-7 7" />
                        </svg>
                    </Link>
                </div>
            ) : (
                <div className="overflow-hidden rounded-lg border border-white/[0.08] bg-[#0b111a]">
                    {interviews.map((interview) => (
                        <div
                            key={interview.id}
                            className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-3 py-3 last:border-b-0"
                        >
                            <div className="flex min-w-0 items-center gap-2.5">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#00b88a]/[0.08] text-[#00b88a]">
                                    <svg
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.6"
                                        className="h-4 w-4"
                                        aria-hidden="true"
                                    >
                                        <rect x="3" y="6" width="13" height="12" rx="2" />
                                        <path d="m16 10 5-3v10l-5-3" />
                                    </svg>
                                </div>

                                <div className="min-w-0">
                                    <p className="truncate text-[10px] font-medium text-[#e7ebf1]">
                                        {interview.role}
                                    </p>
                                    <p className="mt-1 text-[9px] text-[#758194]">
                                        {interview.type} · {interview.date}
                                    </p>
                                </div>
                            </div>

                            <div className="flex shrink-0 items-center gap-3">
                                <span className="text-[11px] font-semibold text-[#dce2ea]">
                                    {interview.score != null
                                        ? `${interview.score}%`
                                        : "—"}
                                </span>

                                <Link
                                    to={`/report/${interview.id}`}
                                    className="text-[9px] text-[#00b88a] hover:text-[#08c99a]"
                                >
                                    Report
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}

export default RecentInterviews;
