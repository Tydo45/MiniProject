// src/api/auth.ts
import type { Credentials, JwtPayload, LoginResponse } from "../types/auth";

const AUTH_API_BASE = "http://localhost:8000";

function toFormBody(credentials: Credentials): URLSearchParams {
  const body = new URLSearchParams();
  body.append("username", credentials.username);
  body.append("password", credentials.password);
  return body;
}

function decodeBase64Url(segment: string): string {
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return atob(padded);
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem("access_token");
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  const [, payload] = token.split(".");

  if (!payload) {
    return null;
  }

  try {
    return JSON.parse(decodeBase64Url(payload)) as JwtPayload;
  } catch {
    return null;
  }
}

export function getCurrentUserIdFromToken(): string | null {
  const token = getStoredAccessToken();
  const payload = token ? decodeJwtPayload(token) : null;

  return typeof payload?.sub === "string" ? payload.sub : null;
}

export async function login(
  credentials: Credentials,
): Promise<LoginResponse> {
  const res = await fetch(`${AUTH_API_BASE}/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: toFormBody(credentials),
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail);
  }

  return res.json();
}

export async function createUser(
  credentials: Credentials,
): Promise<LoginResponse> {
  const res = await fetch(`${AUTH_API_BASE}/user`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: toFormBody(credentials),
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail);
  }

  return res.json();
}
