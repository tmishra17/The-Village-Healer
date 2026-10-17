import io
import torch
from PIL import Image
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.lite_llm import LiteLlm
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.adk.tools import ToolContext, FunctionTool
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from transformers import AutoModel, AutoProcessor

_DEFAULT_TOOL_RETRY_ATTEMPTS = 3

# --- Network configuration ---
BASE_URL = "http://10.0.10.70:8000/v1"           # OpenAI-compatible vLLM endpoint
MODEL_NAME = "openai/Qwen/Qwen3-VL-8B-Instruct"  # model hosted on the cluster
MCP_URL = "http://127.0.0.1:9000/mcp"            # FastMCP server (streamable HTTP)

VILLAGE_NAME = "Kujhala"

# --- Initialize SigLIP 2 globally to prevent re-instantiation overhead ---
SIGLIP_MODEL_NAME = "google/siglip2-base-patch16-224"
print(f"Loading SigLIP 2 processor and model ({SIGLIP_MODEL_NAME})...")
siglip_processor = AutoProcessor.from_pretrained(SIGLIP_MODEL_NAME)
siglip_model = AutoModel.from_pretrained(SIGLIP_MODEL_NAME, device_map="auto")

# FIXED: drop_params is set to False so ADK natively passes tool schemas to vLLM
MODEL = LiteLlm(
    model=MODEL_NAME,
    api_base=BASE_URL,
    api_key="temp",  
    drop_params=False
)


def get_mcp_tools() -> MCPToolset:
    """Connect to the FastMCP server over streamable HTTP (must match MCP_Server.py)."""
    return MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=MCP_URL,
            timeout=30,  # Serper lookups can be slow
        )
    )


def read_and_classify_symptom_image(
    candidate_labels: list[str], 
    tool_context: ToolContext
) -> dict:
    """
    Scans the GADK UI session message history for the most recent uploaded image file,
    extracts the raw bytes, and processes it through SigLIP 2 for objective verification.
    """
    session_history = tool_context.get_history()
    image_bytes = None
    
    # Scan backward through history to grab the last uploaded image part
    for message in reversed(session_history):
        if not message.parts:
            continue
        for part in message.parts:
            if part.inline_data and "image" in part.inline_data.mime_type:
                image_bytes = part.inline_data.data
                break
        if image_bytes:
            break
            
    if not image_bytes:
        return {
            "status": "Failed", 
            "error": "No uploaded image found in the chat box session context."
        }

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = siglip_processor(
            text=candidate_labels, 
            images=image, 
            padding="max_length", 
            return_tensors="pt"
        ).to(siglip_model.device)

        with torch.no_grad():
            outputs = siglip_model(**inputs)
        
        logits_per_image = outputs.logits_per_image 
        probs = logits_per_image.softmax(dim=-1).cpu().tolist()

        predictions = {label: round(prob, 4) for label, prob in zip(candidate_labels, probs)}
        
        return {
            "status": "Success", 
            "top_visual_match": max(predictions, key=predictions.get),
            "matching_probabilities": predictions
        }
    except Exception as e:
        return {"status": "Error", "details": str(e)}


search_tools = get_mcp_tools()
image_tool = FunctionTool.from_function(read_and_classify_symptom_image)

# FIXED: Removed the hardcoded "# TOOLS" code signature strings.
# Retained strategic behavior rules for execution under "# TOOLS USAGE RULES".
INSTRUCTION = f"""
# ROLE
You are an AI health guide for people in {VILLAGE_NAME}, a village in rural India. You work like an advice nurse. You are NOT a doctor or a nurse. You give guidance only. You never give a diagnosis.

# GOAL
Help the person decide HOW SOON to get care. Give safe self-care advice only for minor, common problems.
Every health conversation ends in exactly ONE level, stated plainly:
- RED: get medical help today, right now. Name the nearest facility. Say what to do while going there.
- YELLOW: see a health worker within 1-2 days. Say why and where. Say what change means "go now".
- GREEN: home care is reasonable (for example ORS, rest, ice). Say what to do. Say exactly what change means "get help".
You may recommend home remedies ONLY when the level is GREEN.

# 

"""

# Core Village Healer agent completely wired with MCP and SigLIP tool pipelines
agent = Agent(
    name="Village_Healer",
    model=MODEL,
    description=(
        "An AI health guide for people in rural India. Not a doctor or nurse: "
        "guidance only, no diagnosis. Reads the user's text and photos and decides "
        "the next step (GREEN, YELLOW or RED)."
    ),
    instruction=INSTRUCTION,
    tools=[search_tools, image_tool],
)

root_agent = agent

app = App(
    name="Village_Healer",  # must match the package folder name
    root_agent=root_agent,
    plugins=[
        ReflectAndRetryToolPlugin(max_retries=_DEFAULT_TOOL_RETRY_ATTEMPTS),
    ],
)
