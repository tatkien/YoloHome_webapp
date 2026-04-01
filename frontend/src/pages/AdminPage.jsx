import { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  HouseFill, KeyFill, ClipboardData, PeopleFill, PersonFill,
  TrashFill, LightbulbFill, Clipboard, CheckCircleFill, XCircleFill,
  Activity, WifiOff,
} from "react-bootstrap-icons";
import AdminUserSection from "../components/AdminUserSection";

const COL = {
  num:    "48px",
  name:   "200px",
  middle: "200px",
  status: "110px",
  action: "130px",
};

const LOG_COL = {
  num:      "48px",
  device:   "120px",
  user:     "140px",
  payload:  "140px",
  status:   "100px",
  result:   "140px",
  time:     "170px",
};

// ── Status badge helper ──
const StatusBadge = ({ status }) => {
  const map = {
    pending:   { bg: "bg-warning-subtle",   text: "text-warning",   label: "Pending"   },
    delivered: { bg: "bg-info-subtle",      text: "text-info",      label: "Delivered" },
    acked:     { bg: "bg-success-subtle",   text: "text-success",   label: "Acked"     },
    failed:    { bg: "bg-danger-subtle",    text: "text-danger",    label: "Failed"    },
  };
  const s = map[status] ?? { bg: "bg-secondary-subtle", text: "text-secondary", label: status };
  return (
    <span className={`badge ${s.bg} ${s.text} d-inline-flex align-items-center gap-1`} style={{ fontSize: "0.72rem" }}>
      {s.label}
    </span>
  );
};

// ── Single device websocket hook ──
const useDeviceActivity = (deviceId, token) => {
  const [logs,      setLogs]      = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!deviceId) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url   = `${proto}://${window.location.host}/ws/devices/${deviceId}${token ? `?token=${token}` : ""}`;
    const ws    = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen  = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "device.activity.history") {
        setLogs(msg.items);
      } else if (msg.type === "device.activity.new") {
        setLogs((prev) => [msg.item, ...prev]);
      }
    };

    // keepalive ping every 30s
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 30000);

    return () => { clearInterval(ping); ws.close(); };
  }, [deviceId, token]);

  return { logs, connected };
};

const AdminPage = () => {
  const location = useLocation();

  // ── Key state ──
  const [keyInput,      setKeyInput]      = useState("");
  const [keyError,      setKeyError]      = useState("");
  const [keySuccess,    setKeySuccess]    = useState(false);
  const [keyLastUpdate, setKeyLastUpdate] = useState(null);
  const [keySaving,     setKeySaving]     = useState(false);

  // ── Users state ──
  const [users,        setUsers]        = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError,   setUsersError]   = useState("");

  // ── Devices state ──
  const [devices, setDevices] = useState([
    { id: 1, name: "Living Room Light", type: "Light",  online: true  },
    { id: 2, name: "Front Door Lock",   type: "Lock",   online: true  },
    { id: 3, name: "Garage Sensor",     type: "Sensor", online: false },
  ]);

  // ── Activity log state ──
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);
  const [allLogs,          setAllLogs]          = useState([]);  // merged logs from all WS
  const wsRefs   = useRef({});   // { deviceId: WebSocket }
  const connRefs = useRef({});   // { deviceId: boolean }
  const [wsStatus, setWsStatus] = useState({});  // { deviceId: bool }

  const token = localStorage.getItem("token") || null;

  const menuItems = [
    { label: "Về trang chủ", icon: <HouseFill size={16} />,    path: "/"      },
    { label: "Dashboard",    icon: <ClipboardData size={16} />, path: "/admin" },
  ];

  // ── Fetch users ──
  useEffect(() => {
    const fetchUsers = async () => {
      setUsersLoading(true);
      setUsersError("");
      try {
        const res  = await fetch("/admin/users/", { credentials: "include" });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        setUsers(await res.json());
      } catch (err) {
        setUsersError("Không thể tải danh sách người dùng.");
      } finally {
        setUsersLoading(false);
      }
    };
    fetchUsers();
  }, []);

  // ── Open a WebSocket for every device ──
  useEffect(() => {
    devices.forEach(({ id }) => {
      if (wsRefs.current[id]) return;   // already open
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const url   = `${proto}://${window.location.host}/ws/devices/${id}${token ? `?token=${token}` : ""}`;
      const ws    = new WebSocket(url);
      wsRefs.current[id] = ws;

      ws.onopen  = () => { connRefs.current[id] = true;  setWsStatus(s => ({ ...s, [id]: true  })); };
      ws.onclose = () => { connRefs.current[id] = false; setWsStatus(s => ({ ...s, [id]: false })); };
      ws.onerror = () => { connRefs.current[id] = false; setWsStatus(s => ({ ...s, [id]: false })); };

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "device.activity.history") {
          setAllLogs(prev => {
            const withoutThis = prev.filter(l => l.device_id !== id);
            return [...msg.items, ...withoutThis].sort(
              (a, b) => new Date(b.created_at) - new Date(a.created_at)
            );
          });
        } else if (msg.type === "device.activity.new") {
          setAllLogs(prev =>
            [msg.item, ...prev].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
          );
        }
      };

      // keepalive
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30000);

      ws._pingInterval = ping;
    });

    return () => {
      Object.values(wsRefs.current).forEach(ws => {
        clearInterval(ws._pingInterval);
        ws.close();
      });
      wsRefs.current = {};
    };
  }, [devices, token]);

  // ── filtered logs by selected device ──
  const visibleLogs = selectedDeviceId
    ? allLogs.filter(l => l.device_id === selectedDeviceId)
    : allLogs;

  // ── Key save ──
  const handleSaveKey = async () => {
    if (!keyInput.trim())           { setKeyError("Key không được để trống!");     return; }
    if (keyInput.trim().length < 6) { setKeyError("Key phải có ít nhất 6 ký tự!"); return; }
    setKeySaving(true);
    setKeyError("");
    try {
      const res  = await fetch("/admin/users/invitation-key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ invitation_key: keyInput.trim() }),
      });
      const data = await res.json();
      if (!res.ok) { setKeyError(data.detail || "Lỗi khi lưu key."); return; }
      setKeyInput("");
      setKeyLastUpdate(data.updated_at);
      setKeySuccess(true);
      setTimeout(() => setKeySuccess(false), 3000);
    } catch {
      setKeyError("Lỗi kết nối server.");
    } finally {
      setKeySaving(false);
    }
  };

  const handleToggleDevice = (id) =>
    setDevices(devices.map(d => d.id === id ? { ...d, online: !d.online } : d));
  const handleDeleteDevice = (id) =>
    setDevices(devices.filter(d => d.id !== id));

  return (
    <div className="d-flex" style={{ minHeight: "100vh", backgroundColor: "#f4f6f9" }}>

      {/* ── Sidebar ── */}
      <nav
        className="d-flex flex-column bg-white border-end shadow-sm"
        style={{ width: "230px", flexShrink: 0, position: "sticky", top: 0, height: "100vh", overflowY: "auto" }}
      >
        <div className="px-4 py-3 border-bottom d-flex align-items-center gap-2">
          <ClipboardData size={20} className="text-primary" />
          <span className="text-primary fs-5 fw-bold">MY ADMIN</span>
        </div>

        <div className="px-2 py-3 flex-grow-1">
          <p className="text-uppercase text-muted px-3 mb-2" style={{ fontSize: "0.68rem", letterSpacing: "0.09em" }}>Menu</p>
          <ul className="nav flex-column gap-1">
            {menuItems.map(item => (
              <li className="nav-item" key={item.path}>
                <Link
                  to={item.path}
                  className={`nav-link d-flex align-items-center gap-2 rounded px-3 py-2 ${
                    location.pathname === item.path ? "bg-primary text-white fw-semibold" : "text-secondary"
                  }`}
                  style={{ fontSize: "0.88rem" }}
                >
                  {item.icon} {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <AdminUserSection />
      </nav>

      {/* ── Main ── */}
      <div className="flex-grow-1 d-flex flex-column" style={{ minWidth: 0, overflowY: "auto" }}>

        {/* Top bar */}
        <div
          className="bg-white border-bottom px-4 py-3 d-flex align-items-center justify-content-between"
          style={{ position: "sticky", top: 0, zIndex: 100 }}
        >
          <div>
            <h5 className="mb-0 fw-bold">Dashboard</h5>
            <small className="text-muted">
              {new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </small>
          </div>
        </div>

        <div className="p-4">

          {/* Stat cards */}
          <div className="row g-3 mb-4">
            {[
              { label: "Tổng người dùng",  value: users.length,                            icon: <PeopleFill size={22} />,    color: "primary" },
              { label: "Đang hoạt động",   value: users.filter(u => u.is_active).length,   icon: <PersonFill size={22} />,    color: "success" },
              { label: "Thiết bị online",  value: devices.filter(d => d.online).length,    icon: <LightbulbFill size={22} />, color: "info"    },
              { label: "Activity logs",    value: allLogs.length,                           icon: <Activity size={22} />,  color: "warning" },
            ].map(stat => (
              <div className="col-6 col-xl-3" key={stat.label}>
                <div className="card border-0 shadow-sm">
                  <div className="card-body d-flex align-items-center gap-3 py-3">
                    <div
                      className={`bg-${stat.color}-subtle text-${stat.color} rounded-3 d-flex align-items-center justify-content-center flex-shrink-0`}
                      style={{ width: "50px", height: "50px" }}
                    >
                      {stat.icon}
                    </div>
                    <div>
                      <div className="fw-bold fs-4 lh-1 mb-1">{stat.value}</div>
                      <div className="text-muted small">{stat.label}</div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Invitation Key ── */}
          <div id="keys" className="row g-3 mb-4">
            <div className="col-12">
              <h6 className="fw-bold text-muted text-uppercase mb-0" style={{ fontSize: "0.75rem", letterSpacing: "0.08em" }}>
                🔑 Invitation Key
              </h6>
            </div>
            <div className="col-12 col-lg-5">
              <div className="card border-0 shadow-sm h-100">
                <div className="card-header bg-white border-bottom fw-semibold d-flex align-items-center gap-2 py-3">
                  <KeyFill size={15} className="text-primary" /> Cập nhật Invitation Key
                </div>
                <div className="card-body">
                  <p className="text-muted small mb-3">Đặt một key duy nhất để người dùng có thể đăng ký tài khoản.</p>
                  <div className="input-group">
                    <input
                      type="text"
                      className={`form-control form-control-sm ${keyError ? "is-invalid" : ""}`}
                      placeholder="Nhập key mới..."
                      value={keyInput}
                      onChange={e => { setKeyInput(e.target.value); setKeyError(""); }}
                      onKeyDown={e => e.key === "Enter" && handleSaveKey()}
                      disabled={keySaving}
                    />
                    <button className="btn btn-primary btn-sm" onClick={handleSaveKey} disabled={keySaving}>
                      {keySaving
                        ? <><span className="spinner-border spinner-border-sm me-1" /> Đang lưu...</>
                        : "Lưu Key"}
                    </button>
                    {keyError && <div className="invalid-feedback">{keyError}</div>}
                  </div>
                  {keySuccess && <div className="alert alert-success py-2 small mt-3 mb-0">✅ Key đã được cập nhật!</div>}
                  {keyLastUpdate && (
                    <p className="text-muted small mt-3 mb-0">
                      Cập nhật lần cuối: {new Date(keyLastUpdate).toLocaleString("vi-VN")}
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div className="col-12 col-lg-7">
              <div className="card border-0 shadow-sm h-100">
                <div className="card-header bg-white border-bottom fw-semibold d-flex align-items-center gap-2 py-3">
                  <Clipboard size={15} className="text-primary" /> Lưu ý
                </div>
                <div className="card-body">
                  <ul className="small text-muted mb-0" style={{ lineHeight: "2" }}>
                    <li>Chỉ có <strong>một key duy nhất</strong> tồn tại trong hệ thống.</li>
                    <li>Khi cập nhật, key cũ sẽ <strong>không còn hợp lệ</strong>.</li>
                    <li>Key phải có <strong>ít nhất 6 ký tự</strong>.</li>
                    <li>Key được lưu dưới dạng <strong>hash</strong> — bạn sẽ không thể xem lại key cũ.</li>
                    <li>Chỉ chia sẻ key với người dùng <strong>đáng tin cậy</strong>.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* ── User Management ── */}
          <div id="users" className="mb-4">
            <h6 className="fw-bold text-muted text-uppercase mb-3" style={{ fontSize: "0.75rem", letterSpacing: "0.08em" }}>
              👤 Quản lý người dùng
            </h6>
            <div className="card border-0 shadow-sm">
              <div className="card-body p-0">
                {usersLoading ? (
                  <div className="text-center py-5">
                    <span className="spinner-border spinner-border-sm text-primary me-2" />
                    <span className="text-muted small">Đang tải...</span>
                  </div>
                ) : usersError ? (
                  <div className="alert alert-danger m-3 small">{usersError}</div>
                ) : (
                  <table className="table table-hover align-middle mb-0" style={{ tableLayout: "fixed", width: "100%" }}>
                    <colgroup>
                      <col style={{ width: COL.num    }} />
                      <col style={{ width: COL.name   }} />
                      <col style={{ width: COL.middle }} />
                      <col style={{ width: COL.status }} />
                      <col style={{ width: COL.action }} />
                    </colgroup>
                    <thead className="table-light">
                      <tr>
                        <th className="px-3 py-3" style={{ fontSize: "0.78rem" }}>#</th>
                        <th style={{ fontSize: "0.78rem" }}>Username</th>
                        <th style={{ fontSize: "0.78rem" }}>Email</th>
                        <th style={{ fontSize: "0.78rem" }}>Trạng thái</th>
                        <th style={{ fontSize: "0.78rem" }}>Hành động</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user, idx) => (
                        <tr key={user.id}>
                          <td className="px-3 text-muted small">#{idx + 1}</td>
                          <td>
                            <div className="d-flex align-items-center gap-2">
                              <div
                                className="bg-primary-subtle text-primary rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
                                style={{ width: "30px", height: "30px", fontSize: "0.75rem" }}
                              >
                                {user.username[0].toUpperCase()}
                              </div>
                              <span className="small fw-semibold text-truncate">{user.username}</span>
                            </div>
                          </td>
                          <td className="small text-muted text-truncate">{user.email}</td>
                          <td>
                            {user.is_active ? (
                              <span className="badge bg-success-subtle text-success d-inline-flex align-items-center gap-1">
                                <CheckCircleFill size={10} /> Active
                              </span>
                            ) : (
                              <span className="badge bg-danger-subtle text-danger d-inline-flex align-items-center gap-1">
                                <XCircleFill size={10} /> Locked
                              </span>
                            )}
                          </td>
                          <td>
                            <div className="d-flex gap-2">
                              <button
                                className={`btn btn-sm ${user.is_active ? "btn-outline-warning" : "btn-outline-success"}`}
                                style={{ fontSize: "0.72rem", width: "72px" }}
                              >
                                {user.is_active ? "Khóa" : "Mở khóa"}
                              </button>
                              <button className="btn btn-sm btn-outline-danger" style={{ fontSize: "0.72rem" }}>
                                <TrashFill size={11} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* ── Device Management ── */}
          <div id="devices" className="mb-4">
            <h6 className="fw-bold text-muted text-uppercase mb-3" style={{ fontSize: "0.75rem", letterSpacing: "0.08em" }}>
              💡 Quản lý thiết bị
            </h6>
            <div className="card border-0 shadow-sm">
              <div className="card-body p-0">
                <table className="table table-hover align-middle mb-0" style={{ tableLayout: "fixed", width: "100%" }}>
                  <colgroup>
                    <col style={{ width: COL.num    }} />
                    <col style={{ width: COL.name   }} />
                    <col style={{ width: COL.middle }} />
                    <col style={{ width: COL.status }} />
                    <col style={{ width: COL.action }} />
                  </colgroup>
                  <thead className="table-light">
                    <tr>
                      <th className="px-3 py-3" style={{ fontSize: "0.78rem" }}>#</th>
                      <th style={{ fontSize: "0.78rem" }}>Tên thiết bị</th>
                      <th style={{ fontSize: "0.78rem" }}>Loại</th>
                      <th style={{ fontSize: "0.78rem" }}>Trạng thái</th>
                      <th style={{ fontSize: "0.78rem" }}>Hành động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((device, idx) => (
                      <tr key={device.id}>
                        <td className="px-3 text-muted small">#{idx + 1}</td>
                        <td>
                          <div className="d-flex align-items-center gap-2">
                            <div
                              className="bg-warning-subtle text-warning rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
                              style={{ width: "30px", height: "30px" }}
                            >
                              <LightbulbFill size={13} />
                            </div>
                            <span className="small fw-semibold text-truncate">{device.name}</span>
                          </div>
                        </td>
                        <td>
                          <span className="badge bg-light text-dark border" style={{ fontSize: "0.72rem" }}>{device.type}</span>
                        </td>
                        <td>
                          {device.online ? (
                            <span className="badge bg-success-subtle text-success d-inline-flex align-items-center gap-1">
                              <CheckCircleFill size={10} /> Online
                            </span>
                          ) : (
                            <span className="badge bg-secondary-subtle text-secondary d-inline-flex align-items-center gap-1">
                              <XCircleFill size={10} /> Offline
                            </span>
                          )}
                        </td>
                        <td>
                          <div className="d-flex gap-2">
                            <button
                              className={`btn btn-sm ${device.online ? "btn-outline-secondary" : "btn-outline-success"}`}
                              style={{ fontSize: "0.72rem", width: "72px" }}
                              onClick={() => handleToggleDevice(device.id)}
                            >
                              {device.online ? "Tắt" : "Bật"}
                            </button>
                            <button
                              className="btn btn-sm btn-outline-danger"
                              style={{ fontSize: "0.72rem" }}
                              onClick={() => handleDeleteDevice(device.id)}
                            >
                              <TrashFill size={11} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* ── Activity Log ── */}
          <div id="activity" className="mb-4">
            <h6 className="fw-bold text-muted text-uppercase mb-3" style={{ fontSize: "0.75rem", letterSpacing: "0.08em" }}>
              📋 Activity Log
            </h6>
            <div className="card border-0 shadow-sm">

              {/* Card header with device filter + WS status indicators */}
              <div className="card-header bg-white border-bottom py-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
                <div className="d-flex align-items-center gap-2">
                  <Activity size={15} className="text-primary" />
                  <span className="fw-semibold small">Device Activity</span>
                  <span className="badge bg-secondary-subtle text-secondary rounded-pill">{visibleLogs.length} entries</span>
                </div>

                {/* Per-device WS status dots + filter buttons */}
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <button
                    className={`btn btn-sm ${selectedDeviceId === null ? "btn-primary" : "btn-outline-secondary"}`}
                    style={{ fontSize: "0.72rem" }}
                    onClick={() => setSelectedDeviceId(null)}
                  >
                    All
                  </button>
                  {devices.map(d => (
                    <button
                      key={d.id}
                      className={`btn btn-sm d-flex align-items-center gap-1 ${selectedDeviceId === d.id ? "btn-primary" : "btn-outline-secondary"}`}
                      style={{ fontSize: "0.72rem" }}
                      onClick={() => setSelectedDeviceId(prev => prev === d.id ? null : d.id)}
                    >
                      <span
                        style={{
                          width: "7px", height: "7px", borderRadius: "50%",
                          backgroundColor: wsStatus[d.id] ? "#198754" : "#6c757d",
                          flexShrink: 0,
                        }}
                      />
                      {d.name}
                      {!wsStatus[d.id] && <WifiOff size={10} className="text-muted" />}
                    </button>
                  ))}
                </div>
              </div>

              <div className="card-body p-0" style={{ maxHeight: "420px", overflowY: "auto" }}>
                {visibleLogs.length === 0 ? (
                  <div className="text-center text-muted py-5 small">
                    <Activity size={28} className="mb-2 opacity-25 d-block mx-auto" />
                    Chưa có hoạt động nào được ghi nhận
                  </div>
                ) : (
                  <table className="table table-hover align-middle mb-0" style={{ tableLayout: "fixed", width: "100%" }}>
                    <colgroup>
                      <col style={{ width: LOG_COL.num     }} />
                      <col style={{ width: LOG_COL.device  }} />
                      <col style={{ width: LOG_COL.user    }} />
                      <col style={{ width: LOG_COL.payload }} />
                      <col style={{ width: LOG_COL.status  }} />
                      <col style={{ width: LOG_COL.result  }} />
                      <col style={{ width: LOG_COL.time    }} />
                    </colgroup>
                    <thead className="table-light" style={{ position: "sticky", top: 0, zIndex: 1 }}>
                      <tr>
                        <th className="px-3 py-2" style={{ fontSize: "0.75rem" }}>#</th>
                        <th style={{ fontSize: "0.75rem" }}>Device</th>
                        <th style={{ fontSize: "0.75rem" }}>User</th>
                        <th style={{ fontSize: "0.75rem" }}>Payload</th>
                        <th style={{ fontSize: "0.75rem" }}>Status</th>
                        <th style={{ fontSize: "0.75rem" }}>Result</th>
                        <th style={{ fontSize: "0.75rem" }}>Thời gian</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleLogs.map((log, idx) => (
                        <tr key={log.id}>
                          <td className="px-3 text-muted small">#{idx + 1}</td>
                          <td>
                            <div className="d-flex align-items-center gap-1">
                              <div
                                className="bg-warning-subtle text-warning rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
                                style={{ width: "24px", height: "24px" }}
                              >
                                <LightbulbFill size={11} />
                              </div>
                              <span className="small text-truncate">{log.device_id}</span>
                            </div>
                          </td>
                          <td>
                            <div className="d-flex align-items-center gap-1">
                              <div
                                className="bg-primary-subtle text-primary rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
                                style={{ width: "24px", height: "24px", fontSize: "0.65rem" }}
                              >
                                {log.created_by_username ? log.created_by_username[0].toUpperCase() : "?"}
                              </div>
                              <span className="small text-truncate">{log.created_by_username ?? "—"}</span>
                            </div>
                          </td>
                          <td>
                            <code className="small text-truncate d-block" style={{ maxWidth: "130px" }}>
                              {typeof log.payload === "object" ? JSON.stringify(log.payload) : String(log.payload ?? "—")}
                            </code>
                          </td>
                          <td><StatusBadge status={log.status} /></td>
                          <td className="small text-muted text-truncate">
                            {log.result ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="small text-muted">
                            {new Date(log.created_at).toLocaleString("vi-VN")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default AdminPage;