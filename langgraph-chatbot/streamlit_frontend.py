import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import BaseMessage, HumanMessage

CONFIG = {'configurable': {'thread_id': 'thread-1'}}

if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []


for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input("Type here")

if user_input:

    st.session_state['message_history'].append({'role' : 'user', 'content': user_input})
    with st.chat_message("user"):
        st.text(user_input)


    # response = chatbot.invoke({"message": [HumanMessage(content=user_input)]}, config=CONFIG)
    # ai_message = response['message'][-1].content

    with st.chat_message("assistant"):

        ai_message = st.write_stream(
            # generator object
            message_chunk.content for message_chunk, metadata in chatbot.stream(
                {'message': [HumanMessage(content=user_input)]},
                config= {'configurable': {'thread_id': 'thread-1'}},
                stream_mode='messages'
            )
        )

    st.session_state['message_history'].append({'role' : 'assistant', 'content': ai_message})







# for message_chunk, metadata in chatbot.stream(
#     
# ):
#     if message_chunk.content:
#         print(message_chunk.content, end=" ", flush=True)

