# ruff: noqa
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

import os
import google.auth
from google.auth.exceptions import DefaultCredentialsError

# Load .env file manually if it exists
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip("'\"")
                os.environ[key.strip()] = val

from google.adk.apps import App
from expense_agent.agent import root_agent

try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
            if os.environ.get("GEMINI_API_KEY"):
                os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
                os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
            else:
                os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
                os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
    else:
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
            os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
except DefaultCredentialsError:
    # Gracefully fallback to Google AI Studio (using GEMINI_API_KEY)
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"


app = App(
    root_agent=root_agent,
    name="app",
)
