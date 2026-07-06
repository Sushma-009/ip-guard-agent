import json

with open("artifacts/traces/generated_traces.json") as f:
    data = json.load(f)

cases = data.get("eval_cases", [])
if cases:
    first_case = cases[0]
    print("KEYS:", list(first_case.keys()))
    print("PROMPT TYPE:", type(first_case.get("prompt")))
    print("RESPONSES TYPE:", type(first_case.get("responses")))
    print("RESPONSES:", first_case.get("responses"))
