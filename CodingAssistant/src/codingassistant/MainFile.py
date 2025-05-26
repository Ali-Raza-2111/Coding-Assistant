import os
from dotenv import load_dotenv
from typing import Dict
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

# Define your agent with the tool included
Generating_agent = Agent(
    name="Generating-Assistant",
    instructions="""
    take the file name and file type and the code the user want to generate and then call the generate code file tool and stores the code
""".strip(),
    model=OpenAIChatCompletionsModel(
        model='gemini-2.0-flash',
        openai_client=client
    ),
    tools=[generate_code_file]  # Attach the tool
)

agent = Agent(
    name="Parent-Assistant",
    instructions = """
You are ParentAssistant, the central coordinator. You oversee all user requests and delegate specialized tasks to child agents.

1
You are ParentAssistant, the central coordinator. You oversee every user request and delegate tasks to specialized child agents.

1. Intent Detection
   - If the users request involves generating, saving, or writing code (new scripts, files, or snippets), immediately hand off to Generating-Assistant.
   - Otherwise, handle the request yourself following coding-assistant best practices.""".strip(),
    model=OpenAIChatCompletionsModel(
        model='gemini-2.0-flash',
        openai_client=client
    ),
    handoffs=[Generating_agent],
)
# Chainlit message handler
@cl.on_message
async def main(message: cl.Message):
    try:
        # Run the agent asynchronously with the user message
        result = await Runner.run(agent, message.content)

        # Send the agent's final response back to Chainlit UI
        await cl.Message(content=result.final_output).send()

    except Exception as e:
        # Gracefully handle and display errors
        await cl.Message(content=f"Error: {str(e)}").send()
