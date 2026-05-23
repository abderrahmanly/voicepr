import { useEffect } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import Appointments from "./pages/Appointments";
import Calls from "./pages/Calls";
import TalkButton from "./TalkButton";
import { API_BASE } from "./api";

export default function App() {
  // Wake the HF Space (which may be sleeping) the moment the dashboard loads,
  // so the first voice call doesn't wait 30 s for a cold start.
  useEffect(() => {
    fetch(`${API_BASE}/health`).catch(() => {});
  }, []);

  return (
    <div className="app">
      <header>
        <Link to="/" className="brand">
          <span className="dot" /> Comune di Codroipo · Voicebot
        </Link>
        <nav>
          <NavLink to="/" end>
            Appuntamenti
          </NavLink>
          <NavLink to="/calls">Chiamate</NavLink>
        </nav>
        <TalkButton />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Appointments />} />
          <Route path="/calls" element={<Calls />} />
        </Routes>
      </main>
      <footer>
        <small>Prototipo tecnico — Customer Analytics Italia</small>
      </footer>
    </div>
  );
}
