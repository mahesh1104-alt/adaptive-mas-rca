import ollama


def ollama_llm(prompt: str):
    response = ollama.chat(
        model="llama3",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        
    )
    return response["message"]["content"]