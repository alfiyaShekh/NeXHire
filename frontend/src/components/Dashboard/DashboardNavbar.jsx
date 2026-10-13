
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

function DashboardNavbar() {
    const [profileOpen, setProfileOpen] = useState(false);
    const navigate = useNavigate();


    const handleLogout = () => {
        localStorage.removeItem("nexhire_token");
        localStorage.removeItem("nexhire_user");

        // Replace the current history entry instead of adding another one.
        window.location.replace("/login");
    };

    return (
        <header className="sticky top-0 z-50 w-full border-b border-white/[0.06] bg-[#0b1018]">
            <div className="mx-auto flex h-11 max-w-7xl items-center justify-between px-3 sm:px-5">

                {/* Brand */}
                <Link
                    to="/dashboard"
                    aria-label="NexHire Dashboard"
                    className="flex items-center gap-2"
                >
                    <span className="flex h-6 w-6 items-center justify-center rounded border border-[#00b88a]/20 bg-[#0b2520] text-[9px] font-bold text-[#00b88a]">
                        NH
                    </span>

                    <span className="flex flex-col gap-0.5">
                        <span className="text-[11px] font-semibold leading-none tracking-tight text-[#e7ebf1]">
                            NexHire
                        </span>
                        <span className="text-[8px] leading-none text-[#758194]">
                            AI Interview Coach
                        </span>
                    </span>
                </Link>

                {/* Actions */}
                <div className="flex items-center gap-1 sm:gap-2">

                    {/* Dashboard */}
                    <Link
                        to="/dashboard"
                        title="Dashboard"
                        aria-label="Dashboard"
                        className="flex h-7 w-7 items-center justify-center rounded text-[#8994a5] transition-colors hover:bg-white/[0.04] hover:text-[#00b88a]"
                    >
                        <svg viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="1.6"
                            className="h-3.5 w-3.5" aria-hidden="true">
                            <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
                            <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
                            <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
                            <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
                        </svg>
                    </Link>

                    {/* Notifications */}
                    <button
                        type="button"
                        title="Notifications"
                        aria-label="Notifications"
                        className="flex h-7 w-7 items-center justify-center rounded text-[#8994a5] transition-colors hover:bg-white/[0.04] hover:text-[#00b88a]"
                    >
                        <svg viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="1.6"
                            strokeLinecap="round" strokeLinejoin="round"
                            className="h-3.5 w-3.5" aria-hidden="true">
                            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                            <path d="M10 21h4" />
                        </svg>
                    </button>

                    {/* Profile */}
                    <div className="relative">
                        <button
                            type="button"
                            title="Profile"
                            aria-label="Open profile menu"
                            aria-expanded={profileOpen}
                            onClick={() => setProfileOpen((open) => !open)}
                            className="flex h-6 w-6 items-center justify-center overflow-hidden rounded-full border border-white/[0.12] bg-[#12221f] text-[#00b88a] transition-colors hover:border-[#00b88a]/50"
                        >
                            <svg viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="1.6"
                                className="h-3.5 w-3.5" aria-hidden="true">
                                <circle cx="12" cy="8" r="3.5" />
                                <path d="M5 20c.6-3.4 3.2-5.5 7-5.5s6.4 2.1 7 5.5" />
                            </svg>
                        </button>

                        {profileOpen && (
                            <div className="absolute right-0 top-8 z-50 w-36 rounded-md border border-white/[0.08] bg-[#101620] p-1 shadow-xl">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setProfileOpen(false);
                                        navigate("/profile");
                                    }}
                                    className="w-full rounded px-2.5 py-2 text-left text-[10px] text-[#c0c8d4] hover:bg-white/[0.04] hover:text-[#00b88a]"
                                >
                                    Profile settings
                                </button>

                                <div className="my-1 border-t border-white/[0.06]" />

                                <button
                                    type="button"
                                    onClick={handleLogout}
                                    className="w-full rounded px-2.5 py-2 text-left text-[10px] text-[#c0c8d4] hover:bg-white/[0.04] hover:text-red-400"
                                >
                                    Log out
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Logout */}
                    <button
                        type="button"
                        onClick={handleLogout}
                        className="flex h-7 items-center gap-1 rounded px-1.5 text-[9px] font-medium text-[#8994a5] transition-colors hover:bg-white/[0.04] hover:text-red-400"
                    >
                        <svg viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="1.6"
                            strokeLinecap="round" strokeLinejoin="round"
                            className="h-3.5 w-3.5" aria-hidden="true">
                            <path d="M10 17l5-5-5-5" />
                            <path d="M15 12H3" />
                            <path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" />
                        </svg>
                        <span className="hidden sm:inline">Logout</span>
                    </button>
                </div>
            </div>
        </header>
    );
}

export default DashboardNavbar;
