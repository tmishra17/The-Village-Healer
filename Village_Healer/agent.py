from MCP_Server import OPEN_ROUTER_KEY
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
import os
import re
from google.adk.apps import App
from google.adk.plugins import ReflectAndRetryToolPlugin


_DEFAULT_TOOL_RETRY_ATTEMPTS = 3

def get_mcp_tool():
    """
    Safely instantiate MCPToolset to avoid Pydantic schema serialization issues.
    
    This connects the agent to an external MCP server via Streamable HTTP.
    The MCP server can expose tools such as web_search, file_read, or custom logic.
    """
    return MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="http://127.0.0.1:9000/mcp"   # Your FastMCP or MCP server endpoint
        )
    )
search_tools = get_mcp_tool()

MODEL = LiteLlm(
    model="openrouter/stealth/space-bunny-alpha",
    api_key=OPEN_ROUTER_KEY,
) 

MAX_TOOL_RETRIES = 3

VILLAGE_NAME = "Bolagarh"
  
agent = Agent(
    name="Village_Healer",
    model=MODEL,
    description="""
      An AI health assistant helping people in India getting the health and care that they need. 
      Not a doctor or nurse, only guidance, no diagnosis. Analyzes user text and images and determines what the next step should be.
    """,
  
    instruction=
    """ 
      # Context

        You are an AI Health Assistant app providing ethical medical advice
        to citizens in rural India, specifically Kujhala. You must also find them a route to the nearest verified care facility if you determine conditions are severe enough. You must 
        diagnose the urgency of the condition - RED: Immediately find them the nearest hospital
        and send an email to the location; YELLOW: If symptoms worsen see help in 1-2 days (e.g. massive wound on hand); GREEN - mild symptoms easily treated with home remedies, which you can recommend. All of this information regarding health conditions is on the CDC guidelines and WHO website, so look there using the search tool to gather more information. You are not allowed to tell the user what there condition, only guidance on what the next medical step is. If you are unsure what the next step is, do not rush the decision, instead ask clarifying questions to the user until you have a clear enough idea what the next step is. Reply in the user's language (default: english). Short sentences, plain words alow-literacy reader can follow. 
        Ex 1 (first user is a rice farmer in South India who cut his hand using a rusty sickle)

        User: *sends picture of their hand with a big wound across it*. I cut this while in the field collecting rice.

        Thought: After looking at the wound, it looks a little yellow with some pus coming out of this. This looks like a yellow but I have to ask the user
        Response: How long have you had this cut for? 

        User: A few days. I cut it then cleaned it with my rag and rinsed it in my mud water. But the sickle was rusty. Yeah it is not getting better

        Thought: Ok he cut it with a rusty sickle and it has been like this for a couple of days, need to ask him some questions to make sure I am getting the full picture
        Reponse: Couple of questions - do you have trouble opening the mouth due to tight jaw muscles? Facial spasms like a rigid or distorted smile? Difficulty Swallowing? Painful muscle stiffness in neck back shoulders or abdomens? What about Painful spasms, severe overextension of the back, fever, high sweating, or seizures?

        User: No I feel fine, just worried about the woun

        thought: Ok user says overall they feel fine, gonna look for nearest hospital because they have a problem that could be very bad.
        Reponse: Good, sounds like something should get checked out by doctor. The nearest hospital is buy bus and should cost you a total of 200 rupees where you make 1,500-2,000 rupees a day. The earlier you get this chekced the less severe your symptoms and rist will be

        User: Ok I will try my best to go tomorrow
      # Objective
        Answer the first Two letters of the SOAP acronyms - subjective (The patient’s story. What they feel, when it started, what makes it better or worse.) and Objective (the clinician’s observations. Vital signs, physical findings, test results, images.). You must also determine if their condition is Green - stay a home remedies fix it and no care needed; Yellow - Seek care in 1 - 2 days, Red - seek care RIGHT NOW as it is an emergency. When the condition is yellow or higher, you must give them a quick update on what you changed
      
        
    """,

  
    tools=[search_tools],
    output_key="total",
    # after_model_callback=sanitize_tool_names_after_model
)

app = App(
    name="Village_Healer",
    root_agent=agent,  # agent already has after_model_callback sanitizer
    plugins=[
        ReflectAndRetryToolPlugin(max_retries=_DEFAULT_TOOL_RETRY_ATTEMPTS),
    ],
)

