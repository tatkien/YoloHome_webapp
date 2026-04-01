import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { HiEye, HiEyeOff } from "react-icons/hi";
import { toast } from "react-toastify";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    password: "",
    full_name: "",
    registration_code: "",
  });
  const [errors, setErrors] = useState({});
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const newErrors = {};
    let hasError = false;

    if (form.username.length < 6 || form.username.length > 15) {
      newErrors.username = "*Tên tài khoản phải có 6-15 ký tự";
      hasError = true;
    }
    if (form.password.length < 8 || form.password.length > 16) {
      newErrors.password = "*Mật khẩu phải dài 8-16 ký tự";
      hasError = true;
    }
    if (form.full_name.length < 6 || form.full_name.length > 15) {
      newErrors.username = "*Tên người dùng phải có 6-15 ký tự";
      hasError = true;
    }
    if (!form.registration_code) {
      newErrors.registration_code = "*Key không được để trống!";
      hasError = true;
    }
    

    setErrors(newErrors);

    if (!hasError) {
      try {
        const res = await fetch("http://localhost:8000/api/v1/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        const data = await res.json();
        if (!res.ok) {
          setErrors({ general: data.detail });
          return;
        }
        toast.success("Đăng ký thành công!");
        navigate("/login");
      } catch (error) {
        setErrors({ general: "Đăng ký thất bại. Vui lòng thử lại." });
      }
    }
  };

  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100 bg-light">
      <div className="bg-white p-4 rounded-4 shadow" style={{ width: '100%', maxWidth: '400px' }}>
        <h2 className="text-center fw-semibold mb-4">Đăng ký</h2>

        {errors.general && (
          <p className="text-danger text-center small mb-3">{errors.general}</p>
        )}

        <form onSubmit={handleSubmit}>

            {/* Fullname */}
            <div className="mb-3">
                <input
                type="text"
                name="username"
                placeholder="Tên người dùng"
                value={form.full_name}
                onChange={handleChange}
                className="form-control"
                />
                {errors.username && <p className="text-danger small mt-1">{errors.full_name}</p>}
            </div>

          {/* Username */}
          <div className="mb-3">
            <input
              type="text"
              name="username"
              placeholder="Tên đăng nhập"
              value={form.username}
              onChange={handleChange}
              className="form-control"
            />
            {errors.username && <p className="text-danger small mt-1">{errors.username}</p>}
          </div>

          {/* Password */}
          <div className="mb-3">
            <div className="input-group">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="Mật khẩu"
                value={form.password}
                onChange={handleChange}
                className="form-control"
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <HiEyeOff /> : <HiEye />}
              </button>
            </div>
            {errors.password && <p className="text-danger small mt-1">{errors.password}</p>}
          </div>

          {/* Key */}
          <div className="mb-3">
            <input
              type="text"
              name="key"
              placeholder="Nhập key"
              value={form.registration_code}
              onChange={handleChange}
              className="form-control"
            />
            {errors.registration_code && <p className="text-danger small mt-1">{errors.registration_code}</p>}
          </div>

          <button type="submit" className="btn btn-success w-100">
            Đăng ký
          </button>
        </form>

        <p className="text-center small mt-3">
          Đã có tài khoản?{" "}
          <Link to="/login" className="text-success">Đăng nhập</Link>
        </p>
      </div>
    </div>
  );
}