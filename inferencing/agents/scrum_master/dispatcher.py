# dispatcher.py
from langchain_google_genai import ChatGoogleGenerativeAI
from graph import Story
import os
from dotenv import load_dotenv
from functools import partial

load_dotenv()

class TaskDispatcher:
    def __init__(self):
        create_agent = partial(ChatGoogleGenerativeAI, 
                              model="gemini-2.5-flash", 
                              google_api_key=os.getenv("GOOGLE_API_KEY"))
        
        self.agents = {role: create_agent() 
                      for role in ["data_engineer", "ui_developer", "backend_developer"]}
    
    def dispatch_task(self, story: Story) -> dict:
        agent = self.agents.get(story.assigned_to, self.agents["backend_developer"])
        response = agent.invoke(f"Plan implementation for: {story.title}")
        return {"story": story.title, "plan": response.content, "assigned_to": story.assigned_to}
    
    def dispatch_all(self, stories) -> list:
        return [self.dispatch_task(story) for story in stories]