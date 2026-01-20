# MedGov-AI | Desk Assistance

A Multi-Agent Orchestrator for healthcare, designed to orchestrate different AI services, perform analysis, and ensure interoperability between various systems through existing standards such as HL7, FHIR, and DICOM.

## Context

The Model Context Protocol (MCP) has been gaining traction and is being adopted by major global LLM providers (Gemini, OpenAI, Claude). Healthcare is no exception, with MCP Servers expanding to support different medical protocols.

### Key Challenges

1. **Integration Difficulties** - Medical teams often struggle with tool integration due to time constraints and communication gaps between IT and clinical teams [ElSayed et al.]
2. **LLM Auditability** - LLMs are black boxes, making it difficult to audit their reasoning and ensure compliance with medical guidelines and protocols
3. **Patient-Centric Context** - LLMs have limited context windows and need constant re-feeding to maintain a patient-centric approach

## Objectives

Create a Multi-Agent Orchestrator for healthcare that:
- Orchestrates different AI services and analysis tools
- Ensures interoperability between systems via standards (HL7, FHIR, DICOM)
- Supports electronic prescriptions, MCDT requests, and more

## Features

### Core Capabilities

- **MCP Service Registry** - Easy registration and management of MCP services
- **Multi-Modal Data Handling** - Support for images, prescriptions, clinical notes, and more
- **Natural Language Actions** - Create actions via natural language in an assisted manner (e.g., report/clinical note generation)
- **Patient-Centric Approach** - Explore patient context via LLM with full history awareness
- **Action Auditing** - Audit all LLM actions performed in the patient context

### Health Agent Assistant Protocol (HAAP)

Similar to how the Language Server Protocol (LSP) solves the M×N problem for code editors and programming languages, and the Agent Client Protocol (ACP) does the same for agents and IDEs, we propose a **Health Agent Assistant Protocol** to solve the M'×N' problem in healthcare:

- **M' Applications**: n-PACS, n-RIS, n-EHR systems
- **N' AI Services**: Sycai, Carebot, SmartCare, and others
- **Protocols**: DICOM, HL7, Custom implementations

The goal is to define a protocol that guarantees interoperability between all these systems.

## Use Cases

### Use Case 1: Radiology Report Assistant

**Scenario**: A radiologist needs to report multiple daily exams with different pathologies.

**Components**:
- MONAI models for abdominal MRI segmentation [Harmon et al.]
- Pre-established models (DeepEdit) from MONAI Zoo
- RadLex/RadReport templates (e.g., MR Kidney and Abdomen Renal Mass)

**Objective**: Create an agent-based assisted report that:
- Uses AI-annotated image results
- Applies standardized report templates
- Incorporates patient history
- Suggests content and asks guiding questions

**Required MCP Servers**:
- `mcp-monai` - MONAI integration
- `mcp-radlex` - RadLex/RadReport templates (optional)

### Use Case 2: Clinical Notes with Action Integration

**Scenario**: Clinical notes system with defined actions for integration with other systems.

**Examples**:
- Text: "recommended follow-up in 6 months" → Suggest scheduling new appointment via HL7 FHIR in EHR
- Immuno-hematotherapy workflows

**Requirements**:
- Open-source EHR system
- MCP servers for medical image server or FHIR

### Use Case 3: Research Platform

Continue previous work (Martinho's) with focus on:
- Development integration
- Data/Workspace connections
- Research workflow automation

### Use Case 4: Open/Custom

Example: Vehicle counting in city imagery, or other domain-specific applications.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MedGov-AI Orchestrator                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ MCP Registry│  │ Agent Pool  │  │ Patient Context Manager │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                 Health Agent Assistant Protocol                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ mcp-fhir │ │mcp-monai │ │mcp-dicom │ │ mcp-radlex/other │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │   EHR    │ │   PACS   │ │   RIS    │ │   AI Services    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## References

1. ElSayed, Z., Erickson, C. and Pedapati, E., 2025. *MCP-AI: Protocol-Driven Intelligence Framework for Autonomous Reasoning in Healthcare*. arXiv preprint arXiv:2512.05365.

2. Ehtesham, A., Singh, A. and Kumar, S., 2025. *Enhancing Clinical Decision Support and EHR Insights through LLMs and the Model Context Protocol: An Open-Source MCP-FHIR Framework*. arXiv preprint arXiv:2506.13800.

3. Harmon, S.A., Tetreault, J., Esengur, O.T., Qin, M., Yilmaz, E.C., Chang, V., Yang, D., Xu, Z., Cohen, G., Plum, J. and Sherif, T., 2025. *Based clinical deployment of artificial intelligence algorithm for prostate MRI*. Abdominal Radiology, pp.1-10.

## License

TBD
