import { useState } from "react";
import { createUser, login } from "../api/auth";
import type { LoginResponse } from "../types/auth";
import "../styles/AuthPage.css";

type AuthMode = "login" | "register";

const authModes = {
  login: {
    heading: "Welcome back",
    submitLabel: "Sign in",
    passwordAutocomplete: "current-password",
    passwordPlaceholder: "Enter your password",
  },
  register: {
    heading: "Join the game",
    submitLabel: "Create account",
    passwordAutocomplete: "new-password",
    passwordPlaceholder: "Create a password",
  },
} satisfies Record<
  AuthMode,
  {
    heading: string;
    submitLabel: string;
    passwordAutocomplete: string;
    passwordPlaceholder: string;
  }
>;

export default function AuthPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const modeContent = authModes[mode];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      let data: LoginResponse;

      if (mode === "login") {
        data = await login({ username, password });
      } else {
        data = await createUser({ username, password });
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      window.location.href = "/lobby";
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(mode === "login" ? "Login failed" : "Account creation failed");
      }
    } finally {
      setLoading(false);
    }
  }

  function handleModeChange(nextMode: AuthMode) {
    setMode(nextMode);
    setError("");
  }

  return (
    <div className="auth-root">
      <div className="card">
        <div className="card-header">
          <div className="eyebrow">
            <svg
              className="chess-icon"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M9 4h6M12 4v3M10 7h4l1 5H9l1-5zM8 12h8v2H8v-2zM6 20h12M7 20l1-6h8l1 6"
                stroke="#93d2ff"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span className="brand">Chessgame</span>
          </div>

          <h1 className="heading">{modeContent.heading}</h1>
        </div>

        <div className="card-body">
          <div className="tab-group" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={`tab ${mode === "login" ? "tab--active" : ""}`}
              onClick={() => handleModeChange("login")}
            >
              Sign in
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={`tab ${mode === "register" ? "tab--active" : ""}`}
              onClick={() => handleModeChange("register")}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="field-group">
              <div className="field">
                <label className="label" htmlFor="username">
                  Username
                </label>
                <input
                  id="username"
                  className="input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  placeholder="Enter your username"
                  required
                />
              </div>

              <div className="field">
                <label className="label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={modeContent.passwordAutocomplete}
                  placeholder={modeContent.passwordPlaceholder}
                  required
                />
              </div>
            </div>

            <button className="submit-btn" type="submit" disabled={loading}>
              {loading ? (
                <span className="loading-dots" aria-hidden="true">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </span>
              ) : (
                modeContent.submitLabel
              )}
            </button>
          </form>

          {error && (
            <div className="error" role="alert">
              <span className="error-dot" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}