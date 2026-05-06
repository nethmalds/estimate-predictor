export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export const buildUrl = (path: string) => `${API_BASE_URL}${path}`;

// ─── Wizard form API ──────────────────────────────────────────────────────────

export type WizardSubmitResponse = {
	session_id: string;
	status: string;
};

export type WizardValidateResponse = {
	valid: boolean;
	errors: Record<string, string>;
};

export async function validateWizardForm(
	payload: Record<string, unknown>,
	options?: { signal?: AbortSignal }
): Promise<WizardValidateResponse> {
	const response = await fetch(buildUrl("/api/estimate-project/form/validate"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ payload }),
		signal: options?.signal,
	});
	if (!response.ok) {
		let message = "Validation request failed";
		try {
			const data = await response.json();
			if (typeof data?.detail === "string") message = data.detail;
		} catch { /* ignore */ }
		throw new Error(message);
	}
	return response.json();
}

export async function submitWizardForm(
	payload: Record<string, unknown>,
	options?: { signal?: AbortSignal }
): Promise<WizardSubmitResponse> {
	const response = await fetch(buildUrl("/api/estimate-project/form/submit"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
		signal: options?.signal,
	});
	if (!response.ok) {
		let message = "Submission failed";
		try {
			const data = await response.json();
			if (typeof data?.detail === "string") message = data.detail;
			else if (data?.detail?.message) message = data.detail.message;
		} catch { /* ignore */ }
		throw new Error(message);
	}
	return response.json();
}

export function openFormEstimateStream(sessionId: string): EventSource {
	return new EventSource(buildUrl(`/api/estimate-project/form/stream/${sessionId}`));
}
