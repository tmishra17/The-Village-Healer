from fastmcp import FastMCP
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams


mcp = FastMCP("Demo 🚀")


"""
Differs from store credit. Users can purchase items and get discounts.
subtract from here if users choose to buy products using their balance.
if they don't have enough, say they have insufficient balance, but
charge them anyway :)
"""
BALANCE: dict[int, float] =  {}
# server_params — the StdioServerParameters from above (the "how to launch").
# timeout (float) — how long to wait for the server to respond before giving up.
# MCPToolset = the CLIENT that connects, discovers tools, and gives them to your Agent
"""
Differs from balance. Users can purchase items and get discounts.
subtract from here if users choose to buy products using store credits
"""
STORE_CREDITS: dict[int, float] = {}
BOUGHT_ITEMS: dict [int, list] = {}
NEW_USER_BALANCE = 1000
NEW_USER_STORE_CREDIT = 0

finance_tools = MCPToolset(
    connection_params = StdioConnectionParams(
        server_params = StdioServerParameters(
            command="fastmcp", # program/server to run
            args=["run", "MCP_Server.py"], # arguments (list of commands to start the server)
        )
    )
)


def _ensure_user(user_id: int) -> None:
    """
        Add a new user to the in-memory tables with starting defaults.
    Args: 
        - user_id: id of the user

    """
    if user_id not in BALANCE:
        BALANCE[user_id] = NEW_USER_BALANCE
    if user_id not in STORE_CREDITS:
        STORE_CREDITS[user_id] = NEW_USER_STORE_CREDIT
    if user_id not in BOUGHT_ITEMS:
        BOUGHT_ITEMS[user_id] = []
@mcp.tool
def get_balance(user_id: int) -> float:
    """
    ONLY INVOKE IF THE USER REQUESTS TO SEE THEIR BALANCE
    Return the user's current balance. New users are created automatically
    with a starting balance of 1000. (e.g. 
        User: What is my balance? 
        Agent: Your balance is $1000, would you like to buy or sell something?
        User: I don't know what to buy.
        Agent: No worries! Just let me know when you want to buy, I'm right here
        to help you!
        
        User: How much money do I have?
        Agent: You have $1000, would you like to purchase something with this?
        User: I was just browsing
        Agent: No worries! Just let me know when you want to buy. 
        (no call for the tool)

        User: What amount is in my account?
        Agent: You currently have $1000, what items are you thinking of purchasing? 
        User: I was just browsing
        Agent: No worries! Just let me know when you want to buy. 
        (no call for the tool)

        User: Do I have any money?
        Agent: Yes, you have $1000 right now, interested in buying something? 
        User: I was just browsing
        Agent: No worries! Just let me know when you want to buy. 
        (no call for the tool)

    )

    Args:
        user_id: id of the user

    Returns:
        The user's current balance.
    """
    _ensure_user(user_id)
    return BALANCE[user_id]

@mcp.tool
def get_store_credit(user_id: int) -> float:
    """
    ONLY INVOKE WHEN USER ASKS FOR STORE CREDIT
    Return the user's current store credit. New users are created
    automatically with a starting store credit of 0.

    Args:
        user_id: id of the user

    Returns:
        The user's current store credit.
    """
    _ensure_user(user_id)
    return STORE_CREDITS[user_id]

@mcp.tool
def add_balance(user_id: int, amount: float) -> float:
    """
    ## Description
    Add the given amount to the user's balance.
    ONLY invoke when the user explicitly asks to deposit/add money.
    Never invoke this to check a balance — use get_balance for that.
    Examples:

    ## No tool — text only
    - User: "hi" -> greet, no tool.
    - User: "what can you do?" -> describe capabilities, no tool.
    - User: "how do refunds work?" -> explain in text, no tool.
      (Asking ABOUT a refund is not requesting one.)
    - User: "is 50 dollars a lot for headphones?" -> opinion, no tool.
    - User: "thanks!" -> acknowledge, no tool.

    ## Missing info — ask, don't guess
    - User: "what's my balance?" (no id) -> ask for their user id.
      Do NOT call get_balance with a made-up id.
    - User: "I want a refund" (no amount) -> ask for the amount paid.
    - User: "buy it for me" (no item/price) -> ask which item and price.

    ## Tool calls
    - User: "what's my balance? id 5" -> get_balance(user_id=5)
    - User: "how much store credit do I have? id 5" -> get_store_credit(user_id=5)
    - User: "add $50 to my account, id 5" -> add_balance(user_id=5, amount=50)
    - User: "refund my $20 purchase, id 5, cash back please"
      -> refund_transaction(user_id=5, amount=20)
    - User: "put that $20 back as store credit, id 5"
      -> add_store_credit(user_id=5, amount=20)
    - User: "buy the mug for $12, id 5"
      -> buy_an_item(user_id=5, amount=12, item_name="mug")

    ## Ambiguous — clarify first
    - User: "I want my money back, id 5, $20" -> ask: refund to balance
      or store credit? Then call the matching tool.
    - User: "give me money" -> ask what they mean (deposit? refund?).
    
    
    Args:
        user_id: id of the user
        amount: amount to add to the user's balance

    Returns:
        The user's updated balance.
    """
    _ensure_user(user_id)
    BALANCE[user_id] += amount
    return BALANCE[user_id]

@mcp.tool
def refund_transaction(user_id: int, amount: float) -> float:
    """
    ONLY INVOKE IF THE USER REQUESTS A REFUND 
    Refund a transaction by returning the amount to the user's balance.
    Use only when the user explicitly requests a refund.

    Args:
        user_id: id of the user
        amount: amount of money to refund

    Returns:
        The user's updated balance after the refund.
    """
    _ensure_user(user_id)
    BALANCE[user_id] += amount
    return BALANCE[user_id]

@mcp.tool
def add_store_credit(user_id: int, amount: float) -> float:
    """

    Add store credit to the user's account. Use only when the user
    explicitly requests store credit.

    Args:
        user_id: id of the user
        amount: amount of store credit to add

    Returns:
        The user's updated store credit.
    """
    _ensure_user(user_id)
    STORE_CREDITS[user_id] += int(amount)
    return STORE_CREDITS[user_id]

@mcp.tool
def buy_an_item(user_id: int, amount: float, item_name: str) -> float:
    """
    ONLY INVOKE WHEN THE USER REQUESTS TO BUY AN ITEM 
    Subtract the amount the item costs from the user's balance for a purchase.

    Args:
        user_id: id of the user
        amount: price of the item to charge against the balance
        item_name: name of item user bought

    Returns:
        The user's updated balance.
    """
    _ensure_user(user_id)
    BALANCE[user_id] -= amount
    BOUGHT_ITEMS[user_id].append(item_name)
    return BALANCE[user_id]

if __name__ == "__main__":
    mcp.run()