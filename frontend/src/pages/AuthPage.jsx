
import { useMemo, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

/* ---------------- validation ---------------- */

const emailOk = (value) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);

const userOk = (value) =>
    /^[a-zA-Z0-9_]{3,20}$/.test(value);

const strengthOf = (password) => {
    let strength = 0;

    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;

    return strength;
};

const STRENGTH_LABEL = [
    "Too weak",
    "Weak",
    "Fair",
    "Good",
    "Strong",
];

const STRENGTH_COLOR = [
    "bg-white/10",
    "bg-red-500",
    "bg-amber-500",
    "bg-lime-400",
    "bg-[#00b88a]",
];

const API_BASE_URL = "http://127.0.0.1:8000";

/* ---------------- icons ---------------- */

const Svg = ({ children, className = "h-3 w-3" }) => (
    <svg
        viewBox="0 0 24 24"
        className={className}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
    >
        {children}
    </svg>
);

const Eye = ({ off }) =>
    off ? (
        <Svg>
            <path d="M3 3l18 18" />
            <path d="M10.6 6.1A9.8 9.8 0 0112 6c5 0 8.5 4.2 9.5 6-.4.8-1.2 1.9-2.3 3M6.4 7.6C4.4 9 3 11 2.5 12c1 1.8 4.5 6 9.5 6 1.5 0 2.8-.4 4-1" />
            <path d="M9.9 9.9a3 3 0 004.2 4.2" />
        </Svg>
    ) : (
        <Svg>
            <path d="M2.5 12C3.5 10.2 7 6 12 6s8.5 4.2 9.5 6c-1 1.8-4.5 6-9.5 6s-8.5-4.2-9.5-6z" />
            <circle cx="12" cy="12" r="3" />
        </Svg>
    );

/* ---------------- trust chips ---------------- */

const TRUST = [
    {
        label: "Secure",
        tip: "Passwords are hashed and never stored in plain text.",
        color: "text-[#00b88a]",
        icon: (
            <Svg>
                <rect x="5" y="11" width="14" height="9" rx="2" />
                <path d="M8 11V8a4 4 0 018 0v3" />
            </Svg>
        ),
    },
    {
        label: "Trusted",
        tip: "Prepare confidently for real interviews.",
        color: "text-sky-400",
        icon: (
            <Svg>
                <circle cx="12" cy="12" r="9" />
                <path d="M8 12.5l3 3 5-6" />
            </Svg>
        ),
    },
    {
        label: "Reliable",
        tip: "Your progress can be saved to your account.",
        color: "text-violet-400",
        icon: (
            <Svg>
                <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />
            </Svg>
        ),
    },
];

function TrustChips() {
    return (
        <ul className="mt-3 flex items-center justify-center gap-2">
            {TRUST.map((item) => (
                <li key={item.label} className="group relative">
                    <button
                        type="button"
                        title={item.tip}
                        className="flex items-center gap-1 rounded-full border border-white/[0.07] bg-white/[0.02] px-2 py-1 text-[9px] text-[#8b97a8] transition hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#00b88a]"
                    >
                        <span className={item.color}>{item.icon}</span>
                        {item.label}
                    </button>

                    <span
                        role="tooltip"
                        className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-36 -translate-x-1/2 rounded-md border border-white/10 bg-[#15151a] px-2 py-1.5 text-center text-[9px] leading-4 text-[#aab4c2] opacity-0 shadow-xl transition-opacity group-hover:opacity-100"
                    >
                        {item.tip}
                    </span>
                </li>
            ))}
        </ul>
    );
}

/* ---------------- reusable field ---------------- */

function Field({
    id,
    label,
    error,
    right,
    trailing,
    ...inputProps
}) {
    return (
        <div>
            <div className="mb-1 flex items-center justify-between gap-2">
                <label
                    htmlFor={id}
                    className="text-xs font-semibold text-white"
                >
                    {label}
                </label>
                {right}
            </div>

            <div className="relative">
                <input
                    id={id}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? `${id}-error` : undefined}
                    className={`h-9 w-full rounded-md border bg-[#2a2a2f] px-3 text-xs text-white outline-none placeholder:text-[#7c7c86] transition focus:ring-1 ${error
                        ? "border-red-500/50 focus:border-red-500 focus:ring-red-500/20"
                        : "border-white/[0.07] focus:border-[#00b88a]/60 focus:ring-[#00b88a]/25"
                        } ${trailing ? "pr-9" : ""}`}
                    {...inputProps}
                />

                {trailing}
            </div>

            <p
                id={`${id}-error`}
                className={`text-[10px] text-red-400 ${error ? "mt-1 min-h-3" : "h-0 overflow-hidden"
                    }`}
            >
                {error}
            </p>
        </div>
    );
}

/* ---------------- main authentication page ---------------- */

export default function AuthPage({ mode = "login" }) {
    const isRegister = mode === "register";

    const navigate = useNavigate();
    const location = useLocation();

    const [form, setForm] = useState({
        email: "",
        username: "",
        password: "",
    });

    const [touched, setTouched] = useState({});
    const [showPw, setShowPw] = useState(false);
    const [caps, setCaps] = useState(false);
    const [loading, setLoading] = useState(false);
    const [formError, setFormError] = useState("");
    const [successMessage, setSuccessMessage] = useState(
        location.state?.message || ""
    );
    const [shake, setShake] = useState(false);

    const errors = useMemo(
        () => ({
            email: !form.email.trim()
                ? "Enter your email address."
                : !emailOk(form.email.trim())
                    ? "Enter a valid email address."
                    : "",

            username: !form.username.trim()
                ? "Choose a username."
                : !userOk(form.username.trim())
                    ? "Use 3–20 letters, numbers or underscores."
                    : "",

            password: !form.password
                ? "Enter your password."
                : form.password.length < (isRegister ? 8 : 1)
                    ? `Use at least ${isRegister ? 8 : 1} characters.`
                    : form.password.length > 128
                        ? "Password cannot exceed 128 characters."
                        : "",
        }),
        [form, isRegister]
    );

    const strength = strengthOf(form.password);

    const fields = isRegister
        ? ["email", "username", "password"]
        : ["email", "password"];

    const updateField = (key) => (event) => {
        setFormError("");
        setSuccessMessage("");

        setForm((previous) => ({
            ...previous,
            [key]: event.target.value,
        }));
    };

    const blurField = (key) => () => {
        setTouched((previous) => ({
            ...previous,
            [key]: true,
        }));
    };

    const fieldError = (key) =>
        touched[key] ? errors[key] : "";

    /* ---------------- API submission ---------------- */

    const onSubmit = async (event) => {
        event.preventDefault();

        const touchedFields = {
            email: true,
            password: true,
            ...(isRegister ? { username: true } : {}),
        };

        setTouched(touchedFields);
        setFormError("");
        setSuccessMessage("");

        if (fields.some((key) => errors[key])) {
            setShake(true);
            window.setTimeout(() => setShake(false), 450);
            return;
        }

        setLoading(true);

        try {
            const endpoint = isRegister
                ? `${API_BASE_URL}/api/auth/register`
                : `${API_BASE_URL}/api/auth/login`;

            const payload = isRegister
                ? {
                    name: form.username.trim(),
                    email: form.email.trim().toLowerCase(),
                    password: form.password,
                }
                : {
                    email: form.email.trim().toLowerCase(),
                    password: form.password,
                };

            const response = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const detail = data.detail;

                throw new Error(
                    typeof detail === "string"
                        ? detail
                        : Array.isArray(detail)
                            ? detail.map((item) => item.msg).join(", ")
                            : "The request failed. Please try again."
                );
            }

            if (isRegister) {
                navigate("/login", {
                    replace: true,
                    state: {
                        message: "Account created successfully. Please sign in.",
                    },
                });
                return;
            }

            if (!data.access_token || !data.user) {
                throw new Error(
                    "The server response is missing the login token or user details."
                );
            }

            localStorage.setItem("nexhire_token", data.access_token);
            localStorage.setItem(
                "nexhire_user",
                JSON.stringify(data.user)
            );

            const destination =
                location.state?.from?.pathname || "/dashboard";

            navigate(destination, { replace: true });
        } catch (error) {
            if (
                error instanceof TypeError &&
                error.message.toLowerCase().includes("fetch")
            ) {
                setFormError(
                    "Cannot connect to the NexHire server. Check that the backend is running."
                );
            } else {
                setFormError(
                    error.message ||
                    (isRegister
                        ? "Could not create your account. Please try again."
                        : "Could not sign you in. Please check your details.")
                );
            }
        } finally {
            setLoading(false);
        }
    };

    /* ---------------- UI ---------------- */

    return (
        <main className="min-h-screen overflow-y-auto bg-[#03060f] text-white">
            <style>{`
        @keyframes nh-shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }

        @keyframes nh-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @keyframes nh-glow {
          0%, 100% { opacity: .55; }
          50% { opacity: .9; }
        }

        .nh-shake { animation: nh-shake .45s ease-in-out; }
        .nh-in { animation: nh-in .45s ease-out both; }
        .nh-glow { animation: nh-glow 6s ease-in-out infinite; }

        @media (prefers-reduced-motion: reduce) {
          .nh-shake, .nh-in, .nh-glow { animation: none; }
        }
      `}</style>

            {/* Background glow */}
            <div className="pointer-events-none fixed inset-x-0 top-0 h-72 overflow-hidden">
                <div className="nh-glow absolute left-1/2 top-[-120px] h-72 w-[520px] -translate-x-1/2 rounded-full bg-[#00b88a]/15 blur-3xl" />
            </div>

            <div className="relative flex min-h-screen flex-col items-center justify-center px-4 py-8">
                <div className="w-full max-w-sm">
                    {/* Logo and heading */}
                    <div className="text-center">
                        <Link
                            to="/"
                            aria-label="NexHire home"
                            className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#00b88a] to-[#00875f] text-sm font-bold text-white shadow-[0_8px_30px_-8px_rgba(0,184,138,0.6)] transition-transform duration-300 hover:scale-105"
                        >
                            NH
                        </Link>

                        <h1
                            key={mode}
                            className="nh-in mt-4 text-xl font-bold tracking-tight"
                        >
                            {isRegister
                                ? "Create your account"
                                : "Welcome back"}
                        </h1>

                        <p className="mt-1 text-xs text-[#aab4c2]">
                            {isRegister
                                ? "Start your journey to interview success"
                                : "Continue your journey to interview success"}
                        </p>
                    </div>

                    {/* Authentication card */}
                    <div
                        className={`mt-6 rounded-xl border border-white/[0.06] bg-[#1f1f24] p-5 shadow-[0_25px_70px_-30px_rgba(0,0,0,0.9)] ${shake ? "nh-shake" : ""
                            }`}
                    >
                        <form
                            key={mode}
                            onSubmit={onSubmit}
                            noValidate
                            className="nh-in space-y-3"
                        >
                            <Field
                                id="email"
                                label="Email address"
                                type="email"
                                autoComplete="email"
                                placeholder="Enter your email address"
                                value={form.email}
                                onChange={updateField("email")}
                                onBlur={blurField("email")}
                                error={fieldError("email")}
                                disabled={loading}
                                required
                            />

                            {isRegister && (
                                <Field
                                    id="username"
                                    label="Username"
                                    type="text"
                                    autoComplete="username"
                                    placeholder="Choose a username"
                                    value={form.username}
                                    onChange={updateField("username")}
                                    onBlur={blurField("username")}
                                    error={fieldError("username")}
                                    disabled={loading}
                                    required
                                />
                            )}

                            <div>
                                <Field
                                    id="password"
                                    label="Password"
                                    type={showPw ? "text" : "password"}
                                    autoComplete={
                                        isRegister ? "new-password" : "current-password"
                                    }
                                    placeholder={
                                        isRegister
                                            ? "Create a password"
                                            : "Enter your password"
                                    }
                                    value={form.password}
                                    onChange={updateField("password")}
                                    onBlur={() => {
                                        blurField("password")();
                                        setCaps(false);
                                    }}
                                    onKeyUp={(event) => {
                                        setCaps(
                                            event.getModifierState?.("CapsLock") || false
                                        );
                                    }}
                                    error={fieldError("password")}
                                    disabled={loading}
                                    required
                                    maxLength={128}
                                    right={
                                        !isRegister && (
                                            <span className="text-[10px] text-[#8b97a8]">
                                                Secure sign-in
                                            </span>
                                        )
                                    }
                                    trailing={
                                        <button
                                            type="button"
                                            onClick={() => setShowPw((previous) => !previous)}
                                            aria-label={
                                                showPw ? "Hide password" : "Show password"
                                            }
                                            className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-[#8b97a8] transition-colors hover:text-[#00b88a]"
                                        >
                                            <Eye off={showPw} />
                                        </button>
                                    }
                                />

                                {caps && (
                                    <p className="mt-1 text-[10px] text-amber-400">
                                        Caps Lock is on.
                                    </p>
                                )}

                                {/* Password strength */}
                                {isRegister && form.password && (
                                    <div className="mt-2 flex items-center gap-2">
                                        <div className="flex flex-1 gap-1">
                                            {[1, 2, 3, 4].map((number) => (
                                                <span
                                                    key={number}
                                                    className={`h-1 flex-1 rounded-full transition-colors duration-300 ${strength >= number
                                                        ? STRENGTH_COLOR[strength]
                                                        : "bg-white/10"
                                                        }`}
                                                />
                                            ))}
                                        </div>

                                        <span className="w-12 text-right text-[10px] text-[#8b97a8]">
                                            {STRENGTH_LABEL[strength]}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* API error */}
                            {formError && (
                                <p
                                    role="alert"
                                    className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
                                >
                                    {formError}
                                </p>
                            )}

                            {/* Success message */}
                            {successMessage && (
                                <p
                                    role="status"
                                    className="rounded-md border border-[#00b88a]/30 bg-[#00b88a]/10 px-3 py-2 text-xs text-[#00b88a]"
                                >
                                    {successMessage}
                                </p>
                            )}

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-gradient-to-b from-[#12a87c] to-[#0b8a65] text-xs font-semibold text-[#02120c] transition-all duration-300 hover:brightness-110 hover:shadow-[0_0_24px_rgba(0,184,138,0.3)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
                            >
                                {loading ? (
                                    <>
                                        <svg
                                            className="h-4 w-4 animate-spin"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            aria-hidden="true"
                                        >
                                            <circle
                                                cx="12"
                                                cy="12"
                                                r="9"
                                                stroke="currentColor"
                                                strokeOpacity=".25"
                                                strokeWidth="3"
                                            />
                                            <path
                                                d="M21 12a9 9 0 00-9-9"
                                                stroke="currentColor"
                                                strokeWidth="3"
                                                strokeLinecap="round"
                                            />
                                        </svg>
                                        {isRegister
                                            ? "Creating account..."
                                            : "Signing in..."}
                                    </>
                                ) : isRegister ? (
                                    "Create account"
                                ) : (
                                    "Continue"
                                )}
                            </button>
                        </form>
                    </div>

                    {/* Switch login/register */}
                    <p className="mt-5 text-center text-xs text-[#8b97a8]">
                        {isRegister
                            ? "Already have an account? "
                            : "Don't have an account? "}

                        <Link
                            to={isRegister ? "/login" : "/register"}
                            className="font-semibold text-[#00b88a] transition-colors hover:text-[#08c99a]"
                        >
                            {isRegister ? "Sign in" : "Create account"}
                        </Link>
                    </p>

                    <TrustChips />

                    <p className="mt-5 text-center text-[10px] text-[#626b7a]">
                        By continuing, you agree to use NexHire responsibly.
                    </p>
                </div>
            </div>
        </main>
    );
}

/* ---------------- route components ---------------- */

export const LoginPage = () => <AuthPage mode="login" />;

export const RegisterPage = () => <AuthPage mode="register" />;
