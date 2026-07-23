export type Thread = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  preview?: string | null;
};

export type Message = {
  id: number;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error ?? `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getThreads() {
  return request<{ threads: Thread[] }>("/api/threads");
}

export async function createThread(title?: string) {
  return request<{ thread: Thread }>("/api/threads", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function getMessages(threadId: string) {
  return request<{ messages: Message[] }>(`/api/threads/${threadId}/messages`);
}

export async function sendMessage(threadId: string | null, message: string) {
  return request<{ thread: Thread; messages: Message[]; answer: string }>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId, message }),
  });
}
