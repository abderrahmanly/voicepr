import { Link, NavLink, Route, Routes } from "react-router-dom";
import Appointments from "./pages/Appointments";
import Calls from "./pages/Calls";

export default function App() {
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
