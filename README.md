# 🛡️ PharmaGuard AI

PharmaGuard AI is an AI-powered pharmaceutical complaint management system built for the Avioa AI Internship Assignment.

The idea behind this project was to simplify how pharmaceutical complaints are handled. Instead of manually reading complaint forms, users can either describe the issue in a chat or upload a complaint PDF. The system extracts the important information, classifies the complaint severity and generates a structured complaint report.

---

## Why We Built This

Pharmaceutical companies receive many complaints related to damaged products, wrong labeling, packaging defects and safety issues.

Managing these complaints manually takes time and increases the chances of missing important details.

This project explores how Large Language Models and AI Agents can assist in collecting complaint information, organizing it into a structured format and helping quality teams prioritize cases.

---

## Features

- AI chatbot for complaint registration
- Upload and analyze complaint PDFs
- Automatic extraction of complaint details
- Intelligent severity classification
- Complaint correction through conversation
- Structured complaint report generation
- Clean dashboard interface built with React

---

## How It Works

The user can either:

- Describe a complaint in the chat
- Upload a complaint PDF

The backend extracts the information and sends it through a LangGraph workflow.

The AI identifies important complaint details such as:

- Customer Name
- Product Name
- Batch Number
- Complaint Description

The system then classifies the complaint as:

- Critical
- Major
- Minor

Finally, the processed complaint is displayed in the Complaint Intelligence Report.

---

## Technology Used

### Frontend

- React
- CSS

### Backend

- FastAPI
- Python

### AI

- LangGraph
- Groq API
- Llama 3.1 8B Instant

### PDF Processing

- PyMuPDF (fitz)

---

## Project Structure

backend/

- FastAPI APIs
- LangGraph workflow
- AI service
- Complaint tools

frontend/

- React application
- Dashboard
- AI Chat Interface

uploads/

- Uploaded complaint PDFs

---

## AI Workflow

User Input

↓

Intent Detection

↓

Chat Response or Complaint Processing

↓

Complaint Extraction

↓

Severity Classification

↓

Complaint Report

---

## Challenges Faced

This project was built step by step and several problems came up during development.

### 1. JSON Parsing Errors

At one point the frontend crashed because invalid data like `"undefined"` was being stored in local storage.

This was solved by adding safe JSON parsing and fallback values.

---

### 2. AI Always Created Complaints

Initially every user message, even something like "Hi", generated a complaint.

To solve this, an intent classifier was added before complaint processing so the system could decide whether the user wanted to chat or submit a complaint.

---

### 3. Complaint Corrections

Another challenge was allowing users to correct information.

For example:

> "Sorry, the product name is VMX instead of CMX."

Instead of creating a new complaint, the system now updates only the changed field while keeping the previous complaint information.

---

### 4. Severity Classification

LLM responses were sometimes inconsistent.

To make severity predictable, a rule-based classifier using pharmaceutical keywords was implemented after AI extraction.

---

### 5. PDF Complaint Analysis

Extracting structured information from uploaded PDFs required text extraction before sending the content to the AI workflow.

PyMuPDF was used for this purpose.

---

## Development Process

This project was developed incrementally instead of writing everything at once.

AI tools were used throughout development for:

- brainstorming ideas
- understanding errors
- improving prompts
- debugging code
- refining the overall workflow

The final architecture, integration between frontend and backend, testing, debugging and project improvements were done manually through multiple iterations.

---

## Future Improvements

Some features that can be added in the future:

- Database integration
- User authentication
- Complaint history
- Email notifications
- Analytics dashboard
- Cloud deployment
- Investigation workflow

---

## Demo

The demo includes:

- AI Complaint Chat
- Complaint Updates
- PDF Analysis
- Severity Classification
- Complaint Intelligence Report

---

## Thank You

This project was developed as part of the Avioa AI Internship Assignment.

It was a great opportunity to explore FastAPI, React, LangGraph and LLM-based workflows while solving a real-world pharmaceutical use case.
