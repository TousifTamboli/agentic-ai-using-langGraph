"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Calculator, Loader2, MessageSquare, Plus, Search, Send, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { createThread, getMessages, getThreads, Message, sendMessage, Thread } from "@/lib/api";
import { cn } from "@/lib/utils";

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function Home() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === activeThreadId) ?? null,
    [threads, activeThreadId],
  );

  async function refreshThreads(nextActiveThreadId?: string) {
    const response = await getThreads();
    setThreads(response.threads);

    if (nextActiveThreadId) {
      setActiveThreadId(nextActiveThreadId);
    } else if (!activeThreadId && response.threads.length > 0) {
      setActiveThreadId(response.threads[0].id);
    }
  }

  useEffect(() => {
    async function load() {
      try {
        setError(null);
        await refreshThreads();
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Could not load threads.");
      } finally {
        setIsLoadingThreads(false);
      }
    }

    load();
  }, []);

  useEffect(() => {
    async function loadMessages() {
      if (!activeThreadId) {
        setMessages([]);
        return;
      }

      try {
        setError(null);
        setIsLoadingMessages(true);
        const response = await getMessages(activeThreadId);
        setMessages(response.messages);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Could not load messages.");
      } finally {
        setIsLoadingMessages(false);
      }
    }

    loadMessages();
  }, [activeThreadId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  async function handleNewThread() {
    try {
      setError(null);
      const response = await createThread();
      setThreads((current) => [response.thread, ...current]);
      setActiveThreadId(response.thread.id);
      setMessages([]);
      setInput("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not create thread.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isSending) {
      return;
    }

    const optimisticMessage: Message = {
      id: Date.now(),
      thread_id: activeThreadId ?? "pending",
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };

    setInput("");
    setIsSending(true);
    setError(null);
    setMessages((current) => [...current, optimisticMessage]);

    try {
      const response = await sendMessage(activeThreadId, message);
      setActiveThreadId(response.thread.id);
      setMessages((current) => [...current.filter((item) => item.id !== optimisticMessage.id), ...response.messages]);
      await refreshThreads(response.thread.id);
    } catch (exc) {
      setMessages((current) => current.filter((item) => item.id !== optimisticMessage.id));
      setError(exc instanceof Error ? exc.message : "Could not send message.");
      setInput(message);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="flex min-h-screen bg-zinc-100 text-zinc-950">
      <aside className="hidden w-80 shrink-0 border-r border-zinc-200 bg-white lg:flex lg:flex-col">
        <div className="flex h-16 items-center justify-between border-b border-zinc-200 px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-zinc-950 text-white">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">LangGraph Chatbot</h1>
              <p className="text-xs text-zinc-500">SQLite threads</p>
            </div>
          </div>
          <Button variant="icon" onClick={handleNewThread} title="New thread">
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {isLoadingThreads ? (
            <div className="flex items-center gap-2 px-2 py-3 text-sm text-zinc-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading threads
            </div>
          ) : threads.length === 0 ? (
            <div className="px-2 py-3 text-sm text-zinc-500">No threads yet.</div>
          ) : (
            <div className="space-y-1">
              {threads.map((thread) => (
                <button
                  key={thread.id}
                  className={cn(
                    "w-full rounded-md px-3 py-2 text-left transition-colors",
                    activeThreadId === thread.id ? "bg-zinc-950 text-white" : "hover:bg-zinc-100",
                  )}
                  onClick={() => setActiveThreadId(thread.id)}
                >
                  <div className="truncate text-sm font-medium">{thread.title}</div>
                  <div className={cn("mt-1 truncate text-xs", activeThreadId === thread.id ? "text-zinc-300" : "text-zinc-500")}>
                    {thread.preview ?? "New conversation"}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-200 bg-white px-4 lg:px-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 lg:hidden">
              <Bot className="h-5 w-5" />
              <span className="text-sm font-semibold">LangGraph Chatbot</span>
            </div>
            <h2 className="hidden truncate text-base font-semibold lg:block">
              {activeThread?.title ?? "New chat"}
            </h2>
            <p className="hidden text-xs text-zinc-500 lg:block">Calculator, Exa search, and Twitter/X MCP tools</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" className="lg:hidden" onClick={handleNewThread}>
              <Plus className="h-4 w-4" />
              New
            </Button>
            <div className="hidden items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-500 sm:flex">
              <Calculator className="h-3.5 w-3.5" />
              <Search className="h-3.5 w-3.5" />
              <Sparkles className="h-3.5 w-3.5" />
            </div>
          </div>
        </header>

        {error ? (
          <div className="border-b border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 lg:px-6">{error}</div>
        ) : null}

        <div className="flex-1 overflow-y-auto px-4 py-6 lg:px-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {isLoadingMessages ? (
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading messages
              </div>
            ) : messages.length === 0 ? (
              <div className="py-16 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-md bg-white shadow-sm ring-1 ring-zinc-200">
                  <MessageSquare className="h-6 w-6 text-zinc-700" />
                </div>
                <h3 className="mt-5 text-lg font-semibold">Start a thread</h3>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-500">
                  Ask for a calculation, search the web, or use Twitter/X once the MCP server is running.
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div
                    className={cn(
                      "max-w-[min(42rem,86vw)] rounded-md px-4 py-3 shadow-sm",
                      message.role === "user"
                        ? "bg-zinc-950 text-white"
                        : "border border-zinc-200 bg-white text-zinc-900",
                    )}
                  >
                    <div className="whitespace-pre-wrap break-words text-sm leading-6">{message.content}</div>
                    <div className={cn("mt-2 text-[11px]", message.role === "user" ? "text-zinc-300" : "text-zinc-400")}>
                      {formatTime(message.created_at)}
                    </div>
                  </div>
                </div>
              ))
            )}

            {isSending ? (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-500 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Thinking
                </div>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="border-t border-zinc-200 bg-white p-4 lg:p-5">
          <div className="mx-auto flex max-w-3xl items-end gap-3">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask your chatbot..."
              className="min-h-12 flex-1 py-3"
              disabled={isSending}
            />
            <Button type="submit" className="h-12 px-4" disabled={isSending || !input.trim()}>
              {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              <span className="hidden sm:inline">Send</span>
            </Button>
          </div>
        </form>
      </section>
    </main>
  );
}
