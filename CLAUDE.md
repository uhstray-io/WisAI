# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WisAI is an LLM Agentic Development Team designed to support business-as-code platforms, services, and data. The system consists of multiple specialized AI agents that collaborate to handle different aspects of software development using LangGraph for orchestration.

## Development Commands

### Primary Commands
- `uv sync` - Install dependencies for the project
- `uv run main.py` - Run the main application
- `uv run python -m pytest` - Run tests (inferred from Python project structure)

### Environment Setup
- The project uses `.env` files for environment configuration
- Key environment variables: `REASONING_LLM`, `GOOGLE_API_KEY`
- Default reasoning LLM: `HF1BitLLM/Llama3-8B-1.58-100B`

### LangGraph Development
- `langgraph serve` - Start LangGraph server (API at http://localhost:2024)
- LangGraph Studio Web UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- Configuration files: `inferencing/langgraph.json`, `inferencing/config.json`

## Architecture Overview

### Multi-Workspace Structure
- **inferencing/**: Core agent system with LangGraph workflows
- **modeling/**: Model quantization and optimization (AWQ, BitNet)
- **infrastructure/**: Docker and Kubernetes deployment configurations

### Agent Architecture
The system follows a hierarchical agent structure:

1. **Design LLMs**: Scrum Master, Solutions Architect, Data Scientist, Requirements Researcher
2. **Development LLMs**: UX/UI Engineer, Backend Engineer, Data Engineer  
3. **Operations LLMs**: DevSecOps Engineer, Automation Engineer, Reporting Analyst

### Core Components

#### Base Agent System (`inferencing/agents/base_agent.py`)
- Abstract base class for all agents with LangGraph integration
- Shared functionality: state management, inter-agent handoffs
- Required implementations: `_build_graph()` method

#### State Management (`inferencing/state/`)
- `schemas.py`: Pydantic models for state definitions
- `store.py`: State store interface for shared data
- Uses TypedDict for LangGraph state definitions

#### Agent Communication (`inferencing/comms/`)
- `handoffs.py`: Inter-agent communication protocols
- Supports asynchronous agent-to-agent task delegation

### LangGraph Configuration
- Supervisor system with multiple workflow graphs
- State-based workflows with checkpointing support
- Vector store integration for content indexing (OpenAI embeddings)

## Key Technologies

### Dependencies (inferencing/)
- **LangGraph**: `langgraph>=0.5.1` - Workflow orchestration
- **LangChain**: Multiple providers (Anthropic, Google Gemini, Tavily)
- **VLLM**: `vllm>=0.9.1` - Local LLM inference
- **Pydantic**: `>=2.11.7` - Data validation and serialization

### Dependencies (modeling/)
- **VLLM**: `>=0.6.3` - Model serving
- **LLMCompressor**: `>=0.6.0` - Model optimization
- **Datasets**: `>=3.6.0` - Data handling

## Development Patterns

### Agent Development
1. Inherit from `BaseAgent` class
2. Implement `_build_graph()` method with LangGraph StateGraph
3. Define agent-specific state schemas using TypedDict
4. Use async/await patterns for state updates and handoffs

### Workflow Structure
- Entry point typically starts with user request parsing
- Sequential processing through requirement generation, design, story creation
- Task assignment and validation as final steps
- All workflows end at `END` node

### State Design
- Public state for inter-agent communication
- Private state for internal agent processing
- Sanitized result sharing between agents

## Testing Structure
- Test files located alongside source code (e.g., `test_graph.py`, `test_node.py`)
- Agent-specific test directories under each agent folder
- Integration tests for LangGraph workflows

## Model Configuration
- Target models: Phi-3.5-mini-instruct, Nemotron family, Falcon-3-10B
- Quantization support: BitBLAS, AWQ quantization
- Local inference optimization for energy efficiency
- Model paths configurable via environment variables