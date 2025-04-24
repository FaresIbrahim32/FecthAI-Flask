import requests
import json

class ASI1Client:
    """
    A simple client for interacting with the ASI1 API via your Flask server
    """
    
    def __init__(self, server_url="http://localhost:5000"):
        """
        Initialize the ASI1 client
        
        Args:
            server_url (str): URL of the Flask server
        """
        self.server_url = server_url
        
    def ask_question(self, question):
        """
        Send a question to the ASI1 AI and get a response
        
        Args:
            question (str): The user's question
            
        Returns:
            str: The AI's response
        """
        try:
            payload = {
                "question": question
            }
            
            # Debug info
            print(f"Sending request to: {self.server_url}/ask")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.server_url}/ask",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Debug info
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response received")
            else:
                error_msg = f"Error: {response.status_code}"
                if response.content:
                    try:
                        error_details = response.json()
                        error_msg += f" - {error_details.get('error', '')}"
                    except:
                        error_msg += f" - {response.text}"
                return error_msg
                
        except Exception as e:
            return f"Error: {str(e)}"


if __name__ == "__main__":
    # Example usage
    print("ASI1 AI Chat Client")
    print("Type 'exit' to quit")
    
    # Create client
    client = ASI1Client()
    
    # Chat loop
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['exit', 'quit']:
            break
        
        response = client.ask_question(user_input)
        print(f"\nASI1: {response}")