from fastmcp import FastMCP
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
import json
import os
import smtplib
import http.client
from email.message import EmailMessage
from dotenv import load_dotenv




load_dotenv()
mcp = FastMCP("The Village Healer")

SERPER_API_KEY = os.environ["SERPER_API_KEY"]

OPEN_ROUTER_KEY = os.environ["OPEN_ROUTER_KEY"]


@mcp.tool
def search(query: str) -> dict:
    """
        Return the search results from the serper request

        IMPORTANT: Please use this to look up the WHO guidlines to provide medical care
        
        Arguments:
            query: string to be used to search in the search bar
        
        Returns:
            Formatted dict of the search results
    """
    payload = json.dumps({
        "q": query
    })
  
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    conn = http.client.HTTPSConnection("google.serper.dev", timeout=30)
    try:
        conn.request("POST", "/places", payload, headers)
        data = conn.getresponse()
        return json.loads(data.read().decode("utf-8"))
    finally:
        conn.close()

    # New connection per call — reused HTTPSConnection dies after keep-alive close.


# server_params — the StdioServerParameters from above (the "how to launch").
# timeout (float) — how long to wait for the server to respond before giving up.
# MCPToolset = the CLIENT that connects, discovers tools, and gives them to your Agent





@mcp.tool
def find_nearest_facility(village_name: str) -> tuple[float, float, str]:
  """
    Based on the location of the village, find the nearest care facility within the patient's budget (government hospital is the cheapest, if they have money, find the nearest hospital). 

    IMPORTANT: User this only on user request or in RED emergency situation. Use in the query keywords like 'Bolagarh Hospital', 'government hospital near me', 'high quality hospital near me'

    Returns Tuple of lat, long, and address of nearest hospital
  """
  results = search(f"hospital near {village_name}")
  places = results.get("places") or []
  if not places:
    raise ValueError(f"No facilities found near {village_name}")
  place = places[0]
  return place["latitude"], place["longitude"], place["address"]

# @mcp.tool
# def get_village_context(village_name: str, query: str) -> dict:
#   """
#     Use Serper to get the location of the village user provdes. Search for the village on Serper and find the nearest hospitals that are government verified or that have good reviews. 
    
#     IMPORTANT: USE THIS ONLY WHEN THE USER ASK FOR A RIDE TO A HOSPITAL OR THEIR SITUATION IS A RED

#     Argument:
#       - village_name name of the village user provides
#       - query: query you type in the search result for serper
#     Returns coordinate locations of the village
#   """
#   results = search(query + village_name)

#   return results["place_results"]["gps_coordinates"]

@mcp.tool
def send_patient_data(text: str) -> str:
    """
        Sends the patient data to a legitimate hospital near them, in the style of a medical record. User serper to find the email of the hospital and then send the information via gmail in the style of a medical record. Use gmail SMTP to send the email
    
        IMPORTANT: Only use this on patient request, or in a RED emergency

        Argument:
            text: patient information formatted in the style of a medical record

        returns:
            - String informing user where the email was sent
    """

    to_email = "tej.k.mishra@gmail.com"
    msg = EmailMessage()
    msg["Subject"] = "Patient care summary"
    msg["From"] = os.environ["GMAIL_ADDRESS"]
    msg["To"] = to_email
    msg.set_content(text)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(
            os.environ["GMAIL_ADDRESS"],
            os.environ["GMAIL_APP_PASSWORD"],  # App Password, not normal password
        )
        smtp.send_message(msg)
    return f"Email sent to {to_email}"


@mcp.tool()
def write_to_memory(context: str, name: str):
    """Write to memory non-rederivable details"""
    try:
        with open(f"memory-{name}.md", 'w') as fwrite:
            fwrite.write(context) 
    except Exception as e:
        print(f"Error: {e}")


@mcp.tool()
def read_from_memory(filename: str):
    """Read memory from vector db storage"""
    try:
        with open(filename) as fread:
            text = fread.text()
            return text
    except Exception as e:
        print(f"Error: {e}")
    
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9000)

