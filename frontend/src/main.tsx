import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";
import { SessionProvider } from "./store/session";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SessionProvider>
      <App />
    </SessionProvider>
  </React.StrictMode>
);
