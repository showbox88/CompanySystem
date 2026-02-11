
def main():
    print("Testing Selective Replying Logic...")
    
    # Mock Agents
    agents = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Charlie"}
    ]
    
    participants = ["1", "2", "3"]
    
    def get_targets(prompt):
        target_ids = []
        mentioned = False
        
        for p_id in participants:
            agent = next((a for a in agents if a['id'] == p_id), None)
            if agent and agent['name'] in prompt:
                target_ids.append(p_id)
                mentioned = True
        
        if not mentioned:
            target_ids = participants
            
        return target_ids

    # Test Cases
    tests = [
        ("Hello everyone", ["1", "2", "3"]),
        ("Alice, what do you think?", ["1"]),
        ("Bob and Charlie, please reply.", ["2", "3"]),
        ("Hey Alice!", ["1"]),
        ("Testing...", ["1", "2", "3"])
    ]
    
    for prompt, expected in tests:
        result = get_targets(prompt)
        # Sort for comparison
        result.sort()
        expected.sort()
        
        status = "PASS" if result == expected else "FAIL"
        print(f"Prompt: '{prompt}' -> Targets: {result} [{status}]")

if __name__ == "__main__":
    main()
