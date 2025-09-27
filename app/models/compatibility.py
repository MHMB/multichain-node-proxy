"""
Compatibility checking utilities for API responses.
This module helps ensure backward compatibility when making changes to response models.
"""
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, ValidationError, Field, ConfigDict
import json
from datetime import datetime


class CompatibilityChecker:
    """Utility class for checking API response compatibility."""
    
    def __init__(self):
        self.response_models = {}
        self.version_history = {}
    
    def register_model(self, name: str, model_class: BaseModel, version: str = "1.0.0"):
        """Register a response model for compatibility checking."""
        if name not in self.response_models:
            self.response_models[name] = {}
        self.response_models[name][version] = model_class
    
    def validate_response(self, model_name: str, data: Dict[str, Any], version: str = "1.0.0") -> bool:
        """Validate response data against a specific model version."""
        if model_name not in self.response_models:
            raise ValueError(f"Model {model_name} not registered")
        
        if version not in self.response_models[model_name]:
            raise ValueError(f"Version {version} not found for model {model_name}")
        
        try:
            model_class = self.response_models[model_name][version]
            model_class(**data)
            return True
        except ValidationError as e:
            print(f"Validation error for {model_name} v{version}: {e}")
            return False
    
    def check_backward_compatibility(self, model_name: str, old_version: str, new_version: str) -> Dict[str, Any]:
        """Check if new version is backward compatible with old version."""
        if model_name not in self.response_models:
            raise ValueError(f"Model {model_name} not registered")
        
        old_model = self.response_models[model_name].get(old_version)
        new_model = self.response_models[model_name].get(new_version)
        
        if not old_model or not new_model:
            raise ValueError(f"Models not found for {model_name} versions {old_version} and {new_version}")
        
        # Get field information
        old_fields = set(old_model.model_fields.keys())
        new_fields = set(new_model.model_fields.keys())
        
        # Check for removed fields
        removed_fields = old_fields - new_fields
        
        # Check for added fields
        added_fields = new_fields - old_fields
        
        # Check for field type changes
        field_type_changes = []
        common_fields = old_fields & new_fields
        
        for field in common_fields:
            old_field_info = old_model.model_fields[field]
            new_field_info = new_model.model_fields[field]
            
            if old_field_info.annotation != new_field_info.annotation:
                field_type_changes.append({
                    "field": field,
                    "old_type": str(old_field_info.annotation),
                    "new_type": str(new_field_info.annotation)
                })
        
        return {
            "compatible": len(removed_fields) == 0 and len(field_type_changes) == 0,
            "removed_fields": list(removed_fields),
            "added_fields": list(added_fields),
            "field_type_changes": field_type_changes,
            "breaking_changes": len(removed_fields) > 0 or len(field_type_changes) > 0
        }
    
    def generate_compatibility_report(self, model_name: str) -> Dict[str, Any]:
        """Generate a comprehensive compatibility report for a model."""
        if model_name not in self.response_models:
            raise ValueError(f"Model {model_name} not registered")
        
        versions = sorted(self.response_models[model_name].keys())
        report = {
            "model_name": model_name,
            "versions": versions,
            "compatibility_matrix": {},
            "breaking_changes": [],
            "recommendations": []
        }
        
        # Check compatibility between all version pairs
        for i, old_version in enumerate(versions):
            for new_version in versions[i+1:]:
                compatibility = self.check_backward_compatibility(model_name, old_version, new_version)
                report["compatibility_matrix"][f"{old_version} -> {new_version}"] = compatibility
                
                if not compatibility["compatible"]:
                    report["breaking_changes"].append({
                        "from_version": old_version,
                        "to_version": new_version,
                        "issues": compatibility
                    })
        
        # Generate recommendations
        if report["breaking_changes"]:
            report["recommendations"].append("Consider creating a new API version for breaking changes")
            report["recommendations"].append("Add migration guides for clients")
        
        return report


# Global compatibility checker instance
compatibility_checker = CompatibilityChecker()

# Register current models
from .responses import (
    WalletInfoResponse, 
    TransactionsListResponse, 
    ContractDetailsResponse,
    Transaction,
    NativeToken,
    WalletToken,
    TxnTokenBalance
)

# Register models with current version
compatibility_checker.register_model("WalletInfoResponse", WalletInfoResponse, "1.0.0")
compatibility_checker.register_model("TransactionsListResponse", TransactionsListResponse, "1.0.0")
compatibility_checker.register_model("ContractDetailsResponse", ContractDetailsResponse, "1.0.0")
compatibility_checker.register_model("Transaction", Transaction, "1.0.0")
compatibility_checker.register_model("NativeToken", NativeToken, "1.0.0")
compatibility_checker.register_model("WalletToken", WalletToken, "1.0.0")
compatibility_checker.register_model("TxnTokenBalance", TxnTokenBalance, "1.0.0")


def validate_service_response(service_name: str, endpoint: str, data: Dict[str, Any]) -> bool:
    """Validate a service response against the appropriate model."""
    model_mapping = {
        "wallet_info": "WalletInfoResponse",
        "transactions_list": "TransactionsListResponse", 
        "contract_details": "ContractDetailsResponse"
    }
    
    model_name = model_mapping.get(endpoint)
    if not model_name:
        raise ValueError(f"No model mapping found for endpoint: {endpoint}")
    
    return compatibility_checker.validate_response(model_name, data)


def check_api_compatibility() -> Dict[str, Any]:
    """Check overall API compatibility and return a report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "models": {},
        "overall_compatible": True,
        "recommendations": []
    }
    
    for model_name in compatibility_checker.response_models.keys():
        model_report = compatibility_checker.generate_compatibility_report(model_name)
        report["models"][model_name] = model_report
        
        if model_report["breaking_changes"]:
            report["overall_compatible"] = False
    
    if not report["overall_compatible"]:
        report["recommendations"].append("Review breaking changes before deploying")
        report["recommendations"].append("Consider versioning strategy")
    
    return report

