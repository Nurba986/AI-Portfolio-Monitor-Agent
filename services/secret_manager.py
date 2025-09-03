"""
Secret Manager Service
Handles environment variables and secrets for both local and cloud environments.

Local Development:
- Loads from .env.yaml file for convenience
- Falls back to environment variables

Production (Google Cloud Functions):
- Uses Google Cloud Secret Manager
- Falls back to environment variables for configuration

Security Features:
- Never logs secret values
- Validates required secrets
- Provides clear error messages for missing configuration
"""

import os
import logging
from typing import Dict, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

try:
    from google.cloud import secretmanager
    GCP_SECRET_MANAGER_AVAILABLE = True
except ImportError:
    GCP_SECRET_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)

class SecretManager:
    """Unified secret management for local and cloud environments"""
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self.is_cloud_environment = self._detect_cloud_environment()
        self._secret_client = None
        
        # Cache for secrets to avoid repeated API calls
        self._secret_cache: Dict[str, str] = {}
        
        if not self.is_cloud_environment:
            self._load_local_env()
    
    def _detect_cloud_environment(self) -> bool:
        """Detect if running in Google Cloud environment"""
        cloud_indicators = [
            'GOOGLE_CLOUD_PROJECT',
            'GAE_APPLICATION',
            'FUNCTION_NAME',
            'K_SERVICE'  # Cloud Run
        ]
        return any(os.environ.get(indicator) for indicator in cloud_indicators)
    
    def _get_secret_client(self):
        """Lazy initialization of Secret Manager client"""
        if self._secret_client is None and GCP_SECRET_MANAGER_AVAILABLE:
            try:
                self._secret_client = secretmanager.SecretManagerServiceClient()
            except Exception as e:
                logger.warning(f"Failed to initialize Secret Manager client: {e}")
        return self._secret_client
    
    def _load_local_env(self):
        """Load environment variables from .env.yaml for local development"""
        try:
            env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.yaml')
            if os.path.exists(env_file):
                if yaml:
                    with open(env_file, 'r') as f:
                        env_vars = yaml.safe_load(f)
                        if env_vars:
                            for key, value in env_vars.items():
                                # Don't override existing environment variables
                                if key not in os.environ:
                                    os.environ[key] = str(value)
                            logger.info(f"✅ Loaded {len(env_vars)} environment variables from .env.yaml")
                else:
                    # Manual parsing if PyYAML not available
                    with open(env_file, 'r') as f:
                        env_count = 0
                        for line in f:
                            line = line.strip()
                            if ':' in line and not line.startswith('#') and line:
                                try:
                                    key, value = line.split(':', 1)
                                    key = key.strip()
                                    value = value.strip().strip('"').strip("'")
                                    if key not in os.environ:
                                        os.environ[key] = value
                                        env_count += 1
                                except ValueError:
                                    continue
                        if env_count > 0:
                            logger.info(f"✅ Loaded {env_count} environment variables from .env.yaml (manual parsing)")
            else:
                logger.info("ℹ️ No .env.yaml file found - using system environment variables only")
        except Exception as e:
            logger.warning(f"Failed to load local environment file: {e}")
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Get secret value from appropriate source
        
        Priority:
        1. Cache (if already retrieved)
        2. Google Cloud Secret Manager (if in cloud environment)
        3. Environment variables
        """
        cache_key = f"{secret_name}_{version}"
        
        # Check cache first
        if cache_key in self._secret_cache:
            return self._secret_cache[cache_key]
        
        secret_value = None
        
        # Try Google Cloud Secret Manager first if in cloud environment
        if self.is_cloud_environment and self.project_id and GCP_SECRET_MANAGER_AVAILABLE:
            secret_value = self._get_from_secret_manager(secret_name, version)
        
        # Fall back to environment variables
        if not secret_value:
            secret_value = os.environ.get(secret_name)
        
        # Cache the result if found
        if secret_value:
            self._secret_cache[cache_key] = secret_value
        
        return secret_value
    
    def _get_from_secret_manager(self, secret_name: str, version: str) -> Optional[str]:
        """Retrieve secret from Google Cloud Secret Manager"""
        try:
            client = self._get_secret_client()
            if not client:
                return None
            
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = client.access_secret_version(request={"name": name})
            
            secret_value = response.payload.data.decode("UTF-8")
            logger.info(f"✅ Retrieved secret '{secret_name}' from Secret Manager")
            return secret_value
            
        except Exception as e:
            logger.warning(f"Failed to retrieve secret '{secret_name}' from Secret Manager: {e}")
            return None
    
    def get_required_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Get required secret value, raise exception if not found
        """
        secret_value = self.get_secret(secret_name, version)
        if not secret_value:
            available_sources = []
            if self.is_cloud_environment:
                available_sources.append("Google Cloud Secret Manager")
            available_sources.append("Environment Variables")
            
            raise ValueError(
                f"Required secret '{secret_name}' not found. "
                f"Checked: {', '.join(available_sources)}. "
                f"Environment: {'Cloud' if self.is_cloud_environment else 'Local'}"
            )
        
        return secret_value
    
    def validate_required_secrets(self, required_secrets: list) -> Dict[str, Any]:
        """
        Validate that all required secrets are available
        Returns dict with validation results
        """
        results = {
            'valid': True,
            'missing_secrets': [],
            'found_secrets': [],
            'environment': 'Cloud' if self.is_cloud_environment else 'Local'
        }
        
        for secret_name in required_secrets:
            try:
                secret_value = self.get_required_secret(secret_name)
                results['found_secrets'].append(secret_name)
                # Log that we found it without exposing the value
                logger.info(f"✅ Secret '{secret_name}' is available")
            except ValueError:
                results['valid'] = False
                results['missing_secrets'].append(secret_name)
                logger.error(f"❌ Missing required secret: '{secret_name}'")
        
        return results


# Global instance for easy access
secret_manager = SecretManager()

def get_secret(secret_name: str, version: str = "latest") -> Optional[str]:
    """Convenience function to get secret"""
    return secret_manager.get_secret(secret_name, version)

def get_required_secret(secret_name: str, version: str = "latest") -> str:
    """Convenience function to get required secret"""
    return secret_manager.get_required_secret(secret_name, version)

def validate_secrets() -> Dict[str, Any]:
    """Validate all required secrets for the portfolio application"""
    required_secrets = [
        'GMAIL_USER',
        'GMAIL_PASSWORD', 
        'CLAUDE_API_KEY'
    ]
    
    return secret_manager.validate_required_secrets(required_secrets)