export type Explanation = {
  summary: string;
  steps: string[];
  assumptions: string[];
};
export type QueryArtifact = {
  artifact_id: string;
  text: string;
  validation: string;
  dialect: string;
  schema_version: string;
};
export type TurnResponse = {
  turn_id: string;
  conversation_id: string;
  request_id: string;
  status: string;
  intent: string;
  message: string;
  sql: QueryArtifact | null;
  explanation: Explanation | null;
  diagnostics: { code: string; message: string }[];
  clarification: { question: string; choices: string[] } | null;
  optimization: {
    changes: string[];
    suggestions: string[];
    index_recommendations: string[];
    rewrite_applied: boolean;
  } | null;
  error: { code: string; message: string; retryable: boolean } | null;
  meta: { total_duration_ms: number; execution_available: boolean };
};
export type Turn = {
  id: string;
  message: string;
  mode: string;
  status: string;
  response: TurnResponse | null;
  created_at: number;
};
export type Conversation = {
  id: string;
  title: string;
  created: number;
  updated: number;
};
export type Page<T> = { items: T[]; next_cursor: number | null };
export type Session = {
  csrf_token: string;
  model_configured: boolean;
  model: string | null;
  expires_at: number;
};
export type Catalog = {
  version: string;
  dialect: string;
  tables: Record<
    string,
    { name: string; type: string; nullable: boolean; primary_key: boolean }[]
  >;
  relationships: {
    from_table: string;
    from_column: string;
    to_table: string;
    to_column: string;
  }[];
  dictionary: Record<string, unknown>;
};
export type Result = {
  execution_id: string;
  columns: { name: string; type: string }[];
  rows: (string | number | null)[][];
  returned_row_count: number;
  truncated: boolean;
  limit: number;
  duration_ms: number;
};
export type Plan = {
  steps: { id: number; parent: number; detail: string }[];
  observations: string[];
};
let csrf = "";
export function setCsrf(token: string) {
  csrf = token;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: any,
  ) {
    super(
      body.error?.message ??
        body.message ??
        "The request could not be completed.",
    );
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}
export async function download(path: string, filename: string) {
  const response = await fetch("/api/v1" + path, {
    credentials: "same-origin",
  });
  if (!response.ok) throw new ApiError(response.status, await response.json());
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
