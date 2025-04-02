# 🤖 AI Agents Toolkit

Welcome to the **AI Agents Toolkit** – a collection of intelligent agents powered by `OpenAI GPT-4o` via [OpenRouter](https://openrouter.ai), designed to automate tasks like blog writing, calendar management, and intelligent assistance. This repository contains three powerful agents:

- `📓 Blogger.py` – Blog post orchestrator (✨ core feature)
- `🧭 Personal-Assistant.py` – Intelligent calendar scheduler
- `🗓️ Calendar-Modifier.py` – Smart event creation and modification handler

---

## 🔥 Blogger.py (Primary Agent)

A multi-agent system for fully **automated blog post creation**. This tool manages everything from planning the structure to drafting sections and polishing the final blog.

### 🧠 How It Works

1. **Orchestrator Agent** – Analyzes the topic, generates structure, defines tone, and breaks down sections.
2. **Worker Agent** – Writes each blog section based on the defined structure and writing guide.
3. **Reviewer Agent** – Evaluates cohesion, suggests edits, and returns a final polished blog post.

### ✨ Features

- Topic analysis with target audience segmentation
- Section-wise generation using writing styles and length goals
- Seamless integration and flow review with scoring
- Returns structured outputs with final blog post and revision notes

### 🚀 Example

```python
from Blogger import BlogOrchestrator

orchestrator = BlogOrchestrator()
result = orchestrator.write_blog(
    topic="The impact of AI on software development",
    target_length=1200,
    style="technical but accessible"
)

print(result["review"].final_version)
print("Cohesion Score:", result["review"].cohesion_score)
```

## 🧭 personal-assistant.py – Smart Calendar Assistant

An intelligent assistant that **analyzes freeform user input** to determine if it describes a calendar event, then parses and confirms the event in natural language.

---

### 🧠 Pipeline Overview

This agent performs a **3-step intelligent chain**:

1. **Event Extraction**  
   Determines if the input text describes a calendar event with a confidence score.

2. **Event Details Parsing**  
   Extracts specific details like event name, date, time, duration, and participants.

3. **Confirmation Generation**  
   Generates a friendly confirmation message with optional calendar link.

---

### ✅ Example

```python
from personal_assistant import process_calendar_request

input_text = "Let's schedule a 1h team meeting next Tuesday at 2pm with Alice and Bob."
result = process_calendar_request(input_text)

if result:
    print(f"Confirmation: {result.confirmation_message}")
else:
    print("This doesn't appear to be a calendar event.")
```

## 🗓️ calendar-modifier.py – Event Routing & Editing Agent

An LLM-powered agent that **routes calendar-related commands** into creation or modification tasks, then handles them intelligently using OpenAI's GPT-4o via OpenRouter.

---

### 🧠 Core Capabilities

1. **🧭 Routing Engine**  
   Determines the intent of the user input and classifies it as:
   - `new_event`
   - `modify_event`
   - `other`

2. **📅 New Event Handler**  
   - Extracts detailed information about a new event (name, date, duration, participants).
   - Returns a success message and a mock calendar link.

3. **🔁 Modify Event Handler**  
   - Identifies which event to modify based on user input.
   - Supports field changes and participant updates.
   - Responds with a confirmation message and update status.

---

### ✅ Usage Example

```python
from calendar_modifier import process_calendar_request

# New Event Example
new_input = "Schedule a team sync next Thursday at 10am with Alice."
result = process_calendar_request(new_input)
if result:
    print(result.message)

# Modify Event Example
modify_input = "Move our team sync to Friday at 11am."
result = process_calendar_request(modify_input)
if result:
    print(result.message)
```
