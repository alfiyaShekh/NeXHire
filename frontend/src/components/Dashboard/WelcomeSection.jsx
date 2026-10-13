
import { Link } from "react-router-dom";

function WelcomeSection() {
    return (
        <section className="mb-4">
            {/* Dashboard heading */}
            <div className="mb-3">
                <p className="mb-1 text-[8px] font-medium uppercase tracking-[0.12em] text-[#00b88a]">
                    Dashboard / Overview
                </p>

                <h1 className="text-[15px] font-semibold tracking-tight text-[#e7ebf1]">
                    Welcome back!
                </h1>

                <p className="mt-1 text-[9px] leading-4 text-[#7d899b]">
                    Ready to prepare for your next interview?
                </p>
            </div>

            {/* Create Interview Card */}
            <div className="rounded-md border border-[#12483e] bg-[#0c171b] px-3 py-3">
                {/* Status label */}
                <div className="mb-2 flex items-center gap-1.5">
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-3.5 w-3.5 shrink-0 text-[#00c99a]"
                        aria-hidden="true"
                    >
                        <path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3z" />
                        <path d="M19 15l1.1 2.9L23 19l-2.9 1.1L19 23l-1.1-2.9L15 19l2.9-1.1L19 15z" />
                    </svg>

                    <span className="text-[9px] font-semibold uppercase tracking-wide text-[#00c99a]">
                        Ready when you are
                    </span>
                </div>

                {/* Main heading */}
                <h2 className="text-[13px] font-semibold tracking-tight text-[#e7ebf1]">
                    Prepare for your next opportunity.
                </h2>

                {/* Description */}
                <p className="mt-2 text-[10px] leading-4 text-[#9aa7b8]">
                    Start a personalized mock interview and get feedback on your
                    answers, communication and interview behaviour.
                </p>

                {/* Compact button */}
                <Link
                    to="/interview/setup"
                    className="mt-3 inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-[10px] font-bold text-[#03130e] bg-[#00b88a] transition-colors duration-200 hover:bg-[#08c99a]"
                >
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        className="h-3 w-3"
                        aria-hidden="true"
                    >
                        <path d="M12 5v14M5 12h14" />
                    </svg>

                    Create Interview

                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-2.5 w-2.5"
                        aria-hidden="true"
                    >
                        <path d="M7 17 17 7M7 7h10v10" />
                    </svg>
                </Link>
            </div>
        </section>
    );
}

export default WelcomeSection;
