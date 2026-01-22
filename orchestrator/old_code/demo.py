#!/usr/bin/env python3
"""
Demo script showing how to use the MCP Service Registry
"""
from registry import MCPServiceRegistry
from client import MCPClient, ToolCall


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def audit_callback(phase: str, tool_call: ToolCall) -> None:
    """Simple audit callback to track all tool calls"""
    if phase == "before":
        print(f"  [AUDIT] Calling {tool_call.service_name}.{tool_call.tool_name}")
        print(f"          Args: {tool_call.arguments}")
    else:
        status = "SUCCESS" if tool_call.success else "FAILED"
        print(f"  [AUDIT] {status}")
        if tool_call.error:
            print(f"          Error: {tool_call.error}")


def main():
    print_header("MCP Service Registry Demo")

    # 1. Create registry
    registry = MCPServiceRegistry()
    print("Created registry")

    # 2. Register multiple MCP servers (any MCP-compatible server works!)
    print_header("Registering Services")

    # FHIR MCP Server (you already have this one)
    fhir_service = registry.register(
        name="fhir",
        url="http://localhost:8000",
        description="FHIR MCP Server - Access to FHIR resources",
        data_types=["fhir", "patient", "observation", "condition"],
        metadata={"version": "1.0", "protocol": "FHIR R4"}
    )
    print(f"Registered: {fhir_service.name} @ {fhir_service.url}")

    # Example: MONAI MCP Server (future - for medical imaging AI)
    monai_service = registry.register(
        name="monai",
        url="http://localhost:8001",
        description="MONAI MCP Server - Medical imaging AI models",
        data_types=["image", "dicom", "segmentation", "mri", "ct"],
        metadata={"version": "1.0", "models": ["DeepEdit", "AbdomenMRI"]}
    )
    print(f"Registered: {monai_service.name} @ {monai_service.url}")

    # Example: RadLex MCP Server (future - for radiology terminology)
    radlex_service = registry.register(
        name="radlex",
        url="http://localhost:8002",
        description="RadLex MCP Server - Radiology lexicon and templates",
        data_types=["terminology", "template", "report"],
        metadata={"version": "1.0", "ontology": "RadLex"}
    )
    print(f"Registered: {radlex_service.name} @ {radlex_service.url}")

    # 3. List services
    print_header("Registered Services")
    for service in registry.list():
        print(f"  - {service.name}: {service.url}")
        print(f"    Description: {service.description}")
        print(f"    Data types: {service.data_types}")
        print(f"    Status: {service.status}")
        print()

    # 4. Find services by data type (routing!)
    print_header("Finding Services by Data Type")

    # This is how the orchestrator knows where to route requests
    patient_services = registry.find_by_data_type("patient")
    print(f"Services handling 'patient' data: {[s.name for s in patient_services]}")

    image_services = registry.find_by_data_type("image")
    print(f"Services handling 'image' data: {[s.name for s in image_services]}")

    template_services = registry.find_by_data_type("template")
    print(f"Services handling 'template' data: {[s.name for s in template_services]}")

    # 5. Create client with audit callback
    print_header("Creating Client")
    client = MCPClient(registry)
    client.add_callback(audit_callback)
    print("Client created with audit callback")

    # 6. Health check
    print_header("Health Check")
    health = client.health_check_all()
    for name, is_healthy in health.items():
        status = "ONLINE" if is_healthy else "OFFLINE"
        print(f"  {name}: {status}")

    # 7. Discover tools for all online services
    print_header("Discovering Tools")
    for service in registry.list():
        if health.get(service.name):  # Only if online
            try:
                tools = client.discover_tools(service.name)
                print(f"[{service.name}] Found {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool.get('name')}: {tool.get('description', '')[:50]}...")
                print()
            except Exception as e:
                print(f"[{service.name}] Error: {e}")

    # 8. Try calling FHIR tool (search for patients)
    print_header("Calling FHIR: search")
    try:
        result = client.call_tool(
            service_name="fhir",
            tool_name="search",
            arguments={"type": "Patient", "searchParam": {"_count": "2"}}
        )
        if isinstance(result, dict) and result.get("resourceType") == "Bundle":
            entries = result.get("entry", [])
            print(f"Found {len(entries)} patients")
            for entry in entries[:2]:
                resource = entry.get("resource", {})
                name = resource.get("name", [{}])[0]
                full_name = f"{name.get('given', [''])[0]} {name.get('family', '')}"
                print(f"  - {full_name} (ID: {resource.get('id')})")
    except Exception as e:
        print(f"Could not call tool: {e}")

    # 9. Try calling MONAI tool (get info)
    print_header("Calling MONAI: get_monai_info")
    try:
        result = client.call_tool(
            service_name="monai",
            tool_name="get_monai_info",
            arguments={}
        )
        if isinstance(result, dict):
            print(f"  MONAI version: {result.get('version')}")
            print(f"  PyTorch version: {result.get('pytorch_version')}")
            print(f"  CUDA available: {result.get('cuda_available')}")
            print(f"  GPU count: {result.get('gpu_count')}")
    except Exception as e:
        print(f"Could not call tool: {e}")

    # 10. Try calling MONAI tool (list models)
    print_header("Calling MONAI: list_models (segmentation)")
    try:
        result = client.call_tool(
            service_name="monai",
            tool_name="list_models",
            arguments={"category": "segmentation"}
        )
        if isinstance(result, dict):
            print(f"Found {result.get('total')} segmentation models:")
            for model in result.get("models", []):
                print(f"  - {model.get('name')}: {model.get('description')}")
    except Exception as e:
        print(f"Could not call tool: {e}")

    # 11. Show updated service status for all
    print_header("All Services Status")
    for service in registry.list():
        print(f"  [{service.name}]")
        print(f"    Status: {service.status}")
        print(f"    Tools: {service.tools}")
        print()

    print_header("Demo Complete")


if __name__ == "__main__":
    main()
