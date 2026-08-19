export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiUnauthorizedError extends Error {
  constructor(message = "Session expired. Please log in again.") {
    super(message);
    this.name = "ApiUnauthorizedError";
  }
}

export async function apiErrorMessage(response: Response, fallback: string) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const location = Array.isArray(item.loc) ? item.loc.join(".") : "field";
          return `${location}: ${item.msg ?? "Invalid value"}`;
        })
        .join("; ");
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export async function parseApiResponse<T>(response: Response, fallback: string): Promise<T> {
  if (response.status === 401) {
    throw new ApiUnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(await apiErrorMessage(response, fallback));
  }
  return (await response.json()) as T;
}
