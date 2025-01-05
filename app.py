import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import base64
import zipfile
import networkx as nx
import difflib
import hashlib
from collections import defaultdict
import numpy as np
from scipy import stats

# [Previous configuration and basic API functions remain the same...]

class WorkflowDiffer:
    """Handles workflow comparison and difference visualization"""
    
    def __init__(self, workflow1, workflow2):
        self.workflow1 = workflow1
        self.workflow2 = workflow2
    
    def get_node_signature(self, node):
        """Create a unique signature for a node based on its type and connections"""
        return {
            'type': node.get('type', ''),
            'connections': sorted([
                conn.get('node', '') for conn in node.get('connections', [])
            ]),
            'parameters': json.dumps(node.get('parameters', {}), sort_keys=True)
        }
    
    def compare_workflows(self):
        """Compare two workflows and return detailed differences"""
        differences = {
            'nodes_added': [],
            'nodes_removed': [],
            'nodes_modified': [],
            'connections_changed': [],
            'parameter_changes': defaultdict(dict)
        }
        
        nodes1 = {n['name']: n for n in self.workflow1.get('nodes', [])}
        nodes2 = {n['name']: n for n in self.workflow2.get('nodes', [])}
        
        # Find added and removed nodes
        differences['nodes_added'] = list(set(nodes2.keys()) - set(nodes1.keys()))
        differences['nodes_removed'] = list(set(nodes1.keys()) - set(nodes2.keys()))
        
        # Compare common nodes
        for name in set(nodes1.keys()) & set(nodes2.keys()):
            sig1 = self.get_node_signature(nodes1[name])
            sig2 = self.get_node_signature(nodes2[name])
            
            if sig1 != sig2:
                differences['nodes_modified'].append(name)
                if sig1['parameters'] != sig2['parameters']:
                    differences['parameter_changes'][name] = {
                        'old': json.loads(sig1['parameters']),
                        'new': json.loads(sig2['parameters'])
                    }
        
        return differences
    
    def visualize_differences(self):
        """Create a visual representation of workflow differences"""
        diff = self.compare_workflows()
        G = nx.DiGraph()
        
        # Add nodes with appropriate colors
        for node in self.workflow1.get('nodes', []):
            color = 'lightgray'
            if node['name'] in diff['nodes_removed']:
                color = 'red'
            elif node['name'] in diff['nodes_modified']:
                color = 'yellow'
            G.add_node(node['name'], color=color)
        
        for node in self.workflow2.get('nodes', []):
            if node['name'] in diff['nodes_added']:
                G.add_node(node['name'], color='green')
        
        # Add edges
        for node in self.workflow2.get('nodes', []):
            for conn in node.get('connections', []):
                G.add_edge(node['name'], conn['node'])
        
        return G, diff

class IncrementalBackup:
    """Handles incremental backup functionality"""
    
    def __init__(self, base_dir="./backups"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        
    def calculate_workflow_hash(self, workflow):
        """Calculate a hash for workflow content"""
        content = json.dumps(workflow, sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()
    
    def create_increment(self, workflows):
        """Create an incremental backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Load previous backup manifest if exists
        manifest_path = os.path.join(self.base_dir, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
        else:
            manifest = {"backups": [], "workflow_versions": {}}
        
        # Calculate changes
        changes = {
            "added": [],
            "modified": [],
            "unchanged": []
        }
        
        for workflow in workflows:
            workflow_hash = self.calculate_workflow_hash(workflow)
            workflow_id = workflow['id']
            
            if workflow_id not in manifest['workflow_versions']:
                changes['added'].append(workflow_id)
            elif manifest['workflow_versions'][workflow_id] != workflow_hash:
                changes['modified'].append(workflow_id)
            else:
                changes['unchanged'].append(workflow_id)
            
            manifest['workflow_versions'][workflow_id] = workflow_hash
        
        # Create backup file for changed workflows
        if changes['added'] or changes['modified']:
            backup_file = f"increment_{timestamp}.zip"
            backup_path = os.path.join(self.base_dir, backup_file)
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                changed_workflows = [w for w in workflows 
                                  if w['id'] in changes['added'] + changes['modified']]
                zf.writestr('workflows.json', json.dumps(changed_workflows))
                zf.writestr('changes.json', json.dumps(changes))
            
            manifest['backups'].append({
                'file': backup_file,
                'timestamp': timestamp,
                'changes': changes
            })
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        
        return changes, manifest

class WorkflowAnalytics:
    """Handles advanced workflow analytics and metrics"""
    
    def __init__(self, executions):
        self.executions = executions
        self.df = pd.DataFrame([{
            'started': datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00')),
            'status': e['status'],
            'duration': e.get('stoppedAt') and 
                (datetime.fromisoformat(e['stoppedAt'].replace('Z', '+00:00')) - 
                 datetime.fromisoformat(e['startedAt'].replace('Z', '+00:00'))).seconds,
            'error': e.get('error', {}).get('message', '')
        } for e in executions])
    
    def calculate_performance_trends(self):
        """Calculate performance trends over time"""
        daily_stats = self.df.set_index('started').resample('D').agg({
            'duration': ['mean', 'std'],
            'status': lambda x: (x == 'success').mean()
        }).fillna(0)
        
        # Calculate trending metrics
        trend_data = {
            'success_rate_trend': stats.linregress(
                range(len(daily_stats)), 
                daily_stats['status']['<lambda>']
            ).slope,
            'duration_trend': stats.linregress(
                range(len(daily_stats)), 
                daily_stats['duration']['mean']
            ).slope
        }
        
        return daily_stats, trend_data
    
    def analyze_error_patterns(self):
        """Analyze common error patterns"""
        error_df = self.df[self.df['status'] == 'error']
        error_patterns = error_df['error'].value_counts()
        
        # Categorize errors
        error_categories = defaultdict(int)
        for error in error_df['error']:
            if 'timeout' in error.lower():
                error_categories['Timeout'] += 1
            elif 'authentication' in error.lower():
                error_categories['Authentication'] += 1
            elif 'connection' in error.lower():
                error_categories['Connection'] += 1
            else:
                error_categories['Other'] += 1
        
        return error_patterns, dict(error_categories)
    
    def create_performance_visualizations(self):
        """Create performance visualization charts"""
        daily_stats, trend_data = self.calculate_performance_trends()
        
        # Success rate over time
        success_fig = px.line(
            daily_stats['status'],
            title='Success Rate Trend',
            labels={'value': 'Success Rate', 'started': 'Date'}
        )
        
        # Duration distribution
        duration_fig = px.histogram(
            self.df,
            x='duration',
            title='Execution Duration Distribution',
            labels={'duration': 'Duration (seconds)'}
        )
        
        # Error pattern visualization
        _, error_categories = self.analyze_error_patterns()
        error_fig = px.pie(
            values=list(error_categories.values()),
            names=list(error_categories.keys()),
            title='Error Distribution by Category'
        )
        
        return success_fig, duration_fig, error_fig

class WorkflowDependencyAnalyzer:
    """Analyzes and visualizes workflow dependencies"""
    
    def __init__(self, workflows):
        self.workflows = workflows
        self.G = nx.DiGraph()
        
    def build_dependency_graph(self):
        """Build a graph of workflow dependencies"""
        for workflow in self.workflows:
            self.G.add_node(workflow['name'])
            
            # Analyze nodes for potential dependencies
            for node in workflow.get('nodes', []):
                if node.get('type') == 'n8n-nodes-base.webhook':
                    # Check if this webhook is called by other workflows
                    webhook_url = node.get('parameters', {}).get('path', '')
                    for other_workflow in self.workflows:
                        if other_workflow['name'] != workflow['name']:
                            for other_node in other_workflow.get('nodes', []):
                                if webhook_url in json.dumps(other_node.get('parameters', {})):
                                    self.G.add_edge(other_workflow['name'], workflow['name'])
                
                elif node.get('type') == 'n8n-nodes-base.executeWorkflow':
                    # Direct workflow execution dependencies
                    target_workflow = node.get('parameters', {}).get('workflowId', '')
                    if target_workflow:
                        target_name = next((w['name'] for w in self.workflows 
                                         if w['id'] == target_workflow), None)
                        if target_name:
                            self.G.add_edge(workflow['name'], target_name)
        
        return self.G
    
    def analyze_dependencies(self):
        """Analyze dependency relationships"""
        self.build_dependency_graph()
        
        analysis = {
            'workflow_count': len(self.G),
            'dependency_count': self.G.number_of_edges(),
            'isolated_workflows': list(nx.isolates(self.G)),
            'circular_dependencies': list(nx.simple_cycles(self.G)),
            'entry_points': [n for n in self.G.nodes() 
                           if self.G.in_degree(n) == 0 and self.G.out_degree(n) > 0],
            'terminal_workflows': [n for n in self.G.nodes() 
                                 if self.G.out_degree(n) == 0 and self.G.in_degree(n) > 0],
            'centrality': nx.degree_centrality(self.G)
        }
        
        return analysis
    
    def visualize_dependencies(self):
        """Create interactive dependency visualization"""
        pos = nx.spring_layout(self.G)
        
        edge_trace = go.Scatter(
            x=[], y=[],
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines')

        node_trace = go.Scatter(
            x=[], y=[],
            mode='markers+text',
            hoverinfo='text',
            text=[],
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                size=10,
                colorbar=dict(
                    thickness=15,
                    title='Node Connections',
                    xanchor='left',
                    titleside='right'
                )
            )
        )

        for edge in self.G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace['x'] += tuple([x0, x1, None])
            edge_trace['y'] += tuple([y0, y1, None])

        for node in self.G.nodes():
            x, y = pos[node]
            node_trace['x'] += tuple([x])
            node_trace['y'] += tuple([y])
            node_trace['text'] += tuple([node])

        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           title='Workflow Dependencies',
                           showlegend=False,
                           hovermode='closest',
                           margin=dict(b=20,l=5,r=5,t=40),
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                       )
        
        return fig

def main():
    [Previous main() code remains the same until tabs[1]...]

    with tabs[1]:  # Advanced Analysis (continuation)
            with viz_tabs[1]:  # Error Analysis tab
                st.plotly_chart(error_fig, use_container_width=True)
                
                st.subheader("Common Error Messages")
                for error, count in error_patterns.head().items():
                    st.write(f"**{count} occurrences:** {error}")
            
            with viz_tabs[2]:  # Patterns tab
                st.subheader("Execution Patterns")
                
                # Time-of-day analysis
                st.write("#### Execution Time Distribution")
                hour_dist = pd.DataFrame({
                    'hour': pd.to_datetime(analytics.df['started']).dt.hour,
                    'success': analytics.df['status'] == 'success'
                })
                hour_fig = px.histogram(hour_dist, x='hour', color='success',
                                      title='Executions by Hour of Day')
                st.plotly_chart(hour_fig, use_container_width=True)

    with tabs[2]:  # Dependencies
        st.header("Workflow Dependencies Analysis")
        
        dependency_analyzer = WorkflowDependencyAnalyzer(workflows)
        analysis = dependency_analyzer.analyze_dependencies()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Workflows", analysis['workflow_count'])
        with col2:
            st.metric("Dependencies", analysis['dependency_count'])
        with col3:
            st.metric("Isolated Workflows", len(analysis['isolated_workflows']))
        
        # Dependency Visualization
        st.subheader("Dependency Graph")
        dep_fig = dependency_analyzer.visualize_dependencies()
        st.plotly_chart(dep_fig, use_container_width=True)
        
        # Dependency Details
        with st.expander("View Dependency Details"):
            st.write("#### Entry Point Workflows")
            for workflow in analysis['entry_points']:
                st.write(f"- {workflow}")
            
            st.write("#### Terminal Workflows")
            for workflow in analysis['terminal_workflows']:
                st.write(f"- {workflow}")
            
            if analysis['circular_dependencies']:
                st.write("#### ⚠️ Circular Dependencies Detected")
                for cycle in analysis['circular_dependencies']:
                    st.write(f"- {' → '.join(cycle)}")

    with tabs[3]:  # Backup & Compare
        st.header("Backup Comparison")
        
        col1, col2 = st.columns(2)
        with col1:
            base_workflow = st.selectbox(
                "Select Base Workflow",
                options=[w['name'] for w in workflows],
                key="base_workflow"
            )
        with col2:
            uploaded_file = st.file_uploader(
                "Upload Backup for Comparison",
                type=['json', 'zip']
            )
        
        if uploaded_file and base_workflow:
            base_data = next(w for w in workflows if w['name'] == base_workflow)
            
            if uploaded_file.name.endswith('.zip'):
                with zipfile.ZipFile(uploaded_file) as zf:
                    with zf.open('workflows.json') as f:
                        compare_data = json.load(f)['workflows']
                        compare_workflow = next(
                            (w for w in compare_data if w['name'] == base_workflow),
                            None
                        )
            else:
                compare_workflow = json.load(uploaded_file)
            
            if compare_workflow:
                differ = WorkflowDiffer(base_data, compare_workflow)
                G, diff = differ.visualize_differences()
                
                st.subheader("Workflow Changes")
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Added Nodes", len(diff['nodes_added']))
                with col2:
                    st.metric("Removed Nodes", len(diff['nodes_removed']))
                with col3:
                    st.metric("Modified Nodes", len(diff['nodes_modified']))
                
                # Detailed changes
                st.write("#### Added Nodes")
                for node in diff['nodes_added']:
                    st.write(f"- {node}")
                
                st.write("#### Removed Nodes")
                for node in diff['nodes_removed']:
                    st.write(f"- {node}")
                
                st.write("#### Modified Nodes")
                for node in diff['nodes_modified']:
                    st.write(f"- {node}")
                    params = diff['parameter_changes'].get(node, {})
                    if params:
                        with st.expander(f"View changes in {node}"):
                            st.json({
                                'old_parameters': params.get('old', {}),
                                'new_parameters': params.get('new', {})
                            })

    with tabs[4]:  # Incremental Backup
        st.header("Incremental Backup Management")
        
        backup_manager = IncrementalBackup()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Create Incremental Backup")
            if st.button("Generate Increment"):
                changes, manifest = backup_manager.create_increment(workflows)
                
                st.write("#### Changes in this Increment")
                st.write(f"Added: {len(changes['added'])} workflows")
                st.write(f"Modified: {len(changes['modified'])} workflows")
                st.write(f"Unchanged: {len(changes['unchanged'])} workflows")
                
                if changes['added'] or changes['modified']:
                    st.success("Incremental backup created successfully!")
        
        with col2:
            st.subheader("Backup History")
            manifest_path = os.path.join(backup_manager.base_dir, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                for backup in reversed(manifest['backups']):
                    with st.expander(f"Backup {backup['timestamp']}"):
                        st.write(f"File: {backup['file']}")
                        st.write("Changes:")
                        st.write(f"- Added: {len(backup['changes']['added'])}")
                        st.write(f"- Modified: {len(backup['changes']['modified'])}")
                        st.write(f"- Unchanged: {len(backup['changes']['unchanged'])}")

    with tabs[5]:  # Advanced Metrics
        st.header("System-wide Metrics")
        
        # Time range selector for metrics
        time_range = st.selectbox(
            "Time Range",
            ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
            key="metrics_time_range"
        )
        
        # Collect system-wide metrics
        all_executions = []
        for workflow in workflows:
            executions = get_workflow_executions(workflow['id'])
            if executions:
                for execution in executions:
                    execution['workflow_name'] = workflow['name']
                    all_executions.append(execution)
        
        if all_executions:
            system_analytics = WorkflowAnalytics(all_executions)
            
            # Overall system health
            st.subheader("System Health")
            daily_stats, trend_data = system_analytics.calculate_performance_trends()
            
            # Health metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                success_rate = daily_stats['status']['<lambda>'].mean() * 100
                st.metric("Overall Success Rate", f"{success_rate:.1f}%")
            with col2:
                avg_duration = daily_stats['duration']['mean'].mean()
                st.metric("Average Duration", f"{avg_duration:.1f}s")
            with col3:
                total_executions = len(all_executions)
                st.metric("Total Executions", total_executions)
            
            # System-wide visualizations
            success_fig, duration_fig, error_fig = system_analytics.create_performance_visualizations()
            
            st.plotly_chart(success_fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(duration_fig, use_container_width=True)
            with col2:
                st.plotly_chart(error_fig, use_container_width=True)

if __name__ == "__main__":
    main()
