import { useState } from "react";

function Navbar() {
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const navLinks = [
        { name: "Interviews", href: "#interviews" },
        { name: "Features", href: "#features" }
        // { name: "About", href: "#about" },
    ];

    return (
        <header className="fixed left-0 top-0 z-50 w-full">
            <nav className="mx-auto w-full">
                <div className="flex h-10 items-center justify-around border-x border-b border-white/[0.08] bg-black px-4 backdrop-blur-xl">

                    {/* Logo */}
                    <a
                        href="#"
                        aria-label="NexHire Home"
                        className="shrink-0 text-tiny font-bold tracking-tight text-[#00b88a] transition-all duration-300 hover:text-[#08c99a] hover:drop-shadow-[0_0_8px_rgba(0,184,138,0.35)]"
                    >
                        &lt;NH&gt;
                    </a>

                    {/* Desktop Navigation */}
                    <div className="hidden items-center gap-6 md:flex lg:gap-8">
                        {navLinks.map((link) => (
                            <a
                                key={link.name}
                                href={link.href}
                                className="text-xs text-white transition-colors duration-300 hover:text-[#00b88a] lg:text-xs"
                            >
                                {link.name}
                            </a>
                        ))}
                    </div>

                    {/* Desktop Actions */}
                    <div className="hidden items-center gap-2 md:flex">


                        <a
                            href="/login"
                            className="rounded-md bg-[#00b88ad4] px-1 py-1 text-[11px] font-bold text-white transition-all duration-300 hover:bg-[#08c99a] hover:shadow-[0_0_20px_rgba(0,184,138,0.2)] "
                        >
                            Sign In
                        </a>
                    </div>

                    {/* Mobile Menu Button */}
                    <button
                        type="button"
                        onClick={() => setIsMenuOpen((prev) => !prev)}
                        className="flex h-8 w-8 items-center justify-center rounded-md border border-white/[0.08] text-[#aab4c2] transition-all duration-300 hover:border-[#00b88a]/30 hover:text-[#00b88a] md:hidden"
                        aria-label={isMenuOpen ? "Close menu" : "Open menu"}
                        aria-expanded={isMenuOpen}
                    >
                        <div className="flex w-4 flex-col gap-1">
                            <span
                                className={`h-px w-full bg-current transition-all duration-300 ${isMenuOpen ? "translate-y-1.5 rotate-45" : ""
                                    }`}
                            />

                            <span
                                className={`h-px w-full bg-current transition-all duration-300 ${isMenuOpen ? "opacity-0" : ""
                                    }`}
                            />

                            <span
                                className={`h-px w-full bg-current transition-all duration-300 ${isMenuOpen ? "-translate-y-1.5 -rotate-45" : ""
                                    }`}
                            />
                        </div>
                    </button>
                </div>

                {/* Mobile Menu */}
                <div
                    className={`overflow-hidden transition-all duration-300 md:hidden ${isMenuOpen
                        ? "max-h-80 opacity-100"
                        : "max-h-0 opacity-0"
                        }`}
                >
                    <div className="border-x border-b border-white/[0.08] bg-[#07101d]/95 p-3 backdrop-blur-xl">
                        {navLinks.map((link) => (
                            <a
                                key={link.name}
                                href={link.href}
                                onClick={() => setIsMenuOpen(false)}
                                className="block rounded-lg px-3 py-2.5 text-sm text-[#8d98a8] transition-colors hover:bg-white/[0.04] hover:text-white"
                            >
                                {link.name}
                            </a>
                        ))}

                        <div className="my-2 h-px bg-white/[0.06]" />

                        <a
                            href="/login"
                            onClick={() => setIsMenuOpen(false)}
                            className="block rounded-lg px-3 py-2.5 text-sm text-[#8d98a8] hover:text-white"
                        >
                            Sign In
                        </a>

                        <a
                            href="#start"
                            onClick={() => setIsMenuOpen(false)}
                            className="mt-1 block rounded-lg bg-[#00b88a] px-3 py-2.5 text-center text-sm font-semibold text-[#03110d]"
                        >
                            Get Started
                        </a>
                    </div>
                </div>
            </nav>
        </header>
    );
}

export default Navbar;