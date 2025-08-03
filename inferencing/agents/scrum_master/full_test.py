from graph import create_supervisor_graph, SupervisorState
from dispatcher import TaskDispatcher

def full_test():
    """Test the complete supervisor + dispatcher workflow"""
    graph = create_supervisor_graph()
    
    initial_state = {
        "user_request": "Build a real-time sales dashboard",
        "epic": None,
        "requirements_doc": "",
        "design_doc": "",
        "tasks": [],
        "messages": []
    }
    
    try:
        result = graph.invoke(initial_state)
        
        # Extract all stories using list comprehension
        all_stories = [story for feature in result['epic'].features for story in feature.stories]
        
        print("=== Supervisor Results ===")
        print(f"Epic Title: {result['epic'].title if result['epic'] else 'None'}")
        print(f"Requirements Doc Length: {len(result['requirements_doc'])}")
        print(f"Design Doc Length: {len(result['design_doc'])}")
        print(f"Number of Tasks: {len(result['tasks'])}")
        print(f"Number of Stories: {len(all_stories)}")
        print(f"Number of Messages: {len(result['messages'])}")
        
        # Check for problematic quotes (same as test_graph.py)
        problematic_messages = [(i, msg[:100]) for i, msg in enumerate(result['messages']) 
                               if '"' in msg and not msg.startswith("TASK_DATA:")]
        
        print("✓ No problematic double quotes found in messages" if not problematic_messages 
              else f"WARNING: {len(problematic_messages)} messages contain double quotes")
        
        # Epic title quote check
        epic_has_quotes = result['epic'] and '"' in result['epic'].title
        print(f"WARNING: Epic title contains double quotes: {result['epic'].title}" if epic_has_quotes 
              else "✓ Epic title has no double quotes")
        
        print(f"\n=== Messages ({len(result['messages'])}) ===")
        [print(f"{i+1}. {msg[:100]}{'...' if len(msg) > 100 else ''}") for i, msg in enumerate(result['messages'])]
        
        # Dispatcher testing
        print("\n=== Dispatcher Results ===")
        dispatcher = TaskDispatcher()
        dispatch_results = dispatcher.dispatch_all(all_stories)
        
        print(f"Tasks Dispatched: {len(dispatch_results)}")
        [print(f"- {r['story']}: Assigned to {r['assigned_to']}") for r in dispatch_results]
        
        return result, dispatch_results
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return None, None

if __name__ == "__main__":
    full_test()