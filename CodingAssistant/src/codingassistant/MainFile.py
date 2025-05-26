import os
from dotenv import load_dotenv
from typing import Dict
from docx import Document
import chainlit as cl
from agents import Agent, Runner, OpenAIChatCompletionsModel, function_tool,handoff
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

# Get Gemini API key from environment
gemini_api_key = os.getenv('GOOGLE_API_KEY')

# Initialize OpenAI client for Gemini endpoint
client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url='https://generativelanguage.googleapis.com/v1beta/openai/'
)

# mapping from language/type to file extension
_EXTENSION_MAP = {
    "python": ".py",
    "javascript": ".js",
    "ts": ".ts",
    "typescript": ".ts",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "c++": ".cpp",
    "go": ".go",
    "ruby": ".rb",
    "bash": ".sh",
    "html": ".html",
    "css": ".css",
    # add more as needed
}

@function_tool
def generate_code_file(language: str, filename: str, code: str) -> Dict[str, str]:
    """
    Writes `code` into GeneratedCode/<language>/<filename>.

    Parameters:
      - language (str): e.g. "python", "javascript"
      - filename (str): with or without extension
      - code (str): full code content

    Returns:
      - dict with 'message' and 'file_path'
    """
    try:
        lang = language.strip().lower()
        ext = _EXTENSION_MAP.get(lang, "")
        if ext and not filename.lower().endswith(ext):
            filename += ext

        dir_path = os.path.join("GeneratedCode", lang or "misc")
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code.rstrip() + "\n")

        return {
            "message": f"✅ Code saved to '{file_path}'.",
            "file_path": file_path
        }
    except Exception as e:
        return {"message": f"❌ Failed to save code: {e}"}


@function_tool
def save_documentation_file(filename: str, content: str) -> Dict[str, str]:
    """
    Writes `content` into Documentation/<filename>.docx.

    Parameters:
      - filename (str): desired name, with or without .docx extension
      - content (str): full documentation or explanation text

    Returns:
      - dict with 'message' and 'file_path'
    """
    try:
        # Ensure .docx extension
        name = filename.strip()
        if not name.lower().endswith(".docx"):
            name += ".docx"

        # Prepare directory
        dir_path = os.path.join("Documentation")
        os.makedirs(dir_path, exist_ok=True)

        # Full file path
        file_path = os.path.join(dir_path, name)

        # Create and save .docx
        doc = Document()
        for line in content.splitlines():
            doc.add_paragraph(line)
        doc.save(file_path)

        return {
            "message": f"✅ Documentation saved to '{file_path}'.",
            "file_path": file_path
        }

    except Exception as e:
        return {
            "message": f"❌ Failed to save documentation: {e}"
        }
        

# Define your agent with the tool included
Generating_agent = Agent(
    name="Generating-Assistant",
    instructions="""
You are Generating-Assistant, a code generation agent.

If the user asks to generate, write, or save any programming code, do it. You only handle actual code—not summaries or documentation. Use the `generate_code_file` tool to store code files in their proper folders.
""".strip(),
    model=OpenAIChatCompletionsModel(
        model='gemini-2.0-flash',
        openai_client=client
    ),
    tools=[generate_code_file]  # Attach the tool
)


Documentation_agent = Agent(
    name="documentation-Assistant",
    instructions="""
You are Documentation-Assistant, a learning and explanation agent.

If the user wants to learn, understand, summarize, or document a code or concept, assist with clear explanations. Use the `save_documentation_file` tool to save text in .docx format. You only handle **non-code** content.
""".strip(),
    model=OpenAIChatCompletionsModel(
        model='gemini-2.0-flash',
        openai_client=client
    ),
    tools=[save_documentation_file]  # Attach the tool
)

agent = Agent(
    name="Parent-Assistant",
    instructions =  """
You are ParentAssistant, the central coordinator. You oversee all user requests and delegate tasks to two specialized child agents:

1. Generating-Assistant: handles generating and saving code files.
2. Documentation-Assistant: handles generating explanations, summaries, tutorials, and storing documentation as .docx.

Use the following rules to determine delegation:

- If the user wants to generate or store code → Handoff to **Generating-Assistant**
- If the user wants to learn, summarize, explain, or document a concept → Handoff to **Documentation-Assistant**
- If both are requested, handle each part separately using the correct agent.

Your job is to **never confuse code with documentation**. Only code goes to Generating-Assistant. Only explanations and summaries go to Documentation-Assistant.
""".strip(),
    model=OpenAIChatCompletionsModel(
        model='gemini-2.0-flash',
        openai_client=client
    ),
    handoffs=[Generating_agent,Documentation_agent],
)
#Chainlit chat history setup
auto_history: list

@cl.on_chat_start
async def on_chat_start():
    # initialize session history
    cl.user_session.set("chat_history", [])
    await cl.Message(content="👋 Welcome! I am your coding assistant. How can I help you today?").send()

@cl.on_message
async def main(message: cl.Message):
    # load and update history
    history = cl.user_session.get("chat_history") or []
    history.append({"role": "user", "content": message.content})

    # run agent with history
    result = await Runner.run(agent, history)
    reply = result.final_output

    # send reply
    await cl.Message(content=reply).send()

    # update session history
    new_history = result.to_input_list()
    cl.user_session.set("chat_history", new_history)

