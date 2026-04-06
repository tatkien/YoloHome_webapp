import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { HiEye, HiEyeOff } from "react-icons/hi";
import { toast } from "react-toastify";
import { useAuth } from '../contexts/AuthContext';

const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(username, password);
      toast.success("Login successful!");
      
      if (from === '/') {
        if (data.user.role === "admin") {
          navigate("/admin", { replace: true });
        } else {
          navigate("/", { replace: true });
        }
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100 bg-light">
      <div className="card shadow p-4 border-0 rounded-4" style={{ width: "100%", maxWidth: "400px" }}>
        <h3 className="text-center mb-4 fw-semibold">Login</h3>

        {error && (
          <p className="text-danger text-center small mb-3">{error}</p>
        )}

        <form onSubmit={handleSubmit}>

          {/* Username */}
          <div className="mb-3">
            <label className="form-label text-muted small fw-bold">Username</label>
            <input
              type="text"
              name="username"
              className="form-control"
              placeholder="Enter username..."
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          {/* Password */}
          <div className="mb-3">
            <label className="form-label text-muted small fw-bold">Password</label>
            <div className="input-group">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                className="form-control"
                placeholder="Enter password..."
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <HiEyeOff /> : <HiEye />}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            className="btn btn-primary w-100 mt-2"
            type="submit"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" />
                Loading...
              </>
            ) : (
              "Login"
            )}
          </button>
        </form>

        <p className="text-center small mt-4">
          Don't have an account?{" "}
          <Link to="/register" className="text-primary fw-bold text-decoration-none">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;