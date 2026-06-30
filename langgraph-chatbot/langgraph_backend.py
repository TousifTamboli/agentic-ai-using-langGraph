from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages

load_dotenv()

llm = ChatOpenAI(
    model='gpt-5.4-mini',
    temperature=0.7
)

class ChatState(TypedDict):
    message: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    message = state['message']
    response = llm.invoke(message)
    return {
        "message": [response]
    }

checkpointer = InMemorySaver()

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)

graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

