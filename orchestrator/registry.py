# * MCP Service Registry
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path


# functions:
# register service
# unregister service
# get service by name
# list all services
# find services by data type
# update service status

@dataclass
class MCPService:
    """Represents a registered MCP service"""
    name: str
    url: str
    description: str = ""
    data_types: List[str] = field(default_factory=list) # fhir, dicom, image, patient, etc
    tools: List[str] = field(default_factory=list)  # discovered tools
    status: str = "unknown"  # unknown, online, offline
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_health_check: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MCPService":
        return cls(**data)


class MCPServiceRegistry:
    """
    Registry for MCP services.
    Allows easy registration, discovery, and management of MCP servers.
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._services: Dict[str, MCPService] = {}
        self._persist_path = persist_path or self._default_persist_path()
        self._load()

    def _default_persist_path(self) -> str:
        return str(Path(__file__).parent / "services.json")

    def _load(self) -> None:
        """Load services from persistence file"""
        if os.path.exists(self._persist_path):
            try:
                with open(self._persist_path, "r") as f:
                    data = json.load(f)
                    for name, service_data in data.items():
                        self._services[name] = MCPService.from_dict(service_data)
            except (json.JSONDecodeError, KeyError):
                self._services = {}

    def _save(self) -> None:
        """Persist services to file"""
        data = {name: service.to_dict() for name, service in self._services.items()}
        with open(self._persist_path, "w") as f:
            json.dump(data, f, indent=2)



    def register(
        self,
        name: str,
        url: str,
        description: str = "",
        data_types: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MCPService:
        """
        Register a new MCP service.

        Args:
            name: Unique identifier for the service
            url: Base URL of the MCP server (e.g., "http://localhost:8000")
            description: Human-readable description
            data_types: Types of data this service handles (e.g., ["fhir", "patient"])
            metadata: Additional metadata

        Returns:
            The registered MCPService
        """
        service = MCPService(
            name=name,
            url=url.rstrip("/"),
            description=description,
            data_types=data_types or [],
            metadata=metadata or {},
        )
        self._services[name] = service
        self._save()
        return service

    def unregister(self, name: str) -> bool:
        """Remove a service from the registry"""
        if name in self._services:
            del self._services[name]
            self._save()
            return True
        return False

    def get(self, name: str) -> Optional[MCPService]:
        """Get a service by name"""
        return self._services.get(name)

    def list(self) -> List[MCPService]:
        """List all registered services"""
        return list(self._services.values())

    def find_by_data_type(self, data_type: str) -> List[MCPService]:
        """Find services that handle a specific data type"""
        return [s for s in self._services.values() if data_type in s.data_types]

    def update_status(self, name: str, status: str, tools: Optional[List[str]] = None) -> None:
        """Update service status and discovered tools"""
        if name in self._services:
            self._services[name].status = status
            self._services[name].last_health_check = datetime.now().isoformat()
            if tools is not None:
                self._services[name].tools = tools
            self._save()

    def clear(self) -> None:
        """Clear all services"""
        self._services = {}
        self._save()

    def __len__(self) -> int:
        return len(self._services)

    def __contains__(self, name: str) -> bool:
        return name in self._services

    def __iter__(self):
        return iter(self._services.values())
