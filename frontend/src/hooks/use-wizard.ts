/**
 * Wizard submission hook — encapsulates the full submit + SSE stream lifecycle.
 *
 * Usage:
 *   const { submit, isSubmitting, progress, result, error } = useWizardSubmit(token);
 */

"use client";

import { useState, useRef, useCallback } from "react";
import { submitWizardForm, openFormEstimateStream } from "@/services/estimates.service";
import { useWizardStore } from "@/store/wizard-store";
import type { StreamEvent } from "@/store/wizard-store";

interface UseWizardSubmitOptions {
  token?: string;
  onComplete?: (result: Record<string, unknown>, estimateId: string) => void;
  onError?: (message: string) => void;
}

export function useWizardSubmit({ token, onComplete, onError }: UseWizardSubmitOptions) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const { setSession, appendEvent, setStatus, resetSession } = useWizardStore();

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const submit = useCallback(
    async (payload: Record<string, unknown>) => {
      if (isSubmitting) return;
      setIsSubmitting(true);
      setStatus("submitting");

      try {
        const { session_id, estimate_id } = await submitWizardForm(
          payload,
          token
        );

        setSession(session_id, estimate_id ?? "");

        // Open SSE stream
        const es = openFormEstimateStream(session_id);
        eventSourceRef.current = es;

        es.addEventListener("progress", (e: MessageEvent) => {
          const event: StreamEvent = { event: "progress", data: JSON.parse(e.data) };
          appendEvent(event);
          setStatus("streaming");
        });

        es.addEventListener("completed", (e: MessageEvent) => {
          const data = JSON.parse(e.data) as Record<string, unknown>;
          const event: StreamEvent = { event: "completed", data };
          appendEvent(event);
          setStatus("completed");
          closeStream();
          setIsSubmitting(false);
          onComplete?.(data, estimate_id ?? "");
        });

        es.addEventListener("error", (e: MessageEvent) => {
          let data: Record<string, unknown> = {};
          try { data = JSON.parse(e.data); } catch { /* non-data error event */ }
          const event: StreamEvent = { event: "error", data };
          appendEvent(event);
          setStatus("error");
          closeStream();
          setIsSubmitting(false);
          const msg = (data.message as string) ?? "Pipeline error";
          onError?.(msg);
        });

        es.onerror = () => {
          // SSE connection dropped (e.g., network error)
          if (es.readyState === EventSource.CLOSED) {
            setStatus("error");
            closeStream();
            setIsSubmitting(false);
            onError?.("Connection to estimation service was lost.");
          }
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : "Submission failed";
        setStatus("error");
        setIsSubmitting(false);
        onError?.(message);
      }
    },
    [token, isSubmitting, setSession, appendEvent, setStatus, closeStream, onComplete, onError]
  );

  const cancel = useCallback(() => {
    closeStream();
    resetSession();
    setIsSubmitting(false);
  }, [closeStream, resetSession]);

  return { submit, cancel, isSubmitting };
}
