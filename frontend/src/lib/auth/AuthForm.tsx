"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "../api";
import { setAccessToken } from "../auth/session";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email"));
    const password = String(f.get("password"));
    try {
      const pair = mode === "login"
        ? await api().post("/v1/auth/login", { body: { email, password } })
        : await api().post("/v1/auth/signup", { body: { email, password, display_name: String(f.get("display_name") || "") || undefined } });
      setAccessToken(pair.access_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "요청에 실패했습니다.");
    }
  }
  return (
    <form className="gc-auth" onSubmit={submit}>
      <h1>{mode === "login" ? "로그인" : "회원가입"}</h1>
      {mode === "signup" && <label>이름<input name="display_name" autoComplete="name" /></label>}
      <label>이메일<input name="email" type="email" required autoComplete="email" /></label>
      <label>비밀번호<input name="password" type="password" required minLength={mode === "signup" ? 12 : 1} autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
      {error && <p className="gc-error" role="alert">{error}</p>}
      <button type="submit">{mode === "login" ? "로그인" : "가입"}</button>
      <p>{mode === "login" ? <Link href="/signup">계정 만들기</Link> : <Link href="/login">로그인으로</Link>}</p>
    </form>
  );
}
