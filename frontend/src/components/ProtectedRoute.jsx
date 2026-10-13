
import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

const API_BASE_URL = "http://127.0.0.1:8000";

function ProtectedRoute() {
    const location = useLocation();
    const [status, setStatus] = useState("checking");

    useEffect(() => {
        let cancelled = false;

        async function verifySession() {
            const token = localStorage.getItem("nexhire_token");

            if (!token) {
                if (!cancelled) setStatus("unauthenticated");
                return;
            }

            try {
                const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
                    method: "GET",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                    cache: "no-store",
                });

                if (!response.ok) {
                    localStorage.removeItem("nexhire_token");
                    localStorage.removeItem("nexhire_user");

                    if (!cancelled) setStatus("unauthenticated");
                    return;
                }

                if (!cancelled) setStatus("authenticated");
            } catch (error) {
                // Do not treat a network failure as a successful session.
                if (!cancelled) setStatus("error");
            }
        }

        verifySession();

        return () => {
            cancelled = true;
        };
    }, [location.pathname]);

    if (status === "checking") {
        return (
            <div className="min-h-screen bg-[#080B12] text-white flex items-center justify-center">
                <p className="text-gray-400">Verifying your session...</p>
            </div>
        );
    }

    if (status === "unauthenticated") {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }

    if (status === "error") {
        return (
            <div className="min-h-screen bg-[#080B12] text-white flex flex-col items-center justify-center gap-4">
                <p className="text-gray-300">
                    Unable to verify your session. Please check your connection.
                </p>
                <button
                    onClick={() => window.location.reload()}
                    className="rounded-lg bg-cyan-500 px-5 py-2 font-semibold text-black"
                >
                    Retry
                </button>
                <button
                    onClick={() => {
                        localStorage.removeItem("nexhire_token");
                        localStorage.removeItem("nexhire_user");
                        window.location.replace("/login");
                    }}
                    className="text-sm text-gray-400 hover:text-white"
                >
                    Log out
                </button>
            </div>
        );
    }

    return <Outlet />;
}

export default ProtectedRoute;
