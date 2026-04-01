import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { PersonFill, BoxArrowRight, BoxArrowInRight } from "react-bootstrap-icons";

const AdminUserSection = () => {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loggedInUser = localStorage.getItem("loggedInUser");
    if (loggedInUser) {
      try {
        setUser(JSON.parse(loggedInUser));
      } catch (error) {
        localStorage.removeItem("loggedInUser");
      }
    }
  }, []);

  const handleLogout = async () => {
    try {
      await fetch("/api/logout", { method: "POST" });
    } catch (error) {
      console.error("Lỗi logout:", error);
    } finally {
      setUser(null);
      localStorage.removeItem("loggedInUser");
      localStorage.removeItem("token");
      toast.success("Đã đăng xuất Admin!");
      navigate("/login");
    }
  };

  if (!user) {
    return (
      <div className="p-3 border-top">
        <button
          className="btn btn-primary w-100 d-flex align-items-center justify-content-center gap-2"
          onClick={() => navigate("/login")}
        >
          <BoxArrowInRight size={18} />
          Đăng nhập
        </button>
      </div>
    );
  }

  return (
    <div className="p-3 border-top d-flex align-items-center gap-2">
      {/* Avatar icon */}
      <div
        className="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
        style={{ width: "36px", height: "36px" }}
      >
        <PersonFill size={18} />
      </div>

      {/* User info */}
      <div className="flex-grow-1 overflow-hidden">
        <div className="fw-semibold text-dark small text-truncate">{user.username}</div>
        <div className="text-muted" style={{ fontSize: "0.75rem" }}>
          {user.email || "Admin"}
        </div>
      </div>

      {/* Logout button */}
      <button
        className="btn btn-sm btn-outline-danger d-flex align-items-center justify-content-center flex-shrink-0"
        title="Đăng xuất"
        onClick={handleLogout}
      >
        <BoxArrowRight size={16} />
      </button>
    </div>
  );
};

export default AdminUserSection;