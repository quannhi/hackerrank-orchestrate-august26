# Results

Out of 22,000+ total registrations and nearly 2000 submissions, this one ranked 649th

This was my first ever attempt at a hackathon, and it proved to be a valuable learning experience

There is still much to be learned, I am looking forward to future orchestrates and hackathons!
# Inbox Intelligence Agent

A hybrid AI message routing system that automatically filters, prioritizes, and explains incoming messages using deterministic rules, retrieval-augmented reasoning, and a Large Language Model.

---

## Overview

Modern messaging platforms overwhelm users with hundreds of notifications every day. Most messages are either spam, promotions, routine business updates, or low-priority conversations.

This project automatically classifies every incoming message into one of three actions:

*  **Notify** – Important messages requiring immediate attention
*  **Digest** – Useful but non-urgent information bundled for later review
*  **Mute** – Spam, scams, phishing attempts, and unwanted broadcasts

Unlike purely rule-based systems or purely LLM-based systems, this project combines both approaches to maximize accuracy while minimizing cost.

---

## Features

* Hybrid Rule-Based + LLM Architecture
* Retrieval-Augmented Generation (RAG)
* High-confidence Regex Filtering
* Scam Detection
* Spam & Chain Message Detection
* Promotion Detection
* Personalized Decision Making using historical interactions
* Explainable AI reasoning
* Confidence scoring
* Evidence retrieval from similar historical messages
* Multimodal support (text, images, voice transcripts)

---

## Pipeline

Incoming Message

↓

High-Confidence Rule Engine

* Scam Detection
* Spam Detection
* Promotion Detection
* Greeting Detection
* Forwarded Message Detection

↓

If confidently classified:

Return immediately

↓

Otherwise

Retrieve Similar Historical Messages (RAG)

↓

Gemini Flash

↓

Decision Generation

↓

CSV Output

---

## Output Format

Each message produces

```
message_id
action
message_type
reason
confidence
evidence_message_ids
```

Example

```
msg_045
notify
event
Courier is waiting outside with a delivery requiring action within ten minutes.
0.96
message_0146;message_0145
```

---


## Hybrid Design

Instead of sending every message to the LLM, deterministic filters first remove obvious cases.

Example:

Regex immediately catches

* OTP phishing
* Chain letters
* Promotional spam

Only ambiguous messages are sent to Gemini.

Advantages:

* Lower latency
* Lower token cost
* Deterministic behavior
* Fewer hallucinations

---

## Retrieval-Augmented Generation

Before reasoning, the system retrieves historically similar conversations.

The LLM therefore reasons using:

* Similar past messages
* Previous user behavior
* Historical replies
* Historical mutes

instead of relying only on the current message.

---

## Confidence Scores

Confidence is represented numerically.

| Score     | Meaning                                                      |
| --------- | ------------------------------------------------------------ |
| 0.95–1.00 | Very high confidence (deterministic or nearly deterministic) |
| 0.85–0.94 | Strong semantic confidence                                   |
| 0.70–0.84 | Moderate confidence                                          |
| <0.70     | Borderline decision                                          |

---

## Explainability

Every decision contains a natural-language explanation.

Example

```
Immediate notification because the message requires user action before a deadline and similar messages historically received prompt replies.
```

This allows users to understand *why* the system made a decision.

---

## Edge Cases Considered

* Quoted phishing messages
* Promotions disguised as personal conversations
* Genuine security warnings mentioning OTPs
* Voice message transcripts
* Image-based reminders
* Personal messages with deadlines
* Verified businesses sending urgent updates
* Historical user behavior conflicting with message urgency

---

## Technologies

* Python
* Gemini Flash
* Regex
* Retrieval-Augmented Generation (RAG)
* CSV Processing

---

## Future Improvements

* OCR for image understanding
* Calendar integration
* User-adjustable routing preferences
* Better confidence calibration
* Active learning from user feedback

---

## Design Decisions

Rather than replacing deterministic logic with AI, this project uses AI only where human-like semantic reasoning is actually needed.

This results in:

* Faster execution
* Lower cost
* Higher precision
* Explainable decisions
* Robust handling of ambiguous real-world messages

---

## Repository Structure

```text
.
├── dataset/                    # Original dataset files
├── code/
│   ├── rule_engine.py          # Tier 1 Regex logic
│   ├── context_builder.py      # Relational joiner & metric aggregator
│   ├── router_llm.py           # Tier 2 Gemini Flash-Lite LLM engine
│   ├── requirements.txt        # Dependencies
│   └── main.py                 # Full batch execution pipeline
├── output.csv                  # Final generated submission output
├── .env                        # Environment variable configuration
└── README.md                   # System documentation
```

---

## Quickstart

```bash
# 1. Setup virtual environment & activate
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env

# 4. Run full pipeline → generates final output.csv
python code/main.py
```