import streamlit as st
import uuid

from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage


# ------------------------
# Utility Functions
# ------------------------

def generate_thread_id():
    return str(uuid.uuid4())


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"][thread_id] = []


def new_chat():
    thread_id = generate_thread_id()
    add_thread(thread_id)
    st.session_state["thread_id"] = thread_id


def open_chat(thread_id):
    st.session_state["thread_id"] = thread_id
    st.rerun()


def delete_chat(thread_id):

    if thread_id in st.session_state["chat_threads"]:
        del st.session_state["chat_threads"][thread_id]

    # if all chats deleted, create one
    if len(st.session_state["chat_threads"]) == 0:
        new_thread = generate_thread_id()
        add_thread(new_thread)
        st.session_state["thread_id"] = new_thread

    # if current chat deleted, switch to first available
    elif st.session_state["thread_id"] == thread_id:
        st.session_state["thread_id"] = next(
            iter(st.session_state["chat_threads"])
        )

    st.rerun()


# ------------------------
# Session State
# ------------------------

if "chat_threads" not in st.session_state:
    first_thread = generate_thread_id()

    st.session_state["chat_threads"] = {
        first_thread: []
    }

    st.session_state["thread_id"] = first_thread


# ------------------------
# Sidebar
# ------------------------

st.sidebar.title("🤖 LangGraph Chatbot")

st.sidebar.button(
    "➕ New Chat",
    on_click=new_chat,
    use_container_width=True
)

st.sidebar.divider()

st.sidebar.subheader("Conversations")

for thread_id in st.session_state["chat_threads"].keys():

    col1, col2 = st.sidebar.columns([5, 1])

    with col1:
        if st.button(
            thread_id[:8],
            key=f"open_{thread_id}",
            use_container_width=True
        ):
            open_chat(thread_id)

    with col2:
        if st.button(
            "🗑️",
            key=f"delete_{thread_id}",
            use_container_width=True
        ):
            delete_chat(thread_id)

st.sidebar.divider()

st.sidebar.caption("Current Thread")

st.sidebar.code(st.session_state["thread_id"])


# ------------------------
# Display Messages
# ------------------------

messages = st.session_state["chat_threads"][
    st.session_state["thread_id"]
]

for message in messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ------------------------
# Chat Input
# ------------------------

user_input = st.chat_input("Type your message...")

if user_input:

    messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    config = {
        "configurable": {
            "thread_id": st.session_state["thread_id"]
        }
    }

    with st.chat_message("assistant"):

        ai_message = st.write_stream(
            message_chunk.content
            for message_chunk, metadata in chatbot.stream(
                {
                    "message": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=config,
                stream_mode="messages"
            )
        )

    messages.append(
        {
            "role": "assistant",
            "content": ai_message
        }
    )