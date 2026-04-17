export type EstimationRequest = {
	description: string;
	floorplanImageUrl?: string | null;
};

export type ClarificationStartResponse = {
	status: "session_started";
	session_id: string;
	needs_clarification: boolean;
};

export type ClarificationAnswerResponse = {
	status: string;
};

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export const buildUrl = (path: string) => `${API_BASE_URL}${path}`;

const buildRequestBody = (payload: EstimationRequest) => {
	const body: Record<string, unknown> = {
		description: payload.description,
	};

	if (payload.floorplanImageUrl) {
		body.floorplan_image_url = payload.floorplanImageUrl;
	}

	return body;
};

export async function startClarificationSession(
	payload: EstimationRequest,
	options?: { signal?: AbortSignal }
): Promise<ClarificationStartResponse> {
	const response = await fetch(buildUrl("/api/estimate-project/clarification/start"), {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify(buildRequestBody(payload)),
		signal: options?.signal,
	});

	if (!response.ok) {
		let message = "Request failed";

		try {
			const data = await response.json();
			if (typeof data?.detail === "string") {
				message = data.detail;
			}
		} catch {
			// Ignore JSON parse errors and use the fallback message.
		}

		throw new Error(message);
	}

	return response.json();
}

export async function submitClarificationAnswer(
	sessionId: string,
	answer: string,
	options?: { signal?: AbortSignal }
): Promise<ClarificationAnswerResponse> {
	const response = await fetch(buildUrl(`/api/estimate-project/clarification/${sessionId}/answer`), {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ answer }),
		signal: options?.signal,
	});

	if (!response.ok) {
		let message = "Request failed";

		try {
			const data = await response.json();
			if (typeof data?.detail === "string") {
				message = data.detail;
			}
		} catch {
			// Ignore JSON parse errors and use the fallback message.
		}

		throw new Error(message);
	}

	return response.json();
}

export function openClarificationStream(sessionId: string): EventSource {
	return new EventSource(buildUrl(`/api/estimate-project/clarification/stream/${sessionId}`));
}
