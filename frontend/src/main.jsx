import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { AppStateProvider } from "./state.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppStateProvider>
      <App />
    </AppStateProvider>
  </React.StrictMode>
);
