That's a good use case for LangGraph. You should **not** ask the LLM to "append to a variable." Instead, make the LLM return structured data, and let your node store it in the graph state.

### 1. Define your state

```python
from typing_extensions import TypedDict

class GraphState(TypedDict):
    resume_code: str
    keywords: list[str]
```

---

### 2. Define the output schema

Using Pydantic ensures the LLM returns exactly what you want.

```python
from pydantic import BaseModel

class KeywordOutput(BaseModel):
    keywords: list[str]
```

---

### 3. Create a structured LLM

```python
structured_llm = llm.with_structured_output(KeywordOutput)
```

---

### 4. Write the extraction node

```python
def extract_keywords(state: GraphState):
    prompt = f"""
    You are an ATS keyword extractor.

    Given the following LaTeX resume project, extract all important technical
    keywords, skills, technologies, frameworks, programming languages,
    tools, APIs, and concepts.

    Return only the extracted keywords.

    Resume:
    {state["resume_code"]}
    """

    result = structured_llm.invoke(prompt)

    return {
        "keywords": result.keywords
    }
```

---

### 5. Example

Input:

```python
state = {
    "resume_code": resume_code
}
```

Output state:

```python
{
    "resume_code": "...latex...",
    "keywords": [
        "React.js",
        "Python",
        "FastAPI",
        "LangChain",
        "OpenAI",
        "HuggingFace Embeddings",
        "Docker",
        "RAG",
        "YouTube Transcript API",
        "Conversational AI"
    ]
}
```

---

### Why this is the recommended LangGraph approach

Instead of asking the model to produce formatted text like:

```
- React.js
- Python
- Docker
```

you ask it to produce a structured object. LangGraph can then directly update the state with:

```python
{
    "keywords": result.keywords
}
```

This avoids parsing text and makes your graph more reliable and easier to maintain.
