import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import actions
from system_prompt import SYSTEM_PROMPT

# Load environment variables
load_dotenv()

def setup_client():
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY") 
    # Fallback to GOOGLE_API_KEY if users just pasted it there, but encourage OPENROUTER_API_KEY
    
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found.")
        print("Please set it in a .env file: OPENROUTER_API_KEY=sk-or-...")
        return None
        
    # OpenRouter Configuration
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return client

def parse_json_response(text):
    """
    Extracts JSON from the model's response.
    Handles potential markdown code blocks.
    """
    try:
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        return json.loads(clean_text)
    except json.JSONDecodeError:
        return None

def main():
    print("Welcome to the AI Command Interpreter CLI (OpenRouter Edition).")
    print("Type 'exit' or 'quit' to stop.")
    
    client = setup_client()
    if not client:
        return
        
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    while True:
        try:
            user_input = input("\nUser: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if not user_input:
                continue
            
            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            # Call OpenRouter
            # Using google/gemini-2.0-flash-001 as a good default for OpenRouter if available, 
            # otherwise google/gemini-pro-1.5
            completion = client.chat.completions.create(
                model="google/gemini-2.0-flash-001", 
                # Fallback models are handled by OpenRouter routing if configured, 
                # but we must pick a specific string. 
                # If this fails, user might need to change it.
                messages=messages,
                extra_headers={
                    "HTTP-Referer": "https://antigravity.dev", # Optional
                    "X-Title": "Antigravity CLI", # Optional
                }
            )
            
            response_text = completion.choices[0].message.content
            
            # Add assistant response to history
            messages.append({"role": "assistant", "content": response_text})

            # Parse JSON
            command_data = parse_json_response(response_text)
            
            if not command_data:
                print(f"AI (Raw): {response_text}")
                print("Error: Could not parse JSON from AI response.")
                continue
                
            print(f"\nAI Proposal: {json.dumps(command_data, indent=2)}")
            
            action = command_data.get("action")
            file_type = command_data.get("file_type")
            source = command_data.get("source_path")
            dest = command_data.get("destination_path")
            msg = command_data.get("message")
            
            if action == 'error':
                print(f"AI Error: {msg}")
                continue
            
            if action == 'list':
                print(f"Listing files in: {source or 'Home Directory'}...")
                # Note: list_files handles path resolution
                result = actions.list_files(source)
                if isinstance(result, list):
                    print(f"Items found: {len(result)}")
                    for item in result:
                        print(f" {item}")
                else:
                    print(result)

            elif action == 'find':
                # 'find' is generally safe, but we can still ask or just run it.
                # Let's just run it for convenience, or maybe concise output.
                print("Retrieving file list...")
                result = actions.find_files(file_type, source)
                if isinstance(result, list):
                    print(f"Found {len(result)} files:")
                    for f in result:
                        print(f" - {f}")
                else:
                    print(result)
                    
            elif action in ['move', 'delete', 'execute']:
                confirm = input(f"CONFIRM: Do you want to {action} these files? (y/n): ").lower()
                if confirm == 'y':
                    if action == 'move':
                        print(actions.move_files(file_type, dest, source))
                    elif action == 'delete':
                        print(actions.delete_files(file_type, source))
                    elif action == 'execute':
                        target_file = source
                        if not target_file:
                             print("Error: No file specified in source_path for execution.")
                        else:
                             print(actions.execute_python_file(target_file))
                else:
                    print("Action cancelled.")
            else:
                print(f"Unknown action: {action}")

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
