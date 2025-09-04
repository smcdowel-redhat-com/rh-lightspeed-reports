#!/usr/bin/env python3

import requests
import json
import sys
import os
from datetime import datetime
from collections import defaultdict
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

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
            return advisories
            
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

def get_system_status_data():
    """Fetch system data and organize by OS version"""
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
    
    if not systems:
        print("No systems data retrieved")
        return {}
    
    print(f"Successfully retrieved {len(systems)} systems")
    
    # Group systems by OS version
    os_groups = defaultdict(list)
    
    for system in systems:
        attributes = system.get('attributes', {})
        display_name = attributes.get('display_name', 'Unknown')
        system_id = system.get('id', 'No ID')
        os_version = attributes.get('os', 'Unknown OS')
        
        print(f"Processing system: {display_name}")
        
        # Get advisories for this system
        advisories = api.get_system_advisories(system_id)
        has_installable_advisories = len(advisories) > 0
        
        system_data = {
            'system_id': system_id,
            'display_name': display_name,
            'os_version': os_version,
            'has_installable_advisories': has_installable_advisories,
            'advisory_count': len(advisories)
        }
        
        os_groups[os_version].append(system_data)
    
    return dict(os_groups)

def generate_pdf_report(os_groups_data):
    """Generate PDF report with system status grouped by OS version"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"patch_system_status_{timestamp}.pdf"
    
    # Create PDF document
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Add title
    title = Paragraph("Red Hat System Patch Status Report", title_style)
    story.append(title)
    
    # Add generation timestamp
    timestamp_text = f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    timestamp_para = Paragraph(timestamp_text, styles['Normal'])
    story.append(timestamp_para)
    story.append(Spacer(1, 20))
    
    # Calculate overall statistics
    total_systems = sum(len(systems) for systems in os_groups_data.values())
    total_with_advisories = sum(
        sum(1 for system in systems if system['has_installable_advisories'])
        for systems in os_groups_data.values()
    )
    overall_percentage = (total_with_advisories / total_systems * 100) if total_systems > 0 else 0
    
    # Add overall summary
    summary_text = f"<b>Overall Summary:</b><br/>"
    summary_text += f"Total Systems: {total_systems}<br/>"
    summary_text += f"Systems with Installable Advisories: {total_with_advisories}<br/>"
    summary_text += f"Percentage with Advisories: {overall_percentage:.1f}%"
    
    summary_para = Paragraph(summary_text, styles['Normal'])
    story.append(summary_para)
    story.append(Spacer(1, 20))
    
    # Process each OS version group
    for os_version, systems in sorted(os_groups_data.items()):
        # Calculate statistics for this group
        total_in_group = len(systems)
        with_advisories = sum(1 for system in systems if system['has_installable_advisories'])
        percentage = (with_advisories / total_in_group * 100) if total_in_group > 0 else 0
        
        # Add group header
        group_header = f"{os_version} ({total_in_group} systems, {percentage:.1f}% with advisories)"
        header_para = Paragraph(group_header, heading_style)
        story.append(header_para)
        
        # Create table data
        table_data = [['System Name', 'System ID', 'Advisory Count', 'Status']]
        
        for system in sorted(systems, key=lambda x: x['display_name']):
            status = "Has Advisories" if system['has_installable_advisories'] else "No Advisories"
            table_data.append([
                system['display_name'],
                system['system_id'][:20] + '...' if len(system['system_id']) > 20 else system['system_id'],
                str(system['advisory_count']),
                status
            ])
        
        # Create and style table
        table = Table(table_data, colWidths=[2.5*inch, 2*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        # Add alternating row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
                ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Build PDF
    try:
        doc.build(story)
        print(f"\nPDF report generated successfully: {filename}")
        return filename
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        return None

def main():
    print("Red Hat System Patch Status Report Generator")
    print("=" * 50)
    
    # Get system data grouped by OS version
    os_groups_data = get_system_status_data()
    
    if not os_groups_data:
        print("No system data available to generate report")
        sys.exit(1)
    
    # Display console summary
    print("\n" + "=" * 50)
    print("SYSTEM STATUS SUMMARY BY OS VERSION")
    print("=" * 50)
    
    for os_version, systems in sorted(os_groups_data.items()):
        total_in_group = len(systems)
        with_advisories = sum(1 for system in systems if system['has_installable_advisories'])
        percentage = (with_advisories / total_in_group * 100) if total_in_group > 0 else 0
        
        print(f"\n{os_version}:")
        print(f"  Total systems: {total_in_group}")
        print(f"  Systems with advisories: {with_advisories}")
        print(f"  Percentage with advisories: {percentage:.1f}%")
        
        for system in sorted(systems, key=lambda x: x['display_name']):
            status = "✓" if system['has_installable_advisories'] else "✗"
            print(f"    {status} {system['display_name']} ({system['advisory_count']} advisories)")
    
    # Generate PDF report
    print(f"\nGenerating PDF report...")
    pdf_filename = generate_pdf_report(os_groups_data)
    
    if pdf_filename:
        print(f"Report generation completed successfully!")
        print(f"PDF saved as: {pdf_filename}")
    else:
        print("Failed to generate PDF report")

if __name__ == "__main__":
    main()