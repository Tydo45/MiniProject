// src/pages/AuthPage.tsx
import { useState } from "react";
import { createUser, login } from "../api/auth";
import type { LoginResponse } from "../types/auth";

type AuthMode = "login" | "register";

export default function AuthPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  return (
    <div className="container">
      <h1>{mode === "login" ? "Login" : "Create Account"}</h1>

      <div className="tabs">
        <button
          type="button"
          className={mode === "login" ? "active" : ""}
          onClick={() => setMode("login")}
        >
          Login
        </button>
        <button
          type="button"
          className={mode === "register" ? "active" : ""}
          onClick={() => setMode("register")}
        >
          Create Account
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>

        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading
            ? "Submitting..."
            : mode === "login"
              ? "Login"
              : "Create Account"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}
    </div>
  );
}