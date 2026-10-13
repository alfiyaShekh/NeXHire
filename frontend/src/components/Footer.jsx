function Footer() {
    return (
        <footer className="border-t border-white/[0.08] bg-[#020712]">
            <div className="mx-auto max-w-5xl px-6">

                {/* Top */}
                <div className="flex items-center justify-between py-4">
                    <a
                        href="#"
                        className="text-lg font-bold tracking-tight text-[#00b88a] transition-colors duration-300 hover:text-[#08c99a]"
                    >
                        &lt;NH&gt;
                    </a>

                    <span className="text-[10px] text-[#596577]">
                        © 2026 NexHire. All rights reserved.
                    </span>
                </div>

                {/* Divider */}
                <div className="h-px bg-white/[0.08]" />

                {/* Bottom */}
                <div className="flex items-center justify-center py-2.5">
                    <p className="text-[9px] text-[#4f5b6b]">
                        AI-powered mock interviews for better preparation.
                    </p>
                </div>

            </div>
        </footer>
    );
}

export default Footer;