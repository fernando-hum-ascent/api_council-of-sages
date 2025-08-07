# LangChain Graph Sage Orchestrator with Philosophical Wisdom Distribution and Conversation Persistence

This document provides an implementation for creating a LangChain Graph orchestrator where a moderator agent first analyzes the user query, decides what specific queries to send to each of 3 philosophical sages (Marcus Aurelius, Nassim Nicholas Taleb, and Naval Ravikant), consolidates their wisdom responses, and maintains conversation history using MongoDB.

## Architecture Overview

```
User Query → MongoDB (Load History) → Moderator (Query Distribution) → [Marcus Aurelius, Nassim Taleb, Naval Ravikant] (Parallel) → Moderator (Wisdom Consolidation) → MongoDB (Save) → Final Response
```

## Core Components

### 1. MongoDB Model for Conversation Persistence

First, define the MongoDB model to store conversation history with user queries and AI responses.

```python
# File: models/conversations.py

from datetime import UTC, datetime
from mongoengine import (
    DateTimeField,
    DoesNotExist,
    DynamicField,
    EmbeddedDocument,
    EmbeddedDocumentField,
    ListField,
    StringField,
)
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at
from mongoengine_plus.types import EnumField

from types import ChatUserEnum


class Message(EmbeddedDocument):
    """Individual message in a conversation"""
    id = StringField(primary_key=True, default=uuid_field("MSG_"))
    role = EnumField(ChatUserEnum, required=True)  # 'human' or 'ai'
    content = DynamicField(required=True)  # Supports both string and dict content
    timestamp = DateTimeField(default=lambda: datetime.now(UTC))


@updated_at.apply
class Conversation(BaseModel, AsyncDocument):
    """Conversation model for storing chat history"""
    meta = {
        "collection": "conversations",
        "indexes": [
            "user_id",
        ],
    }

    id = StringField(primary_key=True, default=uuid_field("CONV_"))
    user_id = StringField(required=True)
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))
    messages = ListField(EmbeddedDocumentField(Message), default=list)

    async def add_message(self, content: str | dict, role: ChatUserEnum) -> None:
        """Add a new message to the conversation"""
        self.messages.append(
            Message(
                role=role.value,
                content=content,
                timestamp=datetime.now(UTC)
            )
        )
        await self.async_save()

    def get_chat_history(self) -> list[tuple[str, str]]:
        """Convert messages to chat history format for LangChain"""
        chat_history = []
        for message in self.messages:
            role = "human" if message.role == ChatUserEnum.human else "ai"
            content = message.content
            # Convert dict content to string if needed
            if isinstance(content, dict):
                content = str(content)
            chat_history.append((role, content))
        return chat_history


async def get_active_conversation_or_create_one(
    user_id: str, conversation_id: str | None = None
) -> Conversation:
    """Get existing conversation or create a new one"""
    try:
        if conversation_id:
            return await Conversation.objects.async_get(
                id=conversation_id, user_id=user_id
            )
        else:
            # Create new conversation if no ID provided
            conversation = Conversation(user_id=user_id)
            await conversation.async_save()
            return conversation
    except DoesNotExist:
        # Create new conversation if specified ID doesn't exist
        conversation = Conversation(user_id=user_id)
        await conversation.async_save()
        return conversation
```

### 2. Request and Response Models with Conversation Support

Define the types and models that include conversation capabilities from the start.

```python
# File: types.py

from enum import Enum
from pydantic import BaseModel, Field


class ChatUserEnum(str, Enum):
    """Enum for chat user roles"""
    human = "human"
    ai = "ai"


class SageEnum(str, Enum):
    """Enum for available philosophical sages"""
    marcus_aurelius = "marcus_aurelius"
    nassim_taleb = "nassim_taleb"
    naval_ravikant = "naval_ravikant"


class OrchestratorRequest(BaseModel):
    """Request model for orchestrator endpoint with conversation support"""
    query: str = Field(description="User query to process")
    user_id: str = Field(description="Unique identifier for the user")
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID to continue existing conversation"
    )


class OrchestratorResponse(BaseModel):
    """Response model for orchestrator endpoint"""
    response: str = Field(description="The consolidated response")
    conversation_id: str = Field(description="ID of the conversation")
    agent_queries: dict[str, str] = Field(description="Queries sent to each agent")
    agent_responses: dict[str, str] = Field(description="Individual agent responses")
```

### 3. State Management with Conversation History

```python
# File: orchestrator/states.py

from typing import Annotated, Any, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class OrchestratorState(TypedDict):
    """State for intelligent agent orchestration with conversation history"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    user_id: str
    conversation_id: str
    chat_history: list[tuple[str, str]]  # Previous conversation history
    agent_queries: dict[str, str]    # Specific queries for each agent
    agent_responses: dict[str, str]  # Store individual agent responses
    final_response: str | None       # Final consolidated response
```

### 4. Unified Sage Tool with Sage Parameter

Instead of three separate tools, we'll create a single unified tool that accepts a sage parameter to determine which philosophical perspective to use.

```python
# File: orchestrator/tools/philosophical_sage.py

from langchain_core.tools import StructuredTool
from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from types import SageEnum


class PhilosophicalSageInput(BaseModel):
    """Input model for the unified philosophical sage tool"""
    sage: SageEnum = Field(description="Which philosophical sage to consult")
    query: str = Field(description="Query for the sage")
    chat_history: list[tuple[str, str]] = Field(default=[], description="Previous conversation context")


# Sage configurations with their specific settings
SAGE_CONFIGS = {
    SageEnum.marcus_aurelius: {
        "temperature": 0.3,  # Lower temperature for thoughtful, philosophical responses
        "name": "marcus_aurelius_sage",
        "response_header": "MARCUS AURELIUS REFLECTS:",
        "response_footer": "*From the Meditations of Marcus Aurelius*"
    },
    SageEnum.nassim_taleb: {
        "temperature": 0.5,  # Medium temperature for his distinctive contrarian style
        "name": "nassim_taleb_sage",
        "response_header": "NASSIM TALEB RESPONDS:",
        "response_footer": "*With characteristic Talebian skepticism*"
    },
    SageEnum.naval_ravikant: {
        "temperature": 0.6,  # Higher temperature for creative, expansive thinking
        "name": "naval_ravikant_sage",
        "response_header": "NAVAL RAVIKANT SHARES:",
        "response_footer": "*Wisdom for the modern age*"
    }
}

# Unified prompt template that changes based on sage parameter
SAGE_PROMPT_TEMPLATES = {
    SageEnum.marcus_aurelius: PromptTemplate.from_template(
        """
        You are Marcus Aurelius, Roman Emperor and Stoic philosopher. Respond as if you are writing in your Meditations,
        offering wisdom grounded in Stoic philosophy.

        CONVERSATION CONTEXT:
        {chat_context}

        CURRENT INQUIRY: {query}

        Drawing upon your Stoic principles and imperial experience, provide guidance that reflects:

        - The discipline of perception: See things as they truly are
        - The discipline of action: Act with virtue and for the common good
        - The discipline of will: Accept what you cannot control, focus on what you can
        - Memento mori: Remember mortality and the fleeting nature of all things
        - Virtue as the sole good: Wisdom, justice, courage, and temperance
        - Cosmic perspective: Our place in the larger order of nature

        Consider the conversation history to provide continuity in your philosophical guidance.
        Speak with the voice of someone who has ruled an empire yet remained humble before the cosmos.

        Respond in 2-3 paragraphs with practical wisdom that can be applied to modern life.
        """,
    ),

    SageEnum.nassim_taleb: PromptTemplate.from_template(
        """
        You are Nassim Nicholas Taleb, the iconoclastic thinker and author of "The Black Swan," "Antifragile," and "Skin in the Game."
        Respond with your characteristic wit, mathematical rigor, and disdain for pseudo-intellectuals.

        CONVERSATION CONTEXT:
        {chat_context}

        CURRENT QUESTION: {query}

        Apply your core concepts and thinking patterns:

        - Black Swan events: Rare, high-impact events that are unpredictable yet rationalized after the fact
        - Antifragility: Systems that gain from disorder and stress rather than merely surviving it
        - Skin in the Game: Real-world consequences and accountability, not just theoretical knowledge
        - Via Negativa: What NOT to do is often more important than what to do
        - Lindy Effect: The older something is, the longer it's likely to persist
        - Barbell Strategy: Extreme risk management with safe + highly speculative positions
        - Intellectual Yet Idiot (IYI): Critique of academic theories divorced from practice
        - Probabilistic thinking and fat-tailed distributions

        Consider the conversation history to build upon previous insights while maintaining your provocative style.

        Write with your characteristic blend of erudition and street smarts. Be contrarian where appropriate.
        Include references to probability, Lebanon, deadlifting, or other Talebian themes when relevant.

        Respond in 2-3 paragraphs with practical insights that challenge conventional wisdom.
        """,
    ),

    SageEnum.naval_ravikant: PromptTemplate.from_template(
        """
        You are Naval Ravikant, entrepreneur, investor, and philosopher. Respond with your characteristic clarity,
        combining ancient wisdom with modern insights about wealth, happiness, and decision-making.

        CONVERSATION CONTEXT:
        {chat_context}

        CURRENT QUESTION: {query}

        Draw upon your core principles and frameworks:

        - Wealth creation through specific knowledge, leverage, and accountability
        - The difference between wealth (assets that earn while you sleep) and money/status
        - Happiness as a choice and skill that can be developed
        - The importance of reading, meditation, and clear thinking
        - Specific knowledge: Things you can't be trained for but are uniquely good at
        - Leverage: Labor, capital, code, and media that amplify your efforts
        - Principal-agent problems and misaligned incentives
        - First principles thinking and mental models
        - The integration of Eastern philosophy with Western entrepreneurship
        - Decision-making frameworks and the value of saying no

        Consider the conversation history to provide coherent guidance that builds on previous insights.

        Speak with your characteristic twitter-like clarity - profound insights delivered simply.
        Include references to entrepreneurship, investing, philosophy, or science when relevant.

        Respond in 2-3 paragraphs with actionable wisdom that combines practical and philosophical insights.
        """,
    )
}


async def philosophical_sage_function(
    sage: SageEnum,
    query: str,
    chat_history: list[tuple[str, str]] = None
) -> str:
    """Unified sage function that provides wisdom based on the specified sage parameter"""

    # Get sage-specific configuration
    config = SAGE_CONFIGS[sage]
    prompt_template = SAGE_PROMPT_TEMPLATES[sage]

    # Create LLM instance with sage-specific settings
    llm = ChatAnthropic(
        model="claude-3-5-haiku-20241022",
        temperature=config["temperature"],
    )

    # Format chat history for context
    if chat_history:
        chat_context = "\n".join([f"{role.upper()}: {content}" for role, content in chat_history[-3:]])
    else:
        chat_context = "No previous conversation context."

    # Format the prompt with the query and context
    formatted_prompt = prompt_template.format(
        query=query,
        chat_context=chat_context
    )

    # Invoke the LLM
    response = await llm.ainvoke(formatted_prompt)

    # Return the response with sage-specific formatting
    sage_response = f"""
{config["response_header"]}

{response.content}

{config["response_footer"]}
"""
    return sage_response


# Create the unified tool
philosophical_sage = StructuredTool.from_function(
    name="philosophical_sage",
    description="Provides philosophical wisdom from Marcus Aurelius (Stoic), Nassim Taleb (Antifragile), or Naval Ravikant (Modern Philosophy) based on the sage parameter",
    args_schema=PhilosophicalSageInput,
    coroutine=philosophical_sage_function,
)
```

### 5. Intelligent Moderator Agent with Conversation Awareness

```python
# File: orchestrator/moderator.py

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class QueryDistributionOutput(BaseModel):
    """Output model for query distribution decisions"""
    marcus_query: str = Field(description="Specific query for Marcus Aurelius sage")
    taleb_query: str = Field(description="Specific query for Nassim Taleb sage")
    naval_query: str = Field(description="Specific query for Naval Ravikant sage")
    distribution_rationale: str = Field(description="Explanation of why queries were distributed this way")


class ResponseModerator:
    """Moderator that distributes queries and consolidates responses with conversation context"""

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0.2)
        self.distribution_parser = PydanticOutputParser(pydantic_object=QueryDistributionOutput)

        # Template for query distribution with conversation context
        self.distribution_template = PromptTemplate.from_template(
            """
            You are an intelligent moderator that analyzes user queries and decides what specific questions each philosophical sage should address, considering conversation history for context.

            CONVERSATION CONTEXT:
            {chat_context}

            CURRENT USER QUERY: {user_query}

            AVAILABLE SAGES:
            1. MARCUS AURELIUS: Roman Emperor and Stoic philosopher - specializes in virtue ethics, discipline, acceptance, and practical wisdom for living well
            2. NASSIM TALEB: Scholar of probability and uncertainty - focuses on antifragility, risk, black swan events, and skeptical thinking
            3. NAVAL RAVIKANT: Entrepreneur and modern philosopher - combines ancient wisdom with modern insights on wealth, happiness, and decision-making

            YOUR TASK:
            Analyze the current query in the context of the conversation history and create specific, tailored questions for each sage that will collectively provide a comprehensive response. Each sage should receive a query that plays to their philosophical strengths and builds on the conversation context.

            GUIDELINES:
            - Consider conversation history to maintain continuity and avoid repetition
            - Make each query specific and actionable for that sage's philosophical domain
            - Ensure the three queries complement each other without significant overlap
            - The combination of all three responses should fully address the current query with conversation context
            - Tailor the language and focus to each sage's area of expertise

            RESPONSE FORMAT:
            {format_instructions}

            Create focused, specific queries that will generate the most valuable wisdom from each sage while maintaining conversation continuity.
            """,
            partial_variables={
                "format_instructions": self.distribution_parser.get_format_instructions()
            }
        )

    async def distribute_query(self, user_query: str, chat_history: list[tuple[str, str]] = None) -> dict[str, str]:
        """Analyze user query with conversation context and create specific queries for each sage"""

        # Format chat history for context
        if chat_history:
            chat_context = "\n".join([f"{role.upper()}: {content}" for role, content in chat_history[-5:]])  # Last 5 exchanges
        else:
            chat_context = "No previous conversation context."

        formatted_prompt = self.distribution_template.format(
            user_query=user_query,
            chat_context=chat_context
        )

        try:
            response = await self.llm.ainvoke(formatted_prompt)
            parsed_response = self.distribution_parser.parse(str(response.content))

            return {
                "marcus_aurelius": parsed_response.marcus_query,
                "nassim_taleb": parsed_response.taleb_query,
                "naval_ravikant": parsed_response.naval_query,
                "distribution_rationale": parsed_response.distribution_rationale
            }

        except Exception as e:
            # Fallback: send the original query to all sages with context awareness
            context_note = " (considering conversation history)" if chat_history else ""
            return {
                "marcus_aurelius": f"From a Stoic perspective, how should one approach{context_note}: {user_query}",
                "nassim_taleb": f"From an antifragile and probabilistic perspective{context_note}: {user_query}",
                "naval_ravikant": f"From an entrepreneurial and philosophical perspective{context_note}: {user_query}",
                "distribution_rationale": f"Fallback distribution due to error: {str(e)}"
            }

    async def consolidate_responses(
        self,
        user_query: str,
        agent_queries: dict[str, str],
        agent_responses: dict[str, str],
        chat_history: list[tuple[str, str]] = None
    ) -> str:
        """Consolidate multiple sage responses into a single coherent response with conversation context"""

        # Format chat history for context
        if chat_history:
            conversation_context = "\n".join([f"{role.upper()}: {content}" for role, content in chat_history[-3:]])
        else:
            conversation_context = "No previous conversation context."

        # Prepare the consolidation prompt
        query_context = "\n".join([
            f"• {sage_name.replace('_', ' ').title()}: {query}"
            for sage_name, query in agent_queries.items()
            if not sage_name == "distribution_rationale"
        ])

        sage_outputs = "\n\n".join([
            f"=== {sage_name.upper().replace('_', ' ')} ===\n{response}"
            for sage_name, response in agent_responses.items()
        ])

        consolidation_prompt = f"""
        You are a skilled moderator tasked with consolidating wisdom from three philosophical sages into a comprehensive final answer that maintains conversation continuity.

        CONVERSATION CONTEXT:
        {conversation_context}

        CURRENT USER QUERY: {user_query}

        SAGE QUERIES THAT WERE SENT:
        {query_context}

        SAGE RESPONSES:
        {sage_outputs}

        YOUR TASK:
        1. Consider the conversation history to maintain continuity and avoid repetition
        2. Synthesize wisdom from all three philosophical perspectives (Stoic, Antifragile, and Modern Entrepreneurial)
        3. Create a coherent narrative that flows logically from one perspective to another
        4. Identify complementary insights and highlight where different sages reinforce each other
        5. Remove redundant information while preserving unique value from each sage
        6. Structure the response to directly address the current query while building on previous discussions
        7. Ensure the final response is comprehensive yet concise and contextually appropriate

        Provide a well-structured, consolidated response that seamlessly integrates all three philosophical perspectives while directly answering the user's query and maintaining conversation flow.
        """

        messages = [
            SystemMessage(content="You are an expert moderator who synthesizes multiple philosophical perspectives into comprehensive, actionable wisdom while maintaining conversation continuity."),
            HumanMessage(content=consolidation_prompt)
        ]

        response = await self.llm.ainvoke(messages)
        return response.content
```

### 6. Graph Definition with Conversation Context

```python
# File: orchestrator/graph_definition.py

import asyncio
from typing import Literal
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage

from .states import OrchestratorState
from .tools.philosophical_sage import philosophical_sage
from .moderator import ResponseModerator


async def query_distribution_node(state: OrchestratorState) -> dict[str, dict[str, str]]:
    """Moderator analyzes user query with conversation context and creates specific queries for each sage"""
    moderator = ResponseModerator()
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])

    try:
        sage_queries = await moderator.distribute_query(user_query, chat_history)
        return {"agent_queries": sage_queries}

    except Exception as e:
        # Fallback queries if distribution fails
        context_note = " (with conversation context)" if chat_history else ""
        fallback_queries = {
            "marcus_aurelius": f"From a Stoic perspective{context_note}: {user_query}",
            "nassim_taleb": f"From an antifragile perspective{context_note}: {user_query}",
            "naval_ravikant": f"From an entrepreneurial philosophy perspective{context_note}: {user_query}",
            "distribution_rationale": f"Fallback distribution due to error: {str(e)}"
        }
        return {"agent_queries": fallback_queries}


async def parallel_sages_node(state: OrchestratorState) -> dict[str, dict[str, str]]:
    """Execute all three sages in parallel with their specific queries and conversation context"""
    agent_queries = state["agent_queries"]
    chat_history = state.get("chat_history", [])

    # Extract specific queries for each sage
    marcus_query = agent_queries.get("marcus_aurelius", state["user_query"])
    taleb_query = agent_queries.get("nassim_taleb", state["user_query"])
    naval_query = agent_queries.get("naval_ravikant", state["user_query"])

    # Execute all sages in parallel with their specific queries and conversation context
    tasks = [
        philosophical_sage.ainvoke({"sage": "marcus_aurelius", "query": marcus_query, "chat_history": chat_history}),
        philosophical_sage.ainvoke({"sage": "nassim_taleb", "query": taleb_query, "chat_history": chat_history}),
        philosophical_sage.ainvoke({"sage": "naval_ravikant", "query": naval_query, "chat_history": chat_history}),
    ]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        sage_responses = {}
        sage_names = ["marcus_aurelius", "nassim_taleb", "naval_ravikant"]

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sage_responses[sage_names[i]] = f"Error: {str(result)}"
            else:
                sage_responses[sage_names[i]] = result

        return {"agent_responses": sage_responses}

    except Exception as e:
        return {
            "agent_responses": {
                "error": f"Failed to execute sages: {str(e)}"
            }
        }


async def consolidation_node(state: OrchestratorState) -> dict[str, list]:
    """Consolidate sage responses using the moderator with conversation context"""
    moderator = ResponseModerator()
    chat_history = state.get("chat_history", [])

    try:
        consolidated_response = await moderator.consolidate_responses(
            state["user_query"],
            state["agent_queries"],
            state["agent_responses"],
            chat_history
        )

        return {
            "messages": [HumanMessage(content=consolidated_response)],
            "final_response": consolidated_response
        }

    except Exception as e:
        return {
            "messages": [HumanMessage(content=f"Error consolidating responses: {str(e)}")],
            "final_response": f"Error: {str(e)}"
        }


# Build the orchestrator graph
builder = StateGraph(OrchestratorState)

# Add nodes
builder.add_node("query_distribution", query_distribution_node)
builder.add_node("parallel_sages", parallel_sages_node)
builder.add_node("consolidation", consolidation_node)

# Set entry point
builder.set_entry_point("query_distribution")

# Add edges
builder.add_edge("query_distribution", "parallel_sages")
builder.add_edge("parallel_sages", "consolidation")
builder.add_edge("consolidation", END)

# Compile the graph
orchestrator_graph = builder.compile()
```

### 7. Graph Execution Function with MongoDB Integration

```python
# File: orchestrator/llm_agent.py

from typing import Any
from langchain_core.messages import HumanMessage, AIMessage

from .graph_definition import orchestrator_graph
from .states import OrchestratorState
from models.conversations import get_active_conversation_or_create_one
from types import ChatUserEnum


async def arun_agent(
    query: str,
    user_id: str,
    conversation_id: str | None = None
) -> dict[str, Any]:
    """
    Main function to execute the orchestrator graph with conversation persistence.

    Args:
        query: The user query to process
        user_id: Unique identifier for the user
        conversation_id: Optional conversation ID to continue existing conversation

    Returns:
        Dictionary containing:
        - final_response: The consolidated response
        - conversation_id: The conversation ID (existing or newly created)
        - agent_queries: Queries sent to each agent
        - agent_responses: Individual agent responses
    """
    try:
        # Get or create conversation
        conversation = await get_active_conversation_or_create_one(
            user_id, conversation_id
        )

        # Get chat history from conversation
        chat_history = conversation.get_chat_history()

        # Build the initial state with conversation history
        state = build_orchestrator_state(
            query, user_id, conversation.id, chat_history
        )

        # Execute the graph with recursion limit
        result = await orchestrator_graph.ainvoke(state, {"recursion_limit": 10})

        # Extract and process the final response
        final_response = extract_final_response(result)

        # Save conversation messages
        await save_conversation_messages(conversation, query, final_response)

        # Build the output dictionary
        output = {
            "final_response": final_response,
            "conversation_id": conversation.id,
            "agent_queries": result.get("agent_queries", {}),
            "agent_responses": result.get("agent_responses", {}),
        }

        return output

    except Exception as e:
        return {
            "final_response": f"Error executing orchestrator: {str(e)}",
            "conversation_id": conversation_id,
            "agent_queries": {},
            "agent_responses": {},
        }


def build_orchestrator_state(
    query: str,
    user_id: str,
    conversation_id: str,
    chat_history: list[tuple[str, str]]
) -> OrchestratorState:
    """
    Build the initial state for the orchestrator graph with conversation history.

    Args:
        query: User query
        user_id: User identifier
        conversation_id: Conversation identifier
        chat_history: Previous conversation messages

    Returns:
        Initialized OrchestratorState
    """
    # Convert chat history to LangChain messages
    messages = []
    for role, content in chat_history:
        if role == "human":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    # Add current query as the latest human message
    messages.append(HumanMessage(content=query))

    state: OrchestratorState = {
        "messages": messages,
        "user_query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "chat_history": chat_history,
        "agent_queries": {},
        "agent_responses": {},
        "final_response": None,
    }

    return state


async def save_conversation_messages(
    conversation,
    user_query: str,
    ai_response: str
) -> None:
    """
    Save the user query and AI response to the conversation.

    Args:
        conversation: The conversation object
        user_query: The user's query
        ai_response: The AI's response
    """
    # Add user message
    await conversation.add_message(user_query, ChatUserEnum.human)

    # Add AI response
    await conversation.add_message(ai_response, ChatUserEnum.ai)


def extract_final_response(result: dict[str, Any]) -> str:
    """
    Extract the final response from the graph result.

    Args:
        result: The graph execution result

    Returns:
        The final response string
    """
    # Try to get from final_response field first
    if result.get("final_response"):
        return result["final_response"]

    # Fallback: extract from last message
    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            return last_message.content

    return "No response generated"
```

### 8. FastAPI Endpoint with Conversation Support

```python
# File: resources/orchestrator.py

from typing import Any
from fastapi import FastAPI, HTTPException, status

from orchestrator.llm_agent import arun_agent
from types import OrchestratorRequest, OrchestratorResponse


app = FastAPI(title="Sage Orchestrator API")

DESCRIPTION = "Run the philosophical sage orchestrator with intelligent query distribution and conversation persistence"
RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "description": "Invalid input data"
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Orchestrator execution failed"
    },
}


@app.post(
    "/orchestrator",
    tags=["orchestrator"],
    status_code=status.HTTP_200_OK,
    response_model=OrchestratorResponse,
    responses=RESPONSES,
    description=DESCRIPTION,
)
async def run_orchestrator_endpoint(
    request: OrchestratorRequest,
) -> OrchestratorResponse:
    """
    Main endpoint to run the sage orchestrator with conversation persistence.

    This endpoint:
    1. Receives a user query, user_id, and optional conversation_id
    2. Retrieves or creates conversation history from MongoDB
    3. Distributes the query intelligently to philosophical sages with conversation context
    4. Consolidates the wisdom into a coherent answer
    5. Saves the conversation to MongoDB
    6. Returns the final response with conversation details
    """
    try:
        # Call the orchestrator sage function with conversation support
        result = await arun_agent(
            query=request.query,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        )

        return OrchestratorResponse(
            response=result["final_response"],
            conversation_id=result["conversation_id"],
            agent_queries=result["agent_queries"],
            agent_responses=result["agent_responses"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sage orchestrator execution failed: {str(e)}"
        )
```

## Usage Examples

### Direct Function Usage

```python
# File: example_usage.py

import asyncio
from orchestrator.llm_agent import arun_agent


async def main():
    # Example with conversation continuity
    user_id = "user_123"
    user_query = "How should I approach making difficult life decisions?"

    # First message (creates new conversation)
    result = await arun_agent(
        query=user_query,
        user_id=user_id,
        conversation_id=None  # This will create a new conversation
    )

    print("=== FIRST MESSAGE ===")
    print(f"Conversation ID: {result['conversation_id']}")
    print(f"Response: {result['final_response']}")
    print(f"Sage Queries: {result['agent_queries']}")

    # Follow-up message (continues existing conversation)
    follow_up_query = "What about when the decision involves significant financial risk?"
    result2 = await arun_agent(
        query=follow_up_query,
        user_id=user_id,
        conversation_id=result['conversation_id']  # Use existing conversation
    )

    print("\n=== FOLLOW-UP MESSAGE ===")
    print(f"Conversation ID: {result2['conversation_id']}")
    print(f"Response: {result2['final_response']}")
    print("Note: The sages now have context from the previous conversation")


if __name__ == "__main__":
    asyncio.run(main())
```

### API Usage Example

```python
# File: client_example.py

import httpx
import asyncio


async def call_sage_orchestrator_api():
    """Example of calling the sage orchestrator API endpoint with conversation support"""

    async with httpx.AsyncClient() as client:
        # First API call - new conversation
        response = await client.post(
            "http://localhost:8000/orchestrator",
            json={
                "query": "How should I approach making difficult life decisions?",
                "user_id": "user_123",
                "conversation_id": None
            }
        )

        if response.status_code == 200:
            result = response.json()
            conversation_id = result['conversation_id']
            print("=== FIRST API CALL ===")
            print(f"Conversation ID: {conversation_id}")
            print(f"Final Response: {result['response']}")
            print(f"Sage Queries: {result['agent_queries']}")

            # Follow-up API call - continue conversation
            response2 = await client.post(
                "http://localhost:8000/orchestrator",
                json={
                    "query": "What if the decision involves choosing between security and potential growth?",
                    "user_id": "user_123",
                    "conversation_id": conversation_id
                }
            )

            if response2.status_code == 200:
                result2 = response2.json()
                print("\n=== FOLLOW-UP API CALL ===")
                print(f"Conversation ID: {result2['conversation_id']}")
                print(f"Follow-up Response: {result2['response']}")
                print("Note: Response includes philosophical context from previous conversation")


if __name__ == "__main__":
    asyncio.run(call_sage_orchestrator_api())
```

## Project Structure

```
council_of_sages/
├── resources/                    # API endpoints (stays in root)
│   └── orchestrator.py          # FastAPI orchestrator endpoint
├── models/                       # MongoDB models (stays in root)
│   └── conversations.py         # Conversation persistence model
├── types.py                      # Request/response models (stays in root)
├── orchestrator/                 # NEW: All orchestrator logic goes here
│   ├── __init__.py
│   ├── states.py                 # State management with conversation history
│   ├── graph_definition.py       # Graph with query distribution
│   ├── moderator.py              # Intelligent query distribution + consolidation
│   ├── llm_agent.py              # Graph execution with MongoDB persistence
│   └── tools/
│       ├── __init__.py
│       └── philosophical_sage.py # Unified philosophical sage tool
├── app.py                        # Existing FastAPI app
├── config.py                     # Existing config
├── exc.py                        # Existing exceptions
├── __init__.py                   # Existing init
├── lib/                          # Existing (for other services)
└── tasks/                        # Existing (for background tasks)
```

## Key Benefits

1. **Philosophical Wisdom Integration**: Combines three distinct philosophical perspectives for comprehensive guidance
2. **Conversation Continuity**: Each interaction builds on previous conversations for coherent, context-aware wisdom
3. **Specialized Sage Queries**: Moderator creates tailored questions that leverage each sage's unique philosophical strengths
4. **Reduced Redundancy**: Sages receive specific, focused queries and avoid repeating previous wisdom
5. **Enhanced Consolidation**: Moderator synthesizes different philosophical perspectives while maintaining conversation history
6. **Persistent Wisdom Memory**: All conversations stored in MongoDB for ongoing philosophical development
7. **User-Specific Guidance**: Each user's philosophical journey is separate and continuous
8. **Modern Practical Application**: Ancient and modern wisdom applied to contemporary challenges

### Unified Sage Tool Benefits

With the unified sage tool approach, the system also provides:

9. **Code Maintainability**: Single tool implementation reduces code duplication and simplifies maintenance
10. **Consistent Interface**: All sages share the same input/output structure while maintaining their unique characteristics
11. **Easy Extensibility**: Adding new philosophical perspectives requires only updating the configuration dictionaries
12. **Centralized Configuration**: All sage-specific settings (temperature, prompts, formatting) are managed in one location
13. **Simplified Testing**: Single tool function to test rather than three separate implementations
14. **Dynamic Sage Selection**: Runtime selection of philosophical perspective based on parameter rather than separate tool names

## How It Works

1. **User submits a query with user_id and optional conversation_id**
2. **System loads conversation history from MongoDB**:
   - If conversation_id provided: loads existing conversation
   - If no conversation_id: creates new conversation
3. **Moderator analyzes the query with conversation context**:
   - Reviews recent conversation history for philosophical continuity
   - Creates specialized sub-queries for each sage
   - Ensures wisdom builds upon previous discussions
4. **Three sages process their specific queries in parallel with conversation context**:
   - Marcus Aurelius: Receives virtue-ethics and Stoic wisdom questions with historical context
   - Nassim Taleb: Gets uncertainty and antifragile questions that build on previous insights
   - Naval Ravikant: Handles modern wealth/happiness questions that complement earlier guidance
5. **Each sage processes their tailored query** using conversation-aware philosophical prompts
6. **Moderator consolidates all wisdom**:
   - Considers conversation history to avoid repetition
   - Synthesizes responses into a coherent philosophical narrative
   - Maintains conversation flow and philosophical continuity
7. **System saves both user query and wisdom response to MongoDB**
8. **Returns the consolidated wisdom with conversation_id for future philosophical development**

This architecture ensures intelligent, context-aware philosophical guidance that builds on previous conversations while maintaining the unique wisdom traditions of each sage and providing persistent conversation memory through MongoDB integration.
