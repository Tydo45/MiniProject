// src/api/auth.ts
import type { Credentials, LoginResponse } from "../types/auth";

function toFormBody(credentials: Credentials): URLSearchParams {
  const body = new URLSearchParams();
  body.append("username", credentials.username);
  body.append("password", credentials.password);
  return body;
}

export async function login(
  credentials: Credentials,
): Promise<LoginResponse> {
  const res = await fetch("http://localhost:8000/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: toFormBody(credentials),
  });

  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail);
  }

  return res.json();
}

export async function createUser(
  credentials: Credentials,
): Promise<LoginResponse> {
  const res = await fetch("http://localhost:8000/user", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: toFormBody(credentials),
  });

  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail);
  }

  return res.json();
}