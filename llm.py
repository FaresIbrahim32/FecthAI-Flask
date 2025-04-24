from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
import json
import requests

app = Flask(__name__)

class QuestionRequest(BaseModel):
    question: str

class ResponseObject(BaseModel):
    response: str

@app.route('/ask', methods=['POST'])
def ask():
    try:
        question_data = QuestionRequest(**request.json)
        
        HEADERS = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer sk_21b370999a4e40b79302b09273dd39513b9363905b3844698f8052cfa32672e1'
        }
        
        URL = "https://api.asi1.ai/v1/chat/completions"
        
        MODEL = "asi1-mini"
        
        payload = json.dumps({
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": question_data.question
                }
            ],
            "temperature": 0,
            "stream": False,
            "max_tokens": 0
        })
        
        response = requests.request("POST", URL, headers=HEADERS, data=payload)
        
        # Debug info for troubleshooting
        print(f"Request to ASI1 API with question: {question_data.question}")
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return jsonify(ResponseObject(response=content).model_dump())
        else:
            return jsonify({
                "error": f"ASI1 API returned error: {response.status_code}",
                "details": response.json() if response.content else {"error": "Unknown error"}
            }), response.status_code
            
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)