import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import base64
import zipfile
import plotly.express as px  # Import missing library
import plotly.graph_objects as go # Import missing library
import urllib3

# Suppress only the single InsecureRequestWarning from urllib3 needed for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration and Security Settings
N8N_URL = f"https://agentonline-u29564.vm.elestio.app"
N8N_API_USER = "root"
N8N_API_PASS = "8QRlr4ex-IomJ-4njKSVSX"

# Enhanced API Functions
def make_api_request(method, endpoint, data=None, params=None):
    """Generic API request handler with error handling"""
    headers = {'Accept': 'application/json'}
    if data:
        headers['Content-Type'] = 'application/json'

    auth = (N8N_API_USER, N8N_API_PASS)
    url = f"{N8N_URL}/api/v1/{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            auth=auth,
            json=data if data else None,
            params=params,
            verify=False,
            timeout=10  # Add a timeout to prevent hanging
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Failed: {e}")
        return None

def get_workflows():
    """Fetch all workflows with error handling"""
    response = make_api_request('GET', 'workflows')
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch workflows.")
        return None

def get_workflow_executions(workflow_id, limit=100):
    """Fetch execution history for a workflow with error handling"""
    params = {'limit': limit}
    response = make_api_request('GET', f'workflows/{workflow_id}/executions', params=params)
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch executions for workflow ID {workflow_id}.")
        return None

def execute_workflow(workflow_id, data=None):
    """Trigger workflow execution with error handling"""
    response = make_api_request('POST', f'workflows/{workflow_id}/execute', data=data)
    if response and response.status_code == 200:
        return True
    else:
        st.error(f"Failed to execute workflow ID {workflow_id}.")
        return False

def get_tags():
    """Fetch all tags with error handling"""
    response = make_api_request('GET', 'tags')
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch tags.")
        return None

def create_tag(tag_name):
    """Create a new tag with error handling"""
    data = {'name': tag_name}
    response = make_api_request('POST', 'tags', data=data)
    if response and response.status_code == 200:
        return True
    else:
        st.error(f"Failed to create tag '{tag_name}'.")
        return False

def get_credentials():
    """Fetch credentials list (names only) with error handling"""
    response = make_api_request('GET', 'credentials')
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch credentials.")
        return None

def get_active_workflows():
    """Get all active workflows with error handling"""
    response = make_api_request('GET', 'workflows/active')
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch active workflows.")
        return None

def activate_workflow(workflow_id, active=True):
    """Activate or deactivate a workflow with error handling"""
    data = {'active': active}
    response = make_api_request('PATCH', f'workflows/{workflow_id}', data=data)
    if response and response.status_code == 200:
        return True
    else:
        st.error(f"Failed to {'activate' if active else 'deactivate'} workflow ID {workflow_id}.")
        return False

def get_workflow_metrics(workflow_id):
    """Get execution metrics for a workflow"""
    executions = get_workflow_executions(workflow_id)
    if not executions:
        return None

    success_count = sum(1 for e in executions if e.get('finished') and e.get('status') == 'success')
    failure_count = sum(1 for e in executions if e.get('finished') and e.get('status') == 'error')

    total_executions = len(executions)
    success_rate = (success_count / total_executions) * 100 if total_executions else 0
    failure_rate = (failure_count / total_executions) * 100 if total_executions else 0

    return {
        'total_executions': total_executions,
        'success_rate': success_rate,
        'failure_rate': failure_rate,
    }

# New Visualization Functions
def create_execution_timeline(executions):
    """Create timeline visualization of workflow executions"""
    df = pd.DataFrame([{
        'Started': datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00')),
        'Status': e['status'],
        'Duration': e.get('stoppedAt', None) and
                   (datetime.fromisoformat(e['stoppedAt'].replace('Z', '+00:00')) -
                    datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00'))).seconds
    } for e in executions])

    fig = px.scatter(df, x='Started', y='Duration',
                    color='Status',
                    title='Execution Timeline',
                    labels={'Started': 'Execution Time',
                            'Duration': 'Duration (seconds)'},
                    hover_data=['Status'])
    return fig

def create_success_rate_gauge(metrics):
    """Create gauge chart for success rate"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=metrics['success_rate'],
        title={'text': "Success Rate"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkgreen"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "gray"},
                {'range': [80, 100], 'color': "lightgreen"}
            ],
        }
    ))
    return fig

def create_daily_execution_chart(executions):
    """Create daily execution count chart"""
    df = pd.DataFrame([{
        'Date': datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00')).date(),
        'Status': e['status']
    } for e in executions])

    daily_counts = df.groupby(['Date', 'Status']).size().unstack(fill_value=0)
    fig = px.bar(daily_counts, barmode='group',
                 title='Daily Execution Counts',
                 labels={'value': 'Number of Executions',
                         'Date': 'Date'})
    return fig

# New Backup Functions
def export_workflow(workflow_id):
    """Export a single workflow with error handling"""
    response = make_api_request('GET', f'workflows/{workflow_id}')
    if response and response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to export workflow ID {workflow_id}.")
        return None

def create_backup_file(workflows):
    """Create a backup file containing all workflows"""
    backup_data = {
        'workflows': [],
        'timestamp': datetime.now().isoformat(),
        'metadata': {
            'total_workflows': len(workflows),
            'backup_version': '1.0'
        }
    }

    for workflow in workflows:
        workflow_data = export_workflow(workflow['id'])
        if workflow_data:
            backup_data['workflows'].append(workflow_data)

    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add workflows JSON
        zip_file.writestr('workflows.json',
                         json.dumps(backup_data, indent=2))

        # Add metadata file
        metadata = {
            'backup_date': backup_data['timestamp'],
            'workflow_count': len(backup_data['workflows']),
            'source_instance': N8N_URL
        }
        zip_file.writestr('metadata.json',
                         json.dumps(metadata, indent=2))

    return zip_buffer.getvalue()

def restore_workflow(workflow_data):
    """Restore a workflow from backup"""
    workflow_id = workflow_data.get('id')
    # Remove fields that shouldn't be included in restore
    for field in ['id', 'createdAt', 'updatedAt']:
        workflow_data.pop(field, None)

    response = make_api_request('POST', 'workflows', data=workflow_data)
    if response and response.status_code == 201:  # Assuming 201 Created on success
        return True
    else:
        st.error(f"Failed to restore workflow '{workflow_data.get('name', 'Unknown')}'")
        return False

def main():
    st.set_page_config(page_title="N8N Workflow Manager", layout="wide")

    # Authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if username == N8N_API_USER and password == N8N_API_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        return

    st.title("N8N Workflow Manager")

    tabs = st.tabs([
        "Workflows", "Executions", "Advanced Metrics",
        "Backup & Restore", "Tags", "Credentials"
    ])

    workflows = get_workflows()  # Fetch workflows only once

    with tabs[0]:
        st.header("Workflow Management")
        if workflows:
            for workflow in workflows:
                with st.expander(f"{workflow['name']} (ID: {workflow['id']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"Active: {'✅' if workflow['active'] else '❌'}")
                        if st.button(
                            "Toggle Active Status",
                            key=f"toggle_{workflow['id']}"
                        ):
                            if activate_workflow(workflow['id'], not workflow['active']):
                                st.success("Status updated!")
                                st.rerun()

                    with col2:
                        if st.button(
                            "Execute Workflow",
                            key=f"execute_{workflow['id']}"
                        ):
                            if execute_workflow(workflow['id']):
                                st.success("Workflow executed!")
        else:
            st.info("No workflows found.")

    with tabs[1]:
        st.header("Execution History")
        if workflows:
            workflow_names = [w['name'] for w in workflows]
            selected_workflow_name = st.selectbox(
                "Select Workflow",
                options=workflow_names,
                key="execution_workflow_selector"
            )
            selected_workflow = next((w for w in workflows if w['name'] == selected_workflow_name), None)

            if selected_workflow:
                workflow_id = selected_workflow['id']
                executions = get_workflow_executions(workflow_id)

                if executions:
                    df = pd.DataFrame([{
                        'Started': datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00')),
                        'Status': e['status'],
                        'Duration': e.get('stoppedAt', None) and
                                    (datetime.fromisoformat(e['stoppedAt'].replace('Z', '+00:00')) -
                                     datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00'))).seconds
                    } for e in executions])
                    st.dataframe(df)
                else:
                    st.info("No executions found for this workflow.")
            else:
                st.error("Selected workflow not found.")
        else:
            st.info("No workflows available to select.")

    with tabs[2]:
        st.header("Advanced Workflow Metrics")
        if workflows:
            workflow_names = [w['name'] for w in workflows]
            selected_workflow_name = st.selectbox(
                "Select Workflow",
                options=workflow_names,
                key="advanced_metrics_workflow_selector"
            )

            selected_workflow = next((w for w in workflows if w['name'] == selected_workflow_name), None)

            if selected_workflow:
                workflow_id = selected_workflow['id']
                executions = get_workflow_executions(workflow_id)
                metrics = get_workflow_metrics(workflow_id)

                if executions and metrics:
                    # Time range filter
                    time_range = st.selectbox(
                        "Time Range",
                        ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"]
                    )

                    time_filters = {
                        "Last 24 Hours": timedelta(days=1),
                        "Last 7 Days": timedelta(days=7),
                        "Last 30 Days": timedelta(days=30),
                        "All Time": timedelta(days=36500)  # ~100 years
                    }

                    cutoff_time = datetime.now() - time_filters[time_range]

                    filtered_executions = [
                        e for e in executions
                        if datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00')) > cutoff_time
                    ]

                    col1, col2 = st.columns(2)

                    with col1:
                        # Success Rate Gauge
                        st.plotly_chart(create_success_rate_gauge(metrics), use_container_width=True)

                    with col2:
                        # Execution Timeline
                        st.plotly_chart(create_execution_timeline(filtered_executions), use_container_width=True)

                    # Daily Execution Chart
                    st.plotly_chart(create_daily_execution_chart(filtered_executions), use_container_width=True)
                else:
                    st.info("No executions or metrics available for this workflow.")
            else:
                st.error("Selected workflow not found.")
        else:
            st.info("No workflows available to select.")

    with tabs[3]:
        st.header("Backup and Restore")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Create Backup")
            if st.button("Generate Full Backup"):
                if workflows:  # Check if workflows are available before creating backup
                    backup_data = create_backup_file(workflows)

                    # Create download link
                    b64_backup = base64.b64encode(backup_data).decode()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"n8n_backup_{timestamp}.zip"

                    href = f'<a href="data:application/zip;base64,{b64_backup}" download="{filename}">Download Backup File</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Backup generated successfully!")
                else:
                    st.warning("No workflows to backup.")

        with col2:
            st.subheader("Restore from Backup")
            uploaded_file = st.file_uploader("Upload Backup File", type="zip")

            if uploaded_file:
                try:
                    with zipfile.ZipFile(uploaded_file) as zip_file:
                        with zip_file.open('workflows.json') as f:
                            backup_data = json.load(f)

                        st.write(f"Found {len(backup_data['workflows'])} workflows in backup")

                        if st.button("Restore All Workflows"):
                            success_count = 0
                            for workflow in backup_data['workflows']:
                                if restore_workflow(workflow):
                                    success_count += 1

                            st.success(f"Restored {success_count} workflows successfully!")
                except zipfile.BadZipFile:
                    st.error("Invalid ZIP file. Please upload a valid n8n backup.")
                except KeyError:
                    st.error("The uploaded ZIP file does not contain the expected 'workflows.json' file.")
                except json.JSONDecodeError:
                    st.error("Error decoding JSON from the uploaded file.")

    with tabs[4]:
        st.header("Tags")
        tags = get_tags()
        if tags:
            st.write(tags)
        else:
            st.info("Could not retrieve tags.")

        new_tag_name = st.text_input("Create New Tag")
        if st.button("Create Tag"):
            if new_tag_name:
                if create_tag(new_tag_name):
                    st.success(f"Tag '{new_tag_name}' created successfully!")
                    st.rerun()  # Refresh to show the new tag
                else:
                    st.error(f"Failed to create tag '{new_tag_name}'.")
            else:
                st.warning("Tag name cannot be empty.")

    with tabs[5]:
        st.header("Credentials")
        credentials = get_credentials()
        if credentials:
            st.write(credentials)
        else:
            st.info("Could not retrieve credentials.")

if __name__ == "__main__":
    main()

