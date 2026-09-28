"use client";
import { AlertCircle, RotateCcw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function RouteError({
  message,
  reset,
}: {
  message: string;
  reset: () => void;
}) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="size-5" />
      <AlertTitle>{message.split(":")[0]}</AlertTitle>
      <AlertDescription className="flex flex-wrap items-center justify-between gap-4">
        <span>The service is temporarily unavailable. Please try again.</span>
        <Button variant="outline" onClick={reset}>
          <RotateCcw className="size-4" />
          Try again
        </Button>
      </AlertDescription>
    </Alert>
  );
}
