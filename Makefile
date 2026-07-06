# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

export GOOGLE_CLOUD_PROJECT = project-ef11c640-f8c3-4a2c-a6b
export GOOGLE_CLOUD_LOCATION = global
export GOOGLE_GENAI_USE_VERTEXAI = False

.PHONY: install playground run generate-traces grade

install:
	uv pip install -e .

playground:
	uv run agents-cli playground --port 8090

run:
	uv run python app/fast_api_app.py

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	uv run agents-cli eval grade --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
