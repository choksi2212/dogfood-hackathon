"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { InputField } from "@/components/Field";
import { Button } from "@/components/Button";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage(null);
    try {
      await api.login({ email, password });
      router.push("/judge");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Something went wrong.",
      );
    }
  }

  return (
    <div>
      <PageHeader title="Log in" />
      <form className={styles.form} onSubmit={handleSubmit}>
        <InputField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <InputField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Button type="submit" loading={status === "loading"} className={styles.submitButton}>
          Log in
        </Button>
        {status === "error" && errorMessage && (
          <ErrorState>{errorMessage}</ErrorState>
        )}
      </form>
    </div>
  );
}
