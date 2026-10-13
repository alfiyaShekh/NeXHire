
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const roles = [
    "Software Developer",
    "Web Developer",
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "Data Scientist",
    "Data Analyst",
    "AI / ML Engineer",
    "DevOps Engineer",
    "Cybersecurity Analyst",
    "Other",
];

const experienceLevels = [
    "Fresher",
    "Junior (0–2 years)",
    "Mid-level (2–5 years)",
    "Experienced (5+ years)",
];

const interviewTypes = [
    { value: "Technical", icon: "⌘", description: "Technical skills" },
    { value: "HR", icon: "◎", description: "Communication" },
    { value: "Mixed", icon: "◈", description: "Both areas" },
];

const difficulties = [
    { value: "Easy", description: "Fundamentals" },
    { value: "Medium", description: "Balanced" },
    { value: "Hard", description: "Advanced" },
];

const questionCounts = [5, 10, 15, 20];

const inputClass =
    "h-[27px] w-full rounded border border-white/[0.09] bg-[#080e16] px-2 text-[8px] text-[#e7ebf1] outline-none transition duration-200 focus:border-[#00b88a]/70 focus:ring-1 focus:ring-[#00b88a]/10";

function SetupSection({ number, title, description, children }) {
    return (
        <section className="group rounded-md border border-white/[0.07] bg-[#0b121b] p-2 transition-colors duration-200 hover:border-white/[0.12]">
            <div className="mb-2 flex items-center gap-1.5">
                <span className="flex h- w-4 shrink-0 items-center justify-center rounded border border-[#00b88a]/20 bg-[#0c2922] text-[8px] font-semibold text-[#00c99a] transition-colors group-hover:border-[#00b88a]/50">
                    {number}
                </span>

                <div className="min-w-0">
                    <h2 className="text-[10px] font-semibold text-[#e7ebf1]">
                        {title}
                    </h2>
                    <p className="mt-0.5 text-[7px] leading-3 text-[#758194]">
                        {description}
                    </p>
                </div>
            </div>

            {children}
        </section>
    );
}

function FieldLabel({ children }) {
    return (
        <label className="mb-1 block text-[8px] font-medium text-[#a8b4c4]">
            {children}
        </label>
    );
}

function ChoiceButton({ selected, onClick, children, className = "" }) {
    return (
        <button
            type="button"
            onClick={onClick}
            aria-pressed={selected}
            className={`relative flex items-center justify-center gap-1 rounded border px-1.5 py-1 text-[8px] transition-all duration-200 active:scale-[0.98] ${selected
                ? "border-[#00b88a]/70 bg-[#103128] text-[#43e0b5] shadow-[inset_0_0_10px_rgba(0,184,138,0.05)]"
                : "border-white/[0.08] bg-[#080e16] text-[#8d9bad] hover:border-[#00b88a]/30 hover:bg-[#0d171b] hover:text-[#d5e1ec]"
                } ${className}`}
        >
            {children}

            {selected && (
                <svg
                    viewBox="0 0 24 24"
                    className="h-2.5 w-2.5 shrink-0"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                >
                    <path d="m5 12 4 4L19 6" />
                </svg>
            )}
        </button>
    );
}

function InterviewSetup() {
    const navigate = useNavigate();

    const [form, setForm] = useState({
        role: "Software Developer",
        customRole: "",
        experience: "Fresher",
        interviewType: "Mixed",
        difficulty: "Medium",
        questionCount: 10,
        skills: [],
    });

    const [skillInput, setSkillInput] = useState("");
    const [resume, setResume] = useState(null);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");

    const updateField = (field, value) => {
        setForm((previous) => ({
            ...previous,
            [field]: value,
        }));
        setError("");
        setNotice("");
    };

    const addSkill = () => {
        const skill = skillInput.trim();

        if (!skill) {
            setNotice("Enter a skill first.");
            return;
        }

        if (
            form.skills.some(
                (item) => item.toLowerCase() === skill.toLowerCase()
            )
        ) {
            setNotice("That skill is already added.");
            return;
        }

        setForm((previous) => ({
            ...previous,
            skills: [...previous.skills, skill],
        }));

        setSkillInput("");
        setError("");
        setNotice(`${skill} added`);
    };

    const removeSkill = (skillToRemove) => {
        setForm((previous) => ({
            ...previous,
            skills: previous.skills.filter(
                (skill) => skill !== skillToRemove
            ),
        }));
        setNotice("");
    };

    const handleSkillKeyDown = (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addSkill();
        }
    };

    const handleResume = (event) => {
        const file = event.target.files?.[0];

        if (!file) return;

        if (!/\.(pdf|docx)$/i.test(file.name)) {
            setError("Choose a PDF or DOCX file.");
            event.target.value = "";
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            setError("Resume must be 5 MB or smaller.");
            event.target.value = "";
            return;
        }

        setResume(file);
        setError("");
        setNotice("Resume selected successfully.");
    };

    const removeResume = () => {
        setResume(null);
        setNotice("");
        const input = document.getElementById("resume-upload");
        if (input) input.value = "";
    };

    const handleContinue = (event) => {
        event.preventDefault();

        if (form.role === "Other" && !form.customRole.trim()) {
            setError("Enter your target job role.");
            return;
        }

        const setup = {
            ...form,
            role:
                form.role === "Other"
                    ? form.customRole.trim()
                    : form.role,
            resumeName: resume?.name || null,
        };

        try {
            sessionStorage.setItem(
                "nexhire_interview_setup",
                JSON.stringify(setup)
            );
        } catch {
            setError("Could not save setup in this browser.");
            return;
        }

        navigate("/interview/device-check");
    };

    const completion = Math.round(
        (
            [
                Boolean(
                    form.role === "Other"
                        ? form.customRole.trim()
                        : form.role
                ),
                Boolean(form.experience),
                Boolean(form.interviewType),
                Boolean(form.difficulty),
                Boolean(form.questionCount),
            ].filter(Boolean).length /
            5
        ) * 100
    );

    const displayedRole =
        form.role === "Other"
            ? form.customRole.trim() || "Your custom role"
            : form.role;

    return (
        <main className="min-h-screen bg-[#080b12] text-[#e7ebf1]">
            {/* Navbar */}
            <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#0b1018]/95 backdrop-blur-md">
                <div className="mx-auto flex h-9 max-w-5xl items-center justify-between px-2.5 sm:px-3">
                    <button
                        type="button"
                        onClick={() => navigate("/dashboard")}
                        className="flex items-center gap-1.5"
                    >
                        <span className="flex h-5 w-5 items-center justify-center rounded border border-[#00b88a]/25 bg-[#0b2520] text-[8px] font-bold text-[#00b88a]">
                            NH
                        </span>
                        <span className="text-[9px] font-semibold tracking-tight">
                            NexHire
                        </span>
                    </button>

                    <button
                        type="button"
                        onClick={() => navigate("/dashboard")}
                        className="flex items-center gap-1 text-[8px] text-[#8491a3] transition hover:text-[#00c99a]"
                    >
                        <span aria-hidden="true">←</span>
                        Dashboard
                    </button>
                </div>
            </header>

            <div className="mx-auto w-full max-w-4xl px-2.5 py-3 sm:px-3">
                {/* Heading */}
                <div className="mb-3">
                    <p className="mb-1 text-[7px] font-medium uppercase tracking-[0.13em] text-[#00b88a]">
                        INTERVIEW CONFIGURATION
                    </p>

                    <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
                        <div>
                            <h1 className="text-[13px] font-semibold tracking-tight text-[#f0f3f8]">
                                Build your interview.
                            </h1>
                            <p className="mt-0.5 text-[8px] leading-3 text-[#8290a3]">
                                Personalize your session, one step at a time.
                            </p>
                        </div>

                        <div className="w-full sm:w-32">
                            <div className="mb-1 flex items-center justify-between text-[7px]">
                                <span className="text-[#7c8a9d]">
                                    Setup progress
                                </span>
                                <span className="text-[#43dcb3]">
                                    {completion}%
                                </span>
                            </div>

                            <div
                                className="h-1 overflow-hidden rounded-full bg-[#202b38]"
                                role="progressbar"
                                aria-valuenow={completion}
                                aria-valuemin={0}
                                aria-valuemax={100}
                            >
                                <div
                                    className="h-full rounded-full bg-gradient-to-r from-[#008e70] to-[#36e0b1] transition-all duration-300"
                                    style={{ width: `${completion}%` }}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 items-start gap-2 lg:grid-cols-[minmax(0,1fr)_180px]">
                    {/* Setup form */}
                    <form onSubmit={handleContinue} className="space-y-1.5">
                        <SetupSection
                            number="01"
                            title="Target role"
                            description="Choose your position and experience."
                        >
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                <div>
                                    <FieldLabel>Job role / domain</FieldLabel>
                                    <select
                                        value={form.role}
                                        onChange={(event) =>
                                            updateField("role", event.target.value)
                                        }
                                        className={inputClass}
                                    >
                                        {roles.map((role) => (
                                            <option key={role} value={role}>
                                                {role}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                <div>
                                    <FieldLabel>Experience level</FieldLabel>
                                    <select
                                        value={form.experience}
                                        onChange={(event) =>
                                            updateField(
                                                "experience",
                                                event.target.value
                                            )
                                        }
                                        className={inputClass}
                                    >
                                        {experienceLevels.map((level) => (
                                            <option key={level} value={level}>
                                                {level}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            {form.role === "Other" && (
                                <div className="mt-2">
                                    <FieldLabel>Target job role</FieldLabel>
                                    <input
                                        value={form.customRole}
                                        onChange={(event) =>
                                            updateField(
                                                "customRole",
                                                event.target.value
                                            )
                                        }
                                        placeholder="e.g. Product Manager"
                                        className={inputClass}
                                        maxLength={80}
                                    />
                                </div>
                            )}
                        </SetupSection>

                        <SetupSection
                            number="02"
                            title="Interview preferences"
                            description="Choose the style and difficulty."
                        >
                            <FieldLabel>Interview type</FieldLabel>
                            <div className="mb-1.5 grid grid-cols-3 gap-1">
                                {interviewTypes.map((type) => (
                                    <ChoiceButton
                                        key={type.value}
                                        selected={form.interviewType === type.value}
                                        onClick={() =>
                                            updateField("interviewType", type.value)
                                        }
                                        className="flex-col gap-0 py-1"
                                    >
                                        <span className="text-[10px] leading-none">
                                            {type.icon}
                                        </span>

                                        <span className="text-[9px] leading-tight">
                                            {type.value}
                                        </span>

                                        <span className="text-[6px] leading-tight opacity-70">
                                            {type.description}
                                        </span>
                                    </ChoiceButton>
                                ))}
                            </div>


                            <FieldLabel>Difficulty level</FieldLabel>
                            <div className="mb-2 grid grid-cols-3 gap-1">
                                {difficulties.map((item) => (
                                    <ChoiceButton
                                        key={item.value}
                                        selected={form.difficulty === item.value}
                                        onClick={() =>
                                            updateField("difficulty", item.value)
                                        }
                                        className="flex-col gap-0.5 py-1.5"
                                    >
                                        <span>{item.value}</span>
                                        <span className="text-[7px] opacity-70">
                                            {item.description}
                                        </span>
                                    </ChoiceButton>
                                ))}
                            </div>

                            <FieldLabel>Number of questions</FieldLabel>
                            <div className="grid grid-cols-4 gap-1">
                                {questionCounts.map((count) => (
                                    <ChoiceButton
                                        key={count}
                                        selected={form.questionCount === count}
                                        onClick={() =>
                                            updateField("questionCount", count)
                                        }
                                    >
                                        {count}
                                    </ChoiceButton>
                                ))}
                            </div>
                        </SetupSection>

                        <SetupSection
                            number="03"
                            title="Skills to focus on"
                            description="Add topics you want to practice."
                        >
                            <div className="flex gap-1">
                                <input
                                    value={skillInput}
                                    onChange={(event) =>
                                        setSkillInput(event.target.value)
                                    }
                                    onKeyDown={handleSkillKeyDown}
                                    placeholder="e.g. React, SQL, DSA"
                                    className={`${inputClass} min-w-0 flex-1`}
                                    maxLength={40}
                                    aria-label="Enter a skill"
                                />

                                <button
                                    type="button"
                                    onClick={addSkill}
                                    className="h-[27px] rounded border border-[#00b88a]/30 px-2 text-[8px] text-[#00c99a] transition hover:bg-[#103128] active:scale-95"
                                >
                                    + Add
                                </button>
                            </div>

                            {form.skills.length > 0 && (
                                <div className="mt-1.5 flex flex-wrap gap-1">
                                    {form.skills.map((skill) => (
                                        <span
                                            key={skill}
                                            className="inline-flex items-center gap-1 rounded border border-[#1d5749] bg-[#10241f] px-1.5 py-0.5 text-[8px] text-[#8fe7ce] transition-colors hover:border-[#00b88a]/50"
                                        >
                                            {skill}
                                            <button
                                                type="button"
                                                onClick={() => removeSkill(skill)}
                                                aria-label={`Remove ${skill}`}
                                                className="ml-0.5 text-[#8fe7ce] transition hover:text-white"
                                            >
                                                ×
                                            </button>
                                        </span>
                                    ))}
                                </div>
                            )}

                            {form.skills.length === 0 && (
                                <p className="mt-1 text-[7px] text-[#697b8d]">
                                    Optional · Added skills appear here.
                                </p>
                            )}

                            {notice && (
                                <p
                                    aria-live="polite"
                                    className="mt-1 text-[7px] text-[#43dcb3]"
                                >
                                    {notice}
                                </p>
                            )}
                        </SetupSection>

                        <SetupSection
                            number="04"
                            title="Resume context"
                            description="Optional · Personalize questions with your experience."
                        >
                            <label
                                htmlFor="resume-upload"
                                className="flex cursor-pointer items-center gap-2 rounded border border-dashed border-white/[0.12] bg-[#080e16] px-2 py-1.5 transition duration-200 hover:border-[#00b88a]/60 hover:bg-[#0c171b]"
                            >
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[#102b24] text-[#00c99a]">
                                    <svg
                                        viewBox="0 0 24 24"
                                        className="h-3 w-3"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.6"
                                    >
                                        <path d="M12 16V4m-4 4 4-4 4 4" />
                                        <path d="M5 14v5h14v-5" />
                                    </svg>
                                </span>

                                <span className="min-w-0 flex-1">
                                    <span className="block truncate text-[8px] font-medium text-[#dce4ee]">
                                        {resume ? resume.name : "Upload your resume"}
                                    </span>
                                    <span className="mt-0.5 block text-[7px] text-[#718095]">
                                        {resume
                                            ? `${(resume.size / 1024).toFixed(0)} KB · Selected`
                                            : "PDF or DOCX · Max 5 MB"}
                                    </span>
                                </span>

                                <span className="text-[8px] text-[#00c99a]">
                                    {resume ? "Change" : "Browse"}
                                </span>

                                <input
                                    id="resume-upload"
                                    type="file"
                                    accept=".pdf,.docx"
                                    onChange={handleResume}
                                    className="sr-only"
                                />
                            </label>

                            {resume && (
                                <button
                                    type="button"
                                    onClick={removeResume}
                                    className="mt-1 text-[7px] text-[#e18a8a] hover:text-red-300"
                                >
                                    Remove resume
                                </button>
                            )}
                        </SetupSection>

                        {error && (
                            <p
                                role="alert"
                                className="rounded border border-red-500/20 bg-red-500/[0.06] px-2 py-1.5 text-[8px] text-red-300"
                            >
                                {error}
                            </p>
                        )}

                        <div className="flex flex-col-reverse gap-1.5 border-t border-white/[0.07] pt-2 sm:flex-row sm:items-center sm:justify-between">
                            <p className="text-[7px] text-[#748196]">
                                Next: Camera & microphone check
                            </p>

                            <div className="flex items-center justify-end gap-1">
                                <button
                                    type="button"
                                    onClick={() => navigate("/dashboard")}
                                    className="h-6 rounded border border-white/[0.09] px-2 text-[8px] text-[#a2adbd] transition hover:bg-white/[0.04]"
                                >
                                    Cancel
                                </button>

                                <button
                                    type="submit"
                                    className="flex h-6 items-center gap-1 rounded bg-gradient-to-r from-[#00b88a] to-[#13cba0] px-2.5 text-[8px] font-semibold text-[#04140f] transition hover:brightness-110 active:scale-[0.98]"
                                >
                                    Continue
                                    <span aria-hidden="true">→</span>
                                </button>
                            </div>
                        </div>
                    </form>

                    {/* Live preview */}
                    <aside className="space-y-1.5 lg:sticky lg:top-12">
                        <div className="overflow-hidden rounded-md border border-[#1a5143] bg-[#0b1718]">
                            <div className="border-b border-white/[0.06] bg-gradient-to-r from-[#103128] to-[#101923] p-2">
                                <div className="mb-1 flex items-center gap-1.5">
                                    <span className="flex h-4 w-4 items-center justify-center rounded bg-[#00b88a]/15 text-[9px] text-[#40dfb3]">
                                        ✳
                                    </span>
                                    <span className="text-[9px] font-semibold text-[#e8f2ef]">
                                        Live preview
                                    </span>
                                </div>
                                <p className="text-[7px] leading-3 text-[#91a79f]">
                                    Updates with your selections.
                                </p>
                            </div>

                            <div className="space-y-2 p-2">
                                <div>
                                    <p className="mb-1 text-[7px] uppercase tracking-wide text-[#708b82]">
                                        Target role
                                    </p>
                                    <p className="break-words text-[9px] font-medium text-[#e5f1ed]">
                                        {displayedRole}
                                    </p>
                                    <p className="mt-0.5 text-[7px] text-[#8ba196]">
                                        {form.experience}
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-1">
                                    <div className="rounded border border-white/[0.06] bg-[#0a1118] p-1.5">
                                        <p className="mb-1 text-[7px] text-[#7e9089]">
                                            FORMAT
                                        </p>
                                        <p className="text-[8px] text-[#d8e5e0]">
                                            {form.interviewType}
                                        </p>
                                    </div>
                                    <div className="rounded border border-white/[0.06] bg-[#0a1118] p-1.5">
                                        <p className="mb-1 text-[7px] text-[#7e9089]">
                                            DIFFICULTY
                                        </p>
                                        <p className="text-[8px] text-[#d8e5e0]">
                                            {form.difficulty}
                                        </p>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between border-t border-white/[0.07] pt-1.5">
                                    <span className="text-[8px] text-[#8ba196]">
                                        Questions
                                    </span>
                                    <span className="text-[9px] font-semibold text-[#43dfb5]">
                                        {form.questionCount}
                                    </span>
                                </div>

                                <div className="border-t border-white/[0.07] pt-1.5">
                                    <p className="mb-1 text-[7px] uppercase tracking-wide text-[#708b82]">
                                        Focus skills
                                    </p>

                                    {form.skills.length > 0 ? (
                                        <div className="flex flex-wrap gap-1">
                                            {form.skills.map((skill) => (
                                                <span
                                                    key={skill}
                                                    className="rounded bg-[#12352b] px-1 py-0.5 text-[7px] text-[#82e6c9]"
                                                >
                                                    {skill}
                                                </span>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-[7px] text-[#697b75]">
                                            No skills added
                                        </p>
                                    )}
                                </div>

                                <div className="flex items-center gap-1.5 border-t border-white/[0.07] pt-1.5">
                                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[#19233a] text-[#b6a7ff]">
                                        <svg
                                            viewBox="0 0 24 24"
                                            className="h-3 w-3"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="1.5"
                                        >
                                            <path d="M7 3h7l5 5v13H7z" />
                                            <path d="M14 3v5h5M10 13h6M10 16h6" />
                                        </svg>
                                    </span>
                                    <div className="min-w-0">
                                        <p className="text-[8px] text-[#cbd7e3]">
                                            Resume
                                        </p>
                                        <p className="truncate text-[7px] text-[#819187]">
                                            {resume ? resume.name : "Not attached"}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="rounded-md border border-white/[0.07] bg-[#0b121b] p-2">
                            <div className="mb-1 flex items-center gap-1">
                                <svg
                                    viewBox="0 0 24 24"
                                    className="h-3 w-3 text-[#00c99a]"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.6"
                                >
                                    <path d="M12 3 14.5 9.5 21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />
                                </svg>
                                <p className="text-[8px] font-medium text-[#dce5ed]">
                                    Quick tip
                                </p>
                            </div>
                            <p className="text-[7px] leading-3 text-[#7f8da0]">
                                Add skills relevant to your role to personalize
                                your practice session.
                            </p>
                        </div>
                    </aside>
                </div>
            </div>
        </main>
    );
}

export default InterviewSetup;
