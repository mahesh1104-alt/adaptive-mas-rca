import ollama

print("Connecting to Ollama...")

response = ollama.chat(
    model="llama3",
    messages=[
        {
            "role": "user",
            "content": "Say hello in one short sentence."
        }
    ]
)

print("\nOllama response:")
print(response["message"]["content"])