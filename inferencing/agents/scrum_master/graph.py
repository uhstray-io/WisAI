#from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
#from langgraph.checkpoint.memory import MemorySaver

import os
import json
import re

from dotenv import load_dotenv

load_dotenv()

def fix_quotes(text: str) -> str:
    """Simply replace all double quotes with single quotes"""
    return text.replace('"', "'")

def safe_json_parse(response_text: str, fallback_value: Any = None) -> Any:
    """Parse JSON from LLM response, converting single quotes to double quotes for valid JSON"""
    try:
        cleaned_text = re.sub(r'```(?:json)?\s*\n?', '', response_text).replace("'", '"')
        return json.loads(re.sub(r'```\s*\n?', '', cleaned_text))
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"JSON parsing failed: {e}")
        return fallback_value

class Epic(BaseModel):
    title: str
    description: str
    features: List['Feature']

class Feature(BaseModel):
    title: str
    description: str
    stories: List['Story']

class Story(BaseModel):
    title: str
    description: str
    acceptance_criteria: List[str]
    status: str
    priority: str
    assigned_to: str
    
class Task(BaseModel):
    id: str
    type: str  # "data", "ui", "backend"
    story: Story
    priority: int
    
class SupervisorState(TypedDict):
    user_request: str
    epic: Epic
    requirements_doc: str
    design_doc: str
    tasks: List[Task]
    messages: List[str]
    
# Initialize LLM with Google Generative AI
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    max_tokens=8192,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)


def parse_request(state: SupervisorState) -> SupervisorState:
    """Parse user request and create initial epic structure"""
    prompt = f"""
    Analyze this request and create an Epic structure:
    Request: {state['user_request']}
    
    Return valid JSON only with this exact structure:
    {{
        'title': 'Epic title here',
        'description': 'Brief description here',
        'features': [
            {{'title': 'Feature 1 title', 'description': 'Feature 1 description'}},
            {{'title': 'Feature 2 title', 'description': 'Feature 2 description'}}
        ]
    }}
    
    Use only single quotes for JSON string values. No double quotes in the response.
    """
    
    response = llm.invoke(prompt)
    parsed_data = safe_json_parse(response.content, {'title': 'Default Epic', 'description': 'Default description', 'features': []})
    
    features = [Feature(
        title=fix_quotes(f.get('title', 'Default Feature')),
        description=fix_quotes(f.get('description', 'Default description')),
        stories=[]
    ) for f in parsed_data.get('features', [])]
    
    state['epic'] = Epic(
        title=fix_quotes(parsed_data.get('title', 'Default Epic')),
        description=fix_quotes(parsed_data.get('description', 'Default description')),
        features=features
    )
    return state

def generate_requirements(state: SupervisorState) -> SupervisorState:
    """Generate requirements document"""
    prompt = f"""
    Create a concise requirements document for:
    Epic: {state['epic'].title}
    Description: {state['epic'].description}
    
    Include:
    - Functional requirements (5-7 items)
    - Non-functional requirements (3-5 items)
    - Constraints
    
    Keep it under 500 words.
    """
    
    response = llm.invoke(prompt)
    state['requirements_doc'] = fix_quotes(response.content)
    return state

def generate_design(state: SupervisorState) -> SupervisorState:
    """Generate design document"""
    prompt = f"""
    Create a technical design document for:
    Epic: {state['epic'].title}
    Requirements: {state['requirements_doc'][:500]}
    
    Include:
    - Architecture overview
    - Data flow
    - Key components
    - Technology stack
    
    Keep it under 500 words.
    """
    
    response = llm.invoke(prompt)
    state['design_doc'] = fix_quotes(response.content)
    return state

def create_stories(state: SupervisorState) -> SupervisorState:
    """Break down features into stories"""
    
    def create_stories_for_feature(feature):
        prompt = f"""
        Break down this feature into 2-3 user stories:
        Feature: {feature.title}
        Description: {feature.description}
        
        Return valid JSON array only with this exact structure:
        [
            {{
                'title': 'Story title here',
                'description': 'Story description here',
                'acceptance_criteria': ['Criteria 1', 'Criteria 2', 'Criteria 3'],
                'status': 'pending',
                'priority': 'medium',
                'assigned_to': 'data_engineer'
            }}
        ]
        
        Use only single quotes for JSON string values. No double quotes in the response.
        Assignment options: data_engineer, ui_developer, backend_engineer
        """
        
        response = llm.invoke(prompt)
        parsed_stories = safe_json_parse(response.content, [])
        
        feature.stories = [Story(
            title=fix_quotes(s.get('title', 'Default Story')),
            description=fix_quotes(s.get('description', 'Default description')),
            acceptance_criteria=[fix_quotes(c) for c in s.get('acceptance_criteria', [])],
            status=s.get('status', 'pending'),
            priority=s.get('priority', 'medium'),
            assigned_to=s.get('assigned_to', 'backend_engineer')
        ) for s in parsed_stories]
    
    [create_stories_for_feature(feature) for feature in state['epic'].features]
    return state

def assign_tasks(state: SupervisorState) -> SupervisorState:
    """Create task assignments for agents"""
    all_stories = [story for feature in state['epic'].features for story in feature.stories]
    
    state['tasks'] = [Task(
        id=f"T{i:03d}",
        type=story.assigned_to.split('_')[0],
        story=story,
        priority=i + 1
    ) for i, story in enumerate(all_stories)]
    
    return state

def validate_output(state: SupervisorState) -> SupervisorState:
    """Final validation and summary"""
    epic_title = fix_quotes(state['epic'].title)
    total_features = len(state['epic'].features)
    total_stories = sum(len(f.stories) for f in state['epic'].features)
    total_tasks = len(state['tasks'])
    
    summary = f"Created Epic: {epic_title} | Total Features: {total_features} | Total Stories: {total_stories} | Total Tasks: {total_tasks}"
    
    task_summary = [{
        'id': task.id,
        'type': task.type,
        'title': fix_quotes(task.story.title),
        'description': fix_quotes(task.story.description),
        'assigned_to': task.story.assigned_to,
        'priority': task.priority,
        'status': task.story.status
    } for task in state['tasks']]
    
    state['messages'].extend([summary, f"TASK_DATA: {json.dumps(task_summary, ensure_ascii=True)}"])
    return state

def create_supervisor_graph():
    workflow = StateGraph(SupervisorState)
    
    # Add nodes
    workflow.add_node("parse_request", parse_request)
    workflow.add_node("generate_requirements", generate_requirements)
    workflow.add_node("generate_design", generate_design)
    workflow.add_node("create_stories", create_stories)
    workflow.add_node("assign_tasks", assign_tasks)
    workflow.add_node("validate_output", validate_output)
    
    # Add edges
    workflow.set_entry_point("parse_request")
    workflow.add_edge("parse_request", "generate_requirements")
    workflow.add_edge("generate_requirements", "generate_design")
    workflow.add_edge("generate_design", "create_stories")
    workflow.add_edge("create_stories", "assign_tasks")
    workflow.add_edge("assign_tasks", "validate_output")
    workflow.add_edge("validate_output", END)
    
    # Compile
    #memory = MemorySaver()
    return workflow.compile()#(checkpointer=memory)

# Helper function to run the supervisor
async def run_supervisor(user_request: str) -> Dict[str, Any]:
    graph = create_supervisor_graph()
    
    initial_state = {
        "user_request": user_request,
        "epic": None,
        "requirements_doc": "",
        "design_doc": "",
        "tasks": [],
        "messages": []
    }
    
    config = {"configurable": {"thread_id": "main"}}
    result = await graph.ainvoke(initial_state, config)
    
    
    return {
        "epic": result["epic"],
        "requirements": result["requirements_doc"],
        "design": result["design_doc"],
        "tasks": result["tasks"],
        "messages": result["messages"]
    }
    
    
# class SharedState(TypedDict):
#     messages: List[str]
#     shared_data: dict
#     agent_states: dict


# # Compile individual agent as subgraph
# research_graph = StateGraph(SharedState)
# research_graph.add_node("research", research_function)
# compiled_research = research_graph.compile()

# # Add to parent supervisor graph
# supervisor_graph = StateGraph(SharedState)
# supervisor_graph.add_node("research_agent", compiled_research)
# supervisor_graph.add_node("analysis_agent", compiled_analysis)
