import DashboardNavbar from "../components/Dashboard/DashboardNavbar";
import WelcomeSection from "../components/Dashboard/WelcomeSection";
import StatsCards from "../components/Dashboard/StatsCards";
import RecentInterviews from "../components/Dashboard/RecentInterviews";

function Dashboard() {
    return (
        <main className="min-h-screen bg-[#080b12] text-[#f5f7fa]">
            <DashboardNavbar />

            <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6">
                <WelcomeSection />

                {/* StatsCards and RecentInterviews will go here */}
                <StatsCards />
                <RecentInterviews />

            </div>
        </main>
    );
}

export default Dashboard;