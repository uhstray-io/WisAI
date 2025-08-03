from graph import create_supervisor_graph, SupervisorState

def test_supervisor_graph():
    """Test the supervisor graph with proper state structure"""
    graph = create_supervisor_graph()
    
    initial_state = {
        "user_request": "Build a web application for managing tasks",
        "epic": None,
        "requirements_doc": "",
        "design_doc": "",
        "tasks": [],
        "messages": []
    }
    
    try:
        result = graph.invoke(initial_state)
        print("=== Test Results ===")
        print(f"Epic Title: {result['epic'].title if result['epic'] else 'None'}")
        print(f"Requirements Doc Length: {len(result['requirements_doc'])}")
        print(f"Design Doc Length: {len(result['design_doc'])}")
        print(f"Number of Tasks: {len(result['tasks'])}")
        print(f"Number of Messages: {len(result['messages'])}")
        
        # Check for problematic quotes in messages (excluding TASK_DATA which uses JSON)
        problematic_messages = [(i, msg[:100]) for i, msg in enumerate(result['messages']) 
                               if '"' in msg and not msg.startswith("TASK_DATA:")]
        
        print("✓ No problematic double quotes found in messages" if not problematic_messages 
              else f"WARNING: {len(problematic_messages)} messages contain double quotes")
        
        [print(f"WARNING: Message {i} contains double quotes: {msg}...") for i, msg in problematic_messages]
        
        # Check epic title for quotes
        epic_has_quotes = result['epic'] and '"' in result['epic'].title
        print(f"WARNING: Epic title contains double quotes: {result['epic'].title}" if epic_has_quotes 
              else "✓ Epic title has no double quotes")
            
        print(f"\n=== Messages ({len(result['messages'])}) ===")
        [print(f"{i+1}. {msg[:100]}{'...' if len(msg) > 100 else ''}") for i, msg in enumerate(result['messages'])]
            
        return result
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return None

if __name__ == "__main__":
    test_supervisor_graph()