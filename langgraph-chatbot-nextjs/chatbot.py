import ast
import asyncio
import json
import operator
import os
import shlex
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, TypedDict

import requests
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


load_dotenv()

DATABASE_PATH = os.getenv("CHATBOT_DB_PATH", "langgraph-chatbot-nextjs/chatbot_threads.db")


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate_math(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_math(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        left = _evaluate_math(node.left)
        right = _evaluate_math(node.right)
        return _ALLOWED_OPERATORS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        value = _evaluate_math(node.operand)
        return _ALLOWED_OPERATORS[type(node.op)](value)

    raise ValueError("Only numeric expressions using +, -, *, /, //, %, **, and parentheses are supported.")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression."""
    try:
        parsed_expression = ast.parse(expression, mode="eval")
        result = _evaluate_math(parsed_expression)
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Error: division by zero is not allowed."
    except Exception as exc:
        return f"Error: {exc}"


@tool
def search(query: str) -> str:
    """Search the web with Exa for current or factual information."""
    exa_api_key = os.getenv("EXA_API_KEY")
    if not exa_api_key:
        return "Error: EXA_API_KEY is not set in the environment."

    response = requests.post(
        "https://api.exa.ai/search",
        headers={
            "x-api-key": exa_api_key,
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "numResults": 5,
            "contents": {"text": True},
        },
        timeout=20,
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    if not results:
        return "No search results found."

    formatted_results = []
    for index, result in enumerate(results, start=1):
        title = result.get("title") or "Untitled"
        url = result.get("url") or "No URL"
        text = (result.get("text") or "").strip().replace("\n", " ")
        snippet = text[:500] + ("..." if len(text) > 500 else "")
        formatted_results.append(f"{index}. {title}\nURL: {url}\nSnippet: {snippet}")

    return "\n\n".join(formatted_results)


base_tools = [calculator, search]

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
    temperature=0,
)

system_message = SystemMessage(
    content=(
        "You are a helpful backend chatbot. Use the calculator tool for arithmetic. "
        "Use the search tool when a question needs current, external, or factual web information. "
        "Use the Twitter/X MCP tools for Twitter/X actions such as searching posts, looking up users, "
        "or creating posts when those tools are available. When search is used, summarize the useful "
        "findings and include source URLs."
    )
)


def _json_env(name: str) -> dict[str, str]:
    value = os.getenv(name)
    if not value:
        return {}

    try:
        loaded_value = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON.") from exc

    if not isinstance(loaded_value, dict):
        raise ValueError(f"{name} must be a JSON object.")

    return {str(key): str(val) for key, val in loaded_value.items()}


def _twitter_mcp_connection() -> dict:
    command = os.getenv("TWITTER_MCP_COMMAND")
    if command:
        args = os.getenv("TWITTER_MCP_ARGS")
        return {
            "transport": "stdio",
            "command": command,
            "args": shlex.split(args) if args else [],
            "env": _json_env("TWITTER_MCP_ENV"),
        }

    url = os.getenv("TWITTER_MCP_URL", "http://127.0.0.1:8000/mcp")
    return {
        "transport": os.getenv("TWITTER_MCP_TRANSPORT", "http"),
        "url": url,
        "headers": _json_env("TWITTER_MCP_HEADERS"),
    }


def _format_mcp_error(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        nested_messages = [_format_mcp_error(error) for error in exc.exceptions]
        return "; ".join(message for message in nested_messages if message)

    message = str(exc).strip()
    if message:
        return message

    return exc.__class__.__name__


async def load_twitter_mcp_tools() -> list:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        raise RuntimeError(
            "Twitter MCP support requires langchain-mcp-adapters. "
            "Install it with: pip install langchain-mcp-adapters"
        ) from exc

    client = MultiServerMCPClient(
        {"twitter": _twitter_mcp_connection()},
        tool_name_prefix=True,
    )
    return await client.get_tools(server_name="twitter")


async def build_chatbot(include_twitter_mcp: bool = True):
    tools = list(base_tools)

    if include_twitter_mcp:
        try:
            twitter_tools = await load_twitter_mcp_tools()
            tools.extend(twitter_tools)
            print(f"Loaded {len(twitter_tools)} Twitter/X MCP tools.")
        except Exception as exc:
            print(
                "Twitter/X MCP tools were not loaded. "
                "Start XMCP at http://127.0.0.1:8000/mcp or set TWITTER_MCP_URL. "
                f"Details: {_format_mcp_error(exc)}"
            )

    llm_with_tools = llm.bind_tools(tools)

    async def chatbot_node(state: ChatState) -> dict[str, list[BaseMessage]]:
        response = await llm_with_tools.ainvoke([system_message, *state["messages"]])
        return {"messages": [response]}

    graph_builder = StateGraph(ChatState)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")

    return graph_builder.compile()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
            """
        )


def create_thread(title: str | None = None) -> dict:
    thread_id = str(uuid.uuid4())
    timestamp = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (thread_id, title or "New chat", timestamp, timestamp),
        )

    return {"id": thread_id, "title": title or "New chat", "created_at": timestamp, "updated_at": timestamp}


def list_threads() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                threads.id,
                threads.title,
                threads.created_at,
                threads.updated_at,
                (
                    SELECT content
                    FROM messages
                    WHERE messages.thread_id = threads.id
                    ORDER BY id DESC
                    LIMIT 1
                ) AS preview
            FROM threads
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_thread(thread_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()

    return dict(row) if row else None


def list_thread_messages(thread_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, thread_id, role, content, created_at
            FROM messages
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def add_message(thread_id: str, role: str, content: str) -> dict:
    timestamp = _now()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, timestamp),
        )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (timestamp, thread_id))

    return {
        "id": cursor.lastrowid,
        "thread_id": thread_id,
        "role": role,
        "content": content,
        "created_at": timestamp,
    }


def update_thread_title(thread_id: str, title: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE threads SET title = ?, updated_at = ? WHERE id = ?", (title, _now(), thread_id))


def messages_to_langchain(messages: list[dict]) -> list[BaseMessage]:
    converted_messages: list[BaseMessage] = []
    for message in messages:
        if message["role"] == "user":
            converted_messages.append(HumanMessage(content=message["content"]))
        elif message["role"] == "assistant":
            converted_messages.append(AIMessage(content=message["content"]))

    return converted_messages


def title_from_message(message: str) -> str:
    normalized_message = " ".join(message.strip().split())
    if len(normalized_message) <= 48:
        return normalized_message or "New chat"

    return f"{normalized_message[:45]}..."


async def ask_chatbot(chatbot, messages: list[BaseMessage], thread_id: str = "terminal-chat") -> str:
    response = await chatbot.ainvoke(
        {"messages": messages},
        config={"configurable": {"thread_id": thread_id}},
    )

    for message in reversed(response["messages"]):
        if isinstance(message, AIMessage) and message.content:
            return str(message.content)

    return "No response generated."


async def list_threads_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"threads": list_threads()})


async def create_thread_endpoint(request: Request) -> JSONResponse:
    body = await request.json() if request.headers.get("content-length") else {}
    thread = create_thread(body.get("title") if isinstance(body, dict) else None)
    return JSONResponse({"thread": thread}, status_code=201)


async def list_messages_endpoint(request: Request) -> JSONResponse:
    thread_id = request.path_params["thread_id"]
    if not get_thread(thread_id):
        return JSONResponse({"error": "Thread not found."}, status_code=404)

    return JSONResponse({"messages": list_thread_messages(thread_id)})


async def chat_endpoint(request: Request) -> JSONResponse:
    body = await request.json()
    message = str(body.get("message", "")).strip()
    thread_id = body.get("thread_id")

    if not message:
        return JSONResponse({"error": "Message is required."}, status_code=400)

    thread = get_thread(thread_id) if thread_id else None
    if not thread:
        thread = create_thread(title_from_message(message))
        thread_id = thread["id"]

    existing_messages = list_thread_messages(thread_id)
    user_message = add_message(thread_id, "user", message)

    if thread["title"] == "New chat":
        update_thread_title(thread_id, title_from_message(message))
        thread = get_thread(thread_id)

    langchain_messages = messages_to_langchain(existing_messages)
    langchain_messages.append(HumanMessage(content=message))
    answer = await ask_chatbot(request.app.state.chatbot, langchain_messages, thread_id)
    assistant_message = add_message(thread_id, "assistant", answer)

    return JSONResponse(
        {
            "thread": thread,
            "messages": [user_message, assistant_message],
            "answer": answer,
        }
    )


async def health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@asynccontextmanager
async def lifespan(app: Starlette):
    init_db()
    app.state.chatbot = await build_chatbot()
    yield


app = Starlette(
    debug=os.getenv("DEBUG", "0") == "1",
    lifespan=lifespan,
    routes=[
        Route("/api/health", health_endpoint, methods=["GET"]),
        Route("/api/threads", list_threads_endpoint, methods=["GET"]),
        Route("/api/threads", create_thread_endpoint, methods=["POST"]),
        Route("/api/threads/{thread_id}/messages", list_messages_endpoint, methods=["GET"]),
        Route("/api/chat", chat_endpoint, methods=["POST"]),
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your environment or .env file.")

    init_db()
    chatbot = await build_chatbot()
    print("LangGraph chatbot is ready. Type 'exit' or 'quit' to stop.")

    while True:
        query = input("\nYou: ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not query:
            continue

        try:
            thread = get_thread("terminal-chat")
            if not thread:
                thread = create_thread("Terminal chat")
                with get_db() as conn:
                    conn.execute("UPDATE threads SET id = ? WHERE id = ?", ("terminal-chat", thread["id"]))

            existing_messages = list_thread_messages("terminal-chat")
            add_message("terminal-chat", "user", query)
            langchain_messages = messages_to_langchain(existing_messages)
            langchain_messages.append(HumanMessage(content=query))
            answer = await ask_chatbot(chatbot, langchain_messages)
            add_message("terminal-chat", "assistant", answer)
            print(f"\nBot: {answer}")
        except Exception as exc:
            print(f"\nBot error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
