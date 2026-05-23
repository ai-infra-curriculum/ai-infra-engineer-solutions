"""Guided decoding: force the model to return valid JSON matching a schema."""
import httpx


schema = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "temperature_c": {"type": "number"},
        "conditions": {"type": "string", "enum": ["clear", "cloudy", "rainy", "snowy"]},
    },
    "required": ["city", "temperature_c", "conditions"],
}


r = httpx.post("http://localhost:8000/v1/completions", json={
    "model": "mistralai/Mistral-7B-Instruct-v0.2",
    "prompt": "Make up a weather report for Paris in JSON format.",
    "max_tokens": 200,
    "guided_json": schema,
})
print(r.json()["choices"][0]["text"])
