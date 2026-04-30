import { useEffect, useState, useCallback, useRef } from "react";
import API from "./api/api";
import "./App.css";

// ── Constants ─────────────────────────────────────────────────────────────────
const SEVERITY_RANK = { P0: 1, P1: 2, P2: 3, P3: 4 };
const SEVERITY_META = {
  P0: { label: "P0", cls: "sev-p0", desc: "CRITICAL" },
  P1: { label: "P1", cls: "sev-p1", desc: "HIGH"     },
  P2: { label: "P2", cls: "sev-p2", desc: "MEDIUM"   },
  P3: { label: "P3", cls: "sev-p3", desc: "LOW"      },
};
const STATUS_META = {
  OPEN:          { cls: "stat-open",          icon: "◉" },
  INVESTIGATING: { cls: "stat-investigating",  icon: "◎" },
  RESOLVED:      { cls: "stat-resolved",       icon: "◈" },
  CLOSED:        { cls: "stat-closed",         icon: "◆" },
};
const NEXT_STATES = {
  OPEN:          ["INVESTIGATING"],
  INVESTIGATING: ["RESOLVED"],
  RESOLVED:      ["CLOSED"],
  CLOSED:        [],
};
const ROOT_CAUSE_OPTIONS = [
  "INFRASTRUCTURE","APPLICATION","NETWORK","HUMAN_ERROR","THIRD_PARTY","UNKNOWN",
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function relativeTime(ts) {
  const diff = Math.floor((Date.now() - new Date(ts)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function useInterval(fn, ms) {
  const ref = useRef(fn);
  useEffect(() => { ref.current = fn; }, [fn]);
  useEffect(() => { const id = setInterval(() => ref.current(), ms); return () => clearInterval(id); }, [ms]);
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [incidents,        setIncidents]        = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [loading,          setLoading]          = useState(true);
  const [lastRefresh,      setLastRefresh]      = useState(null);
  const [health,           setHealth]           = useState("checking");
  const [toast,            setToast]            = useState(null);

  const notify = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchIncidents = useCallback(async () => {
    try {
      const res  = await API.get("/incidents/");
      const list = res.data.incidents ?? res.data ?? [];
      setIncidents(list);
      setLastRefresh(new Date());
      setLoading(false);
      setHealth("online");
    } catch {
      setHealth("error");
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id) => {
    try {
      const res = await API.get(`/incidents/${id}`);
      setSelectedIncident(res.data);
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to load incident", "error");
    }
  }, []);

  useInterval(fetchIncidents, 5000);
  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  const sorted = [...incidents].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
  );

  const stats = {
    total:    incidents.length,
    p0:       incidents.filter(i => i.severity === "P0").length,
    open:     incidents.filter(i => i.status === "OPEN").length,
    resolved: incidents.filter(i => ["RESOLVED","CLOSED"].includes(i.status)).length,
  };

  return (
    <div className="app">
      {toast && <div className={`toast toast-${toast.type}`}>{toast.type === "success" ? "✓" : "✕"} {toast.msg}</div>}

      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo"><span className="logo-pulse" />IMS</div>
          <div>
            <h1 className="app-title">Incident Management System</h1>
            <p className="app-sub">SRE Operations · Real-time Monitoring</p>
          </div>
        </div>
        <div className="header-right">
          <div className={`health-pill health-${health}`}>
            <span className="health-dot" />
            {health === "online" ? "Systems nominal" : health === "error" ? "Backend unreachable" : "Checking…"}
          </div>
          <div className="refresh-info">
            {lastRefresh ? `Updated ${relativeTime(lastRefresh)}` : "Loading…"}
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="stats-bar">
        {[
          { label: "Total Incidents", value: stats.total,    cls: "sn"  },
          { label: "P0 Critical",     value: stats.p0,       cls: "sc"  },
          { label: "Active",          value: stats.open,     cls: "sa"  },
          { label: "Resolved",        value: stats.resolved, cls: "sr"  },
        ].map(s => (
          <div key={s.label} className={`stat-card ${s.cls}`}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Layout */}
      <div className="layout">
        <aside className="panel panel-left">
          <div className="panel-header">
            <span className="panel-title">Live Feed</span>
            <span className="live-badge"><span className="live-dot" /> LIVE</span>
          </div>
          {loading ? (
            <div className="empty-state"><div className="spinner" /><p>Connecting…</p></div>
          ) : sorted.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">✓</div>
              <p>No active incidents</p>
              <span>All systems operational</span>
            </div>
          ) : (
            <div className="incident-list">
              {sorted.map(inc => (
                <IncidentCard
                  key={inc.incident_id}
                  incident={inc}
                  selected={selectedIncident?.incident_id === inc.incident_id}
                  onClick={() => fetchDetail(inc.incident_id)}
                />
              ))}
            </div>
          )}
        </aside>

        <section className="panel panel-right">
          {!selectedIncident ? (
            <div className="empty-state empty-state-large">
              <div className="empty-icon">⌖</div>
              <p>Select an incident to investigate</p>
              <span>Click any incident from the live feed</span>
            </div>
          ) : (
            <IncidentDetail
              incident={selectedIncident}
              onRefresh={() => fetchDetail(selectedIncident.incident_id)}
              onListRefresh={fetchIncidents}
              notify={notify}
            />
          )}
        </section>
      </div>
    </div>
  );
}

// ── Incident Card ─────────────────────────────────────────────────────────────
function IncidentCard({ incident, selected, onClick }) {
  const sev = SEVERITY_META[incident.severity] || SEVERITY_META.P3;
  const sta = STATUS_META[incident.status]     || STATUS_META.OPEN;
  return (
    <div className={`incident-card ${sev.cls} ${selected ? "incident-card--active" : ""}`} onClick={onClick}>
      <div className="ic-top">
        <span className={`sev-chip sev-chip--${sev.cls}`}>{sev.label}</span>
        <span className={`status-chip ${sta.cls}`}>{sta.icon} {incident.status}</span>
      </div>
      <div className="ic-component">{incident.component_id}</div>
      <div className="ic-meta">
        <span>⚡ {incident.signal_count} signals</span>
        {incident.created_at && <span>🕐 {relativeTime(incident.created_at)}</span>}
      </div>
    </div>
  );
}

// ── Incident Detail ───────────────────────────────────────────────────────────
function IncidentDetail({ incident, onRefresh, onListRefresh, notify }) {
  const [signals,      setSignals]      = useState([]);
  const [sigLoading,   setSigLoading]   = useState(true);
  const [tab,          setTab]          = useState("overview");
  const [transitioning, setTransitioning] = useState(false);
  const [rcaSubmitting, setRcaSubmitting] = useState(false);
  const [rca, setRca] = useState({
    incident_start:      "",
    incident_end:        "",
    root_cause_category: "INFRASTRUCTURE",
    root_cause_detail:   "",
    fix_applied:         "",
    prevention_steps:    "",
  });

  const sev       = SEVERITY_META[incident.severity] || SEVERITY_META.P3;
  const sta       = STATUS_META[incident.status]     || STATUS_META.OPEN;
  const nextStates = NEXT_STATES[incident.status]   || [];
  const hasRCA    = !!incident.rca;

  useEffect(() => {
    setSigLoading(true);
    API.get(`/incidents/${incident.incident_id}`)
      .then(r => setSignals(r.data.raw_signals || []))
      .catch(() => setSignals([]))
      .finally(() => setSigLoading(false));
  }, [incident.incident_id]);

  const handleTransition = async (newStatus) => {
    if (newStatus === "CLOSED" && !hasRCA) {
      notify("Submit RCA before closing the incident", "error");
      setTab("rca"); return;
    }
    setTransitioning(true);
    try {
      await API.patch(`/incidents/${incident.incident_id}/status`, { status: newStatus });
      notify(`Status → ${newStatus}`);
      onRefresh(); onListRefresh();
    } catch (e) {
      notify(e.response?.data?.detail || "Transition failed", "error");
    } finally { setTransitioning(false); }
  };

  const handleRCA = async () => {
    if (!rca.incident_start || !rca.incident_end)      { notify("Start and end times required", "error"); return; }
    if (rca.root_cause_detail.length < 20)              { notify("Root cause detail: min 20 chars", "error"); return; }
    if (rca.fix_applied.length < 10)                   { notify("Fix applied: min 10 chars", "error"); return; }
    if (rca.prevention_steps.length < 10)              { notify("Prevention steps: min 10 chars", "error"); return; }
    setRcaSubmitting(true);
    try {
      await API.post(`/rca/${incident.incident_id}`, rca);
      notify("RCA submitted — you can now close the incident");
      onRefresh();
    } catch (e) {
      notify(e.response?.data?.detail || "RCA failed", "error");
    } finally { setRcaSubmitting(false); }
  };

  const mttr = incident.mttr_seconds
    ? incident.mttr_seconds >= 60 ? `${Math.round(incident.mttr_seconds / 60)} min` : `${incident.mttr_seconds}s`
    : null;

  return (
    <div className="detail-root">
      {/* Header band */}
      <div className={`detail-band detail-band--${sev.cls}`}>
        <div>
          <div className="detail-sev">{sev.label} · {sev.desc}</div>
          <div className="detail-component">{incident.component_id}</div>
          <div className="detail-id">#{incident.incident_id?.slice(0,8)}…</div>
        </div>
        <div className={`detail-status-pill ${sta.cls}`}>{sta.icon} {incident.status}</div>
      </div>

      {/* Metrics */}
      <div className="metrics-row">
        {[
          { label: "Signals",    value: incident.signal_count             },
          { label: "Type",       value: incident.component_type || "—"    },
          { label: "MTTR",       value: mttr || "Active",   hi: !!mttr   },
          { label: "RCA",        value: hasRCA ? "✓ Done" : "Pending", hi: hasRCA },
        ].map(m => (
          <div key={m.label} className={`metric-cell ${m.hi ? "metric-cell--hi" : ""}`}>
            <div className="metric-val">{m.value}</div>
            <div className="metric-lbl">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="actions-row">
        <span className="actions-label">Transition:</span>
        {nextStates.length === 0 ? (
          <span className="actions-closed">Incident closed</span>
        ) : nextStates.map(ns => (
          <button
            key={ns}
            className={`btn-tx ${ns === "CLOSED" && !hasRCA ? "btn-tx--blocked" : "btn-tx--active"}`}
            onClick={() => handleTransition(ns)}
            disabled={transitioning}
            title={ns === "CLOSED" && !hasRCA ? "Submit RCA first" : `→ ${ns}`}
          >
            {transitioning ? "…" : ns}{ns === "CLOSED" && !hasRCA && " 🔒"}
          </button>
        ))}
      </div>

      {/* Tabs */}
      <div className="tabs">
        {[
          { key: "overview", label: "Overview"                                          },
          { key: "signals",  label: `Signals (${signals.length})`                      },
          { key: "rca",      label: hasRCA ? "RCA ✓" : "Submit RCA"                   },
        ].map(t => (
          <button key={t.key} className={`tab-btn ${tab === t.key ? "tab-btn--on" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {tab === "overview" && (
        <div className="tab-body">
          <div className="ov-grid">
            <IC label="Incident ID"    value={incident.incident_id} mono />
            <IC label="Component"      value={incident.component_id} />
            <IC label="Type"           value={incident.component_type} />
            <IC label="Priority"       value={incident.severity} />
            <IC label="Status"         value={incident.status} />
            <IC label="Signal Count"   value={incident.signal_count} />
            <IC label="Started"        value={incident.created_at ? new Date(incident.created_at).toLocaleString() : "—"} />
            <IC label="MTTR"           value={mttr || "In progress…"} />
          </div>
          {hasRCA && (
            <div className="rca-summary-box">
              <div className="rca-summary-title">✓ Root Cause Analysis Submitted</div>
              <div className="ov-grid">
                <IC label="Category"   value={incident.rca.root_cause_category} />
                <IC label="MTTR"       value={`${incident.rca.mttr_minutes} min`} />
                <IC label="Root Cause" value={incident.rca.root_cause_detail}  full />
                <IC label="Fix"        value={incident.rca.fix_applied}        full />
                <IC label="Prevention" value={incident.rca.prevention_steps}   full />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Signals */}
      {tab === "signals" && (
        <div className="tab-body">
          {sigLoading ? (
            <div className="empty-state"><div className="spinner" /><p>Loading signals…</p></div>
          ) : signals.length === 0 ? (
            <div className="empty-state"><p>No raw signals</p></div>
          ) : (
            <div className="signals-list">
              {signals.map((sig, i) => <SignalCard key={sig.id || i} signal={sig} index={i} />)}
            </div>
          )}
        </div>
      )}

      {/* Tab: RCA */}
      {tab === "rca" && (
        <div className="tab-body">
          {hasRCA ? (
            <div className="rca-done">
              <div className="rca-done-icon">✓</div>
              <div className="rca-done-title">RCA Submitted</div>
              <div className="rca-done-sub">MTTR: {incident.rca.mttr_minutes} minutes · {incident.rca.root_cause_category}</div>
              <div className="ov-grid" style={{marginTop:"1.5rem"}}>
                <IC label="Root Cause" value={incident.rca.root_cause_detail} full />
                <IC label="Fix"        value={incident.rca.fix_applied}       full />
                <IC label="Prevention" value={incident.rca.prevention_steps}  full />
              </div>
            </div>
          ) : (
            <div className="rca-form">
              <div className="rca-notice">All fields mandatory. RCA required before closing.</div>

              <div className="form-row-2">
                <div className="form-group">
                  <label>Incident Start *</label>
                  <input type="datetime-local" value={rca.incident_start}
                    onChange={e => setRca(r => ({...r, incident_start: e.target.value}))} />
                </div>
                <div className="form-group">
                  <label>Incident End *</label>
                  <input type="datetime-local" value={rca.incident_end}
                    onChange={e => setRca(r => ({...r, incident_end: e.target.value}))} />
                </div>
              </div>

              <div className="form-group">
                <label>Root Cause Category *</label>
                <select value={rca.root_cause_category}
                  onChange={e => setRca(r => ({...r, root_cause_category: e.target.value}))}>
                  {ROOT_CAUSE_OPTIONS.map(o => <option key={o} value={o}>{o.replace("_"," ")}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label>Root Cause Detail * <span className="hint">(min 20 chars)</span></label>
                <textarea rows={3} placeholder="Describe the root cause…" value={rca.root_cause_detail}
                  onChange={e => setRca(r => ({...r, root_cause_detail: e.target.value}))} />
                <div className="char-hint" style={{color: rca.root_cause_detail.length >= 20 ? "#22c55e" : "#94a3b8"}}>
                  {rca.root_cause_detail.length} / 20 min
                </div>
              </div>

              <div className="form-group">
                <label>Fix Applied * <span className="hint">(min 10 chars)</span></label>
                <textarea rows={3} placeholder="What fix was applied?" value={rca.fix_applied}
                  onChange={e => setRca(r => ({...r, fix_applied: e.target.value}))} />
              </div>

              <div className="form-group">
                <label>Prevention Steps * <span className="hint">(min 10 chars)</span></label>
                <textarea rows={3} placeholder="How will this be prevented?" value={rca.prevention_steps}
                  onChange={e => setRca(r => ({...r, prevention_steps: e.target.value}))} />
              </div>

              <button className="btn-rca-submit" onClick={handleRCA} disabled={rcaSubmitting}>
                {rcaSubmitting ? "Submitting…" : "Submit RCA"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SignalCard({ signal, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="signal-card" onClick={() => setOpen(o => !o)}>
      <div className="signal-top">
        <span className="signal-idx">#{index + 1}</span>
        <span className="signal-code">{signal.error_code || signal.component_type || "SIGNAL"}</span>
        <span className="signal-msg">{signal.message}</span>
        <span className="signal-time">{signal.timestamp ? relativeTime(signal.timestamp) : ""}</span>
        <span className="signal-chevron">{open ? "▲" : "▼"}</span>
      </div>
      {open && <pre className="signal-raw">{JSON.stringify(signal, null, 2)}</pre>}
    </div>
  );
}

function IC({ label, value, mono, full }) {
  return (
    <div className={`ic ${full ? "ic--full" : ""}`}>
      <div className="ic-label">{label}</div>
      <div className={`ic-value ${mono ? "ic-value--mono" : ""}`}>{value ?? "—"}</div>
    </div>
  );
}