import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

// When the app is bundled into the backend image at /dashboard,
// VITE_BASE_PATH is set at build time. In dev it stays "/".
const basename = (import.meta.env.BASE_URL || "/").replace(/\/$/, "") || "/";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
