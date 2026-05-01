/**
 * Navbar Component
 * ================
 * Reusable top navigation bar — extracted from App.jsx so it can be
 * imported independently if the app is split into multiple pages.
 *
 * Props:
 *   health      {string}  - "online" | "error" | "checking"
 *   lastUpdated {number}  - seconds since last successful poll
 */

import React from "react";

export default function Navbar({ health = "checking", lastUpdated = 0 }) {
  const healthLabel = {
    online:   "Systems nominal",
    error:    "Backend unreachable",
    checking: "Checking…",
  }[health] ?? "Checking…";

  const healthClass = {
    online:   "health-online",
    error:    "health-error",
    checking: "health-checking",
  }[health] ?? "health-checking";

  return (
    <header className="app-header">
      <div className="header-left">
        {/* Logo / brand */}
        <div className="logo">
          <span className="logo-pulse" />
          IMS
        </div>

        {/* Title block */}
        <div>
          <div className="app-title">Incident Management System</div>
          <div className="app-sub">SRE Operations · Real-time Monitoring</div>
        </div>
      </div>

      <div className="header-right">
        {/* Health pill */}
        <div className={`health-pill ${healthClass}`}>
          <span className="health-dot" />
          {healthLabel}
        </div>

        {/* Last refresh */}
        <span className="refresh-info">
          Updated {lastUpdated}s ago
        </span>
      </div>
    </header>
  );
}
