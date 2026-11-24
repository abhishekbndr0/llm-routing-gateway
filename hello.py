from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()

response = client.messages.create(model="claude-haiku-5-5", max_tokens=100, messages=[{"role": "user", "content": "Say hello in one short sentence."}])
for block in response.content:
  if block.type == "text":
    print(block.text)

print(f"\n[tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out]")
