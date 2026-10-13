import Navbar from "../components/Navbar";
import MovingBar from "../components/MovingBar";
import Hero from "../components/Hero";
import Interviews from "../components/Interviews";
import Features from "../components/Features"
import Footer from "../components/Footer"

function LandingPage() {
    return (
        <main className="min-h-screen bg-[#020712]">
            <Navbar />
            <MovingBar />
            <Hero />
            <Interviews />
            <Features />
            <Footer />

            {/* Hero section will be added here */}
        </main>
    );
}

export default LandingPage;