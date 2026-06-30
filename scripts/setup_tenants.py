
import requests
import json
import os

# ==============================================================================
# DEV-ONLY UTILITY: Tenant Registration Script
# ==============================================================================
# This script is used for local development to quickly bootstrap the data-service
# with test tenants. 
#
# WHY IS THIS NEEDED?
# data-service is now multi-tenant and stateless. It doesn't load a static list 
# of tenants from a file; instead, it maintains a dynamic TenantStore in memory.
# When a request arrives with 'X-Tenant-ID', data-service looks up the 
# corresponding DB connection and router.
#
# Without registering a tenant via the /admin/tenants API, the service will 
# return 'tenant_not_found' (404).
#
# WARNING: This script is a test helper. In production, tenants would be 
# managed via a proper Admin Dashboard or automated Provisioning Pipeline.
# ==============================================================================

DATA_SERVICE_URL = "http://127.0.0.1:8084"
DB_PATH = os.path.abspath("university.db")
CONFIG_PATH = os.path.abspath("specs/config.example.json")

def add_tenant(tenant_id, config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # We use absolute paths for DSN to avoid "no such table" errors
    # when data-service is started from different working directories.
    config['data_source']['dsn'] = DB_PATH
    
    payload = {
        "id": tenant_id,
        "config": config,
        "config_path": CONFIG_PATH
    }
    
    try:
        # Authorization is required for /admin endpoints
        resp = requests.post(
            f"{DATA_SERVICE_URL}/admin/tenants", 
            json=payload, 
            headers={"Authorization": "Bearer secret"}
        )
        print(f"Tenant {tenant_id}: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Error adding {tenant_id}: {e}")

if __name__ == "__main__":
    add_tenant("uni-tenant", CONFIG_PATH)
