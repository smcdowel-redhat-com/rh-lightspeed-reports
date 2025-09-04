#!/usr/bin/env python3

import requests
import json
import sys
import os
from datetime import datetime

class RedHatPatchAPI:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
        self.patch_api_url = "https://console.redhat.com/api/patch/v3/systems"
        self.access_token = None
    
    def get_oauth_token(self):
        """Refresh OAuth token using client credentials"""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting OAuth token: {e}")
            return None
    
    def get_patch_systems(self):
        """Fetch systems data from Red Hat Patch API"""
        if not self.access_token:
            print("No access token available. Please refresh token first.")
            return []
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(self.patch_api_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            systems = data.get('data', [])
            return systems
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching patch systems: {e}")
            return []
    
    def get_system_advisories(self, inventory_id):
        """Fetch advisories for a specific system"""
        if not self.access_token:
            print("No access token available. Please refresh token first.")
            return []
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        advisories_url = f"https://console.redhat.com/api/patch/v3/systems/{inventory_id}/advisories"
        
        try:
            response = requests.get(advisories_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            advisories = data.get('data', [])
            
            # Extract advisory IDs and synopsis
            advisory_list = []
            for advisory in advisories:
                advisory_info = {
                    'id': advisory.get('id', 'Unknown'),
                    'synopsis': advisory.get('attributes', {}).get('synopsis', 'No synopsis')
                }
                advisory_list.append(advisory_info)
            
            return advisory_list
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching advisories for system {inventory_id}: {e}")
            return []

def load_config(config_file='config.json'):
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config['redhat_api']['client_id'], config['redhat_api']['client_secret']
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing configuration key {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)

def main():
    client_id, client_secret = load_config()
    
    api = RedHatPatchAPI(client_id, client_secret)
    
    print("Refreshing OAuth token...")
    token = api.get_oauth_token()
    if not token:
        print("Failed to get OAuth token")
        sys.exit(1)
    
    print("Token refreshed successfully")
    
    print("Fetching patch systems data...")
    systems = api.get_patch_systems()
    
    systems_with_advisories = []
    
    if systems:
        print(f"Successfully retrieved {len(systems)} systems")
        print("\nSystems data and advisories:")
        
        for i, system in enumerate(systems):
            display_name = system.get('attributes', {}).get('display_name', 'Unknown')
            system_id = system.get('id', 'No ID')
            
            print(f"\n{i+1}. {display_name} - {system_id}")
            
            # Get advisories for this system
            advisories = api.get_system_advisories(system_id)
            
            system_data = {
                'system_id': system_id,
                'display_name': display_name,
                'advisories': advisories
            }
            systems_with_advisories.append(system_data)
            
            if advisories:
                print(f"   Found {len(advisories)} advisories:")
                for j, advisory in enumerate(advisories[:3]):  # Show first 3 advisories
                    print(f"   - {advisory['id']}: {advisory['synopsis'][:100]}...")
                if len(advisories) > 3:
                    print(f"   ... and {len(advisories) - 3} more advisories")
            else:
                print("   No advisories found")
    else:
        print("No systems data retrieved")
    
    return systems_with_advisories

def print_advisory_report(systems_data):
    """Print a detailed report of systems and their advisories"""
    print("\n" + "="*80)
    print("RED HAT PATCH ADVISORY REPORT")
    print("="*80)
    
    for system in systems_data:
        system_id = system['system_id']
        display_name = system['display_name']
        advisories = system['advisories']
        
        print(f"\nSYSTEM: {display_name}")
        print(f"ID: {system_id}")
        print(f"ADVISORIES COUNT: {len(advisories)}")
        print("-" * 60)
        
        if advisories:
            for i, advisory in enumerate(advisories, 1):
                print(f"{i:2d}. {advisory['id']}")
                print(f"    Synopsis: {advisory['synopsis']}")
                print()
        else:
            print("    No advisories found for this system")
            print()

def generate_json_report(systems_data):
    """Generate JSON report with system names as top attributes"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"patch_api_report_{timestamp}.json"
    
    json_report = {}
    
    for system in systems_data:
        system_name = system['display_name']
        advisories_list = []
        
        for advisory in system['advisories']:
            advisory_entry = {
                "advisory_id": advisory['id'],
                "synopsis": advisory['synopsis']
            }
            advisories_list.append(advisory_entry)
        
        json_report[system_name] = {
            "system_id": system['system_id'],
            "advisory_count": len(advisories_list),
            "advisories": advisories_list
        }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        print(f"\nJSON report saved to: {filename}")
        return filename
    except Exception as e:
        print(f"Error saving JSON report: {e}")
        return None

if __name__ == "__main__":
    systems_array = main()
    print_advisory_report(systems_array)
    generate_json_report(systems_array)