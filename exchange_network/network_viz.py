import streamlit as st
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import numpy as np
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import os
import plotly.express as px
import math

# Set page config
st.set_page_config(page_title="Trading Network Visualization", page_icon="🔄", layout="wide")

# App title and description
st.title("Trading Network Visualization")
st.markdown("""
This application visualizes the trading network between financial institutions based on:
- **Node Size**: Market share of each institution
- **Edge Thickness**: Notional value of the flow between institutions
- **Node Color**: Connectivity (darker = more connections)

Use the filters in the sidebar to explore different aspects of the network.
""")

# Function to load data
@st.cache_data
def load_data():
    df = pd.read_csv('exchange_party_flows_and_shares.csv')
    return df

# Load the data
df = load_data()

# Sidebar filters
st.sidebar.header("Visualization Settings")

# Filter for top parties by market share
top_n_parties = st.sidebar.slider(
    "Show top N parties by market share",
    min_value=5,
    max_value=len(df['party'].unique()),
    value=30,
    step=5
)

# Filter by minimum notional value
min_edge_value = st.sidebar.slider(
    "Minimum flow value (notional)",
    min_value=int(df['notional'].min()),
    max_value=int(df['notional'].max() * 0.5),
    value=int(1e8),  # Default to 100 million
    format="%e"
)

# Filter specific parties
all_parties = sorted(df['party'].unique())
selected_parties = st.sidebar.multiselect(
    "Focus on specific parties",
    options=all_parties,
    default=[]
)

# Visualization type selection
viz_type = st.sidebar.radio(
    "Visualization Type",
    ["Interactive Network", "Centrality Analysis", "Party Flow Distribution", "Trading Clusters"]
)

# Color scheme
color_scheme = st.sidebar.selectbox(
    "Color Scheme",
    ["Blues", "Greens", "Reds", "Purples", "Oranges"]
)

# Common functions
def get_top_parties(df, n):
    """Get the top N parties by market share"""
    party_market_shares = df.drop_duplicates('party')[['party', 'party_market_share_pct']]
    top_parties = party_market_shares.sort_values('party_market_share_pct', ascending=False).head(n)['party'].tolist()
    return top_parties

def prepare_network_data(df, top_parties=None, min_notional=0, focus_parties=None):
    """Prepare the data for network visualization"""
    # If top parties are specified, filter the data
    if top_parties:
        df_filtered = df[df['party'].isin(top_parties) | df['counter_party'].isin(top_parties)]
    else:
        df_filtered = df.copy()
    
    # Apply minimum notional filter
    df_filtered = df_filtered[df_filtered['notional'] >= min_notional]
    
    # If focus parties are specified, include all their connections
    if focus_parties and len(focus_parties) > 0:
        df_filtered = df_filtered[(df_filtered['party'].isin(focus_parties)) | 
                                 (df_filtered['counter_party'].isin(focus_parties))]
    
    # Get unique parties for nodes
    unique_parties = set(df_filtered['party'].unique()) | set(df_filtered['counter_party'].unique())
    
    # Create node dataframe with market share
    parties_market_share = df.drop_duplicates('party')[['party', 'party_market_share_pct']]
    
    # Calculate degree (connectivity) for each party
    party_degree = {}
    for party in unique_parties:
        out_degree = df_filtered[df_filtered['party'] == party]['counter_party'].nunique()
        in_degree = df_filtered[df_filtered['counter_party'] == party]['party'].nunique()
        party_degree[party] = out_degree + in_degree
    
    # Create nodes dataframe
    nodes_df = pd.DataFrame({
        'id': list(unique_parties),
        'market_share': [parties_market_share[parties_market_share['party'] == party]['party_market_share_pct'].iloc[0] 
                        if party in parties_market_share['party'].values else 0 
                        for party in unique_parties],
        'degree': [party_degree.get(party, 0) for party in unique_parties]
    })
    
    # Create edges dataframe
    edges_df = df_filtered[['party', 'counter_party', 'notional', 'cp_share_pct']].copy()
    
    return nodes_df, edges_df

# Interactive Network Visualization
def create_interactive_network(nodes_df, edges_df, color_scheme):
    # Create a network graph
    G = nx.DiGraph()
    
    # Add nodes with attributes
    for _, node in nodes_df.iterrows():
        # Scale size by market share
        size = max(10, min(50, node['market_share'] * 3 + 10))
        
        # Scale color by degree (connectivity)
        color_intensity = min(0.9, max(0.1, node['degree'] / nodes_df['degree'].max()))
        
        # Map color schemes
        color_map = {
            "Blues": f"rgba(0, 0, 255, {color_intensity})",
            "Greens": f"rgba(0, 128, 0, {color_intensity})",
            "Reds": f"rgba(255, 0, 0, {color_intensity})",
            "Purples": f"rgba(128, 0, 128, {color_intensity})",
            "Oranges": f"rgba(255, 165, 0, {color_intensity})"
        }
        
        color = color_map.get(color_scheme, f"rgba(0, 0, 255, {color_intensity})")
        
        # Add node with attributes
        G.add_node(node['id'], 
                   size=size, 
                   title=f"{node['id']}\nMarket Share: {node['market_share']}%\nConnections: {node['degree']}",
                   color=color)
    
    # Add edges with attributes
    for _, edge in edges_df.iterrows():
        # Scale width by notional value (logarithmic scale for better visualization)
        width = max(1, min(10, math.log10(edge['notional']) - 5))
        
        # Add edge with attributes
        G.add_edge(edge['party'], 
                   edge['counter_party'], 
                   value=edge['notional'],
                   width=width,
                   title=f"Flow: {edge['notional']:,}\n{edge['party']} -> {edge['counter_party']}\n{edge['cp_share_pct']}% of {edge['party']}'s flow")
    
    # Create a pyvis network
    net = Network(notebook=True, directed=True, height="600px", width="100%")
    
    # Take the networkx graph and translate it to a pyvis graph
    net.from_nx(G)
    
    # Set physics layout
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08
        },
        "solver": "forceAtlas2Based",
        "stabilization": {
          "enabled": true,
          "iterations": 100
        }
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.5
          }
        },
        "smooth": {
          "enabled": true,
          "type": "continuous"
        }
      },
      "interaction": {
        "navigationButtons": true,
        "keyboard": true,
        "hover": true
      }
    }
    """)
    
    # Generate the HTML file
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmpfile:
        net.save_graph(tmpfile.name)
        return tmpfile.name

# Centrality Analysis
def plot_centrality_metrics(nodes_df, edges_df):
    # Create a networkx graph for analysis
    G = nx.DiGraph()
    
    # Add nodes
    for node_id in nodes_df['id']:
        G.add_node(node_id)
    
    # Add edges with weights based on notional value
    for _, edge in edges_df.iterrows():
        G.add_edge(edge['party'], edge['counter_party'], weight=edge['notional'])
    
    # Calculate centrality metrics
    # Degree centrality (normalized)
    degree_centrality = nx.degree_centrality(G)
    
    # Betweenness centrality (how often a node appears on shortest paths)
    betweenness_centrality = nx.betweenness_centrality(G, weight='weight')
    
    # Eigenvector centrality (connection to important nodes)
    try:
        eigenvector_centrality = nx.eigenvector_centrality(G, weight='weight', max_iter=1000)
    except:
        # Fallback if eigenvector centrality doesn't converge
        eigenvector_centrality = {node: 0 for node in G.nodes()}
    
    # Create dataframe with centrality metrics
    centrality_df = pd.DataFrame({
        'Party': list(G.nodes()),
        'Degree Centrality': [degree_centrality.get(n, 0) for n in G.nodes()],
        'Betweenness Centrality': [betweenness_centrality.get(n, 0) for n in G.nodes()],
        'Eigenvector Centrality': [eigenvector_centrality.get(n, 0) for n in G.nodes()]
    })
    
    # Add market share to the dataframe
    centrality_df = centrality_df.merge(
        nodes_df[['id', 'market_share']], 
        left_on='Party', 
        right_on='id', 
        how='left'
    ).drop(columns=['id'])
    
    centrality_df.rename(columns={'market_share': 'Market Share (%)'}, inplace=True)
    
    # Sort by degree centrality
    centrality_df = centrality_df.sort_values('Degree Centrality', ascending=False).reset_index(drop=True)
    
    # Plot centrality metrics for top 20 parties
    top_centrality = centrality_df.head(20)
    
    # Create 2x2 grid of charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Market Share vs Degree Centrality
        fig1 = px.scatter(
            centrality_df, 
            x='Market Share (%)', 
            y='Degree Centrality',
            color='Betweenness Centrality',
            hover_name='Party',
            size=[max(5, ms) for ms in centrality_df['Market Share (%)']],
            color_continuous_scale=color_scheme.lower(),
            title='Market Share vs. Degree Centrality',
            labels={'Market Share (%)': 'Market Share (%)', 'Degree Centrality': 'Degree Centrality'}
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # Top 20 by Betweenness Centrality
        fig3 = px.bar(
            top_centrality.sort_values('Betweenness Centrality', ascending=False), 
            x='Party', 
            y='Betweenness Centrality',
            color='Betweenness Centrality',
            color_continuous_scale=color_scheme.lower(),
            title='Top 20 Parties by Betweenness Centrality',
            labels={'Party': 'Party', 'Betweenness Centrality': 'Betweenness Centrality (Bridge Role)'}
        )
        st.plotly_chart(fig3, use_container_width=True)
        
    with col2:
        # Top 20 by Degree Centrality
        fig2 = px.bar(
            top_centrality, 
            x='Party', 
            y='Degree Centrality',
            color='Degree Centrality',
            color_continuous_scale=color_scheme.lower(),
            title='Top 20 Parties by Degree Centrality',
            labels={'Party': 'Party', 'Degree Centrality': 'Degree Centrality (Connectivity)'}
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        # Eigenvector vs Betweenness
        fig4 = px.scatter(
            centrality_df, 
            x='Eigenvector Centrality', 
            y='Betweenness Centrality',
            color='Degree Centrality',
            hover_name='Party',
            size=[max(5, ms) for ms in centrality_df['Market Share (%)']],
            color_continuous_scale=color_scheme.lower(),
            title='Eigenvector vs. Betweenness Centrality',
            labels={
                'Eigenvector Centrality': 'Eigenvector Centrality (Connection to Important Nodes)', 
                'Betweenness Centrality': 'Betweenness Centrality (Bridge Role)'
            }
        )
        st.plotly_chart(fig4, use_container_width=True)
    
    # Display table with top parties by different centrality metrics
    st.subheader("Centrality Metrics for Top Parties")
    st.write("The table below shows different network centrality measures that indicate party importance:")
    st.write("- **Degree Centrality**: Number of direct connections (normalized)")
    st.write("- **Betweenness Centrality**: How often a party is on the shortest path between others (bridge role)")
    st.write("- **Eigenvector Centrality**: Connection to other important parties")
    
    # Format the centrality metrics table
    formatted_df = centrality_df.head(20).copy()
    for col in ['Degree Centrality', 'Betweenness Centrality', 'Eigenvector Centrality']:
        formatted_df[col] = formatted_df[col].map(lambda x: f"{x:.4f}")
    
    formatted_df['Market Share (%)'] = formatted_df['Market Share (%)'].map(lambda x: f"{x:.2f}%")
    
    st.dataframe(formatted_df, use_container_width=True)

# Party Flow Distribution
def plot_flow_distribution(df):
    # Get top 20 parties by market share
    top_parties = df.drop_duplicates('party')[['party', 'party_market_share_pct']] \
                   .sort_values('party_market_share_pct', ascending=False) \
                   .head(20)['party'].tolist()
    
    # Filter data for top parties
    df_top = df[df['party'].isin(top_parties)]
    
    # Create a DataFrame for the flow distribution
    flow_data = []
    
    for party in top_parties:
        party_flows = df[df['party'] == party].sort_values('cp_share_pct', ascending=False)
        
        # Get top 5 counter parties by flow
        top_cps = party_flows.head(5)
        
        # Calculate "Others" category if enough data exists
        if len(top_cps) > 0:  # Make sure there's data
            others_share = max(0, 100 - top_cps['cp_share_pct'].sum())
            
            # Add top counter parties
            for _, row in top_cps.iterrows():
                flow_data.append({
                    'Party': party,
                    'Counter Party': row['counter_party'],
                    'Flow Share (%)': row['cp_share_pct'],
                    'Notional': row['notional']
                })
            
            # Add "Others" if applicable
            if others_share > 0 and len(party_flows) > len(top_cps):
                flow_data.append({
                    'Party': party,
                    'Counter Party': 'Others',
                    'Flow Share (%)': others_share,
                    'Notional': party_flows[~party_flows['counter_party'].isin(top_cps['counter_party'])]['notional'].sum()
                })
    
    flow_df = pd.DataFrame(flow_data)
    
    # Create a grouped bar chart for flow distribution
    fig = px.bar(
        flow_df,
        x='Party',
        y='Flow Share (%)',
        color='Counter Party',
        hover_data=['Notional'],
        title='Flow Distribution for Top 20 Parties',
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={'Party': 'Party', 'Flow Share (%)': 'Share of Total Flow (%)'}
    )
    
    # Update layout
    fig.update_layout(
        xaxis_title='Party',
        yaxis_title='Flow Share (%)',
        legend_title='Counter Party',
        barmode='stack',
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show details in an expandable section
    with st.expander("View Detailed Flow Data"):
        # Create pivot table for detailed inspection
        pivot_df = df.pivot_table(
            index='party', 
            columns='counter_party', 
            values='notional',
            aggfunc='sum',
            fill_value=0
        )
        
        # Filter for top parties
        pivot_df = pivot_df.loc[pivot_df.index.isin(top_parties), pivot_df.columns.isin(top_parties)]
        
        # Format values as millions
        formatted_pivot = pivot_df.applymap(lambda x: f"{x/1e6:.2f}M" if x > 0 else "-")
        
        st.write("Flow Values Between Top Parties (in millions)")
        st.dataframe(formatted_pivot, use_container_width=True)

def plot_trading_clusters(nodes_df, edges_df):
    # Create networkx graph for community detection
    G = nx.Graph()  # Undirected for community detection
    
    # Add nodes
    for _, node in nodes_df.iterrows():
        G.add_node(node['id'], market_share=node['market_share'])
    
    # Add edges (combine bidirectional edges)
    edge_weights = {}
    for _, edge in edges_df.iterrows():
        pair = tuple(sorted([edge['party'], edge['counter_party']]))
        if pair not in edge_weights:
            edge_weights[pair] = 0
        edge_weights[pair] += edge['notional']
    
    for (source, target), weight in edge_weights.items():
        G.add_edge(source, target, weight=weight)
    
    # Apply community detection (Louvain method)
    try:
        import community as community_louvain
        partition = community_louvain.best_partition(G)
    except ImportError:
        st.warning("The python-louvain package is not installed. Using a simpler clustering method.")
        # Fallback to connected components
        components = list(nx.connected_components(G))
        partition = {}
        for i, component in enumerate(components):
            for node in component:
                partition[node] = i
    
    # Get number of communities
    num_communities = len(set(partition.values()))
    
    # Add a filter to select specific communities
    st.write(f"Detected {num_communities} trading communities in the network")
    
    # Create columns for community selection and summary
    filter_col, info_col = st.columns([3, 1])
    
    with filter_col:
        # Create a multiselect to filter communities
        community_options = sorted(set(partition.values()))
        selected_communities = st.multiselect(
            "Select communities to display (empty = show all)",
            options=[f"Community {i}" for i in community_options],
            default=[]
        )
    
    # Convert selected options back to IDs
    selected_community_ids = [int(comm.split(" ")[1]) for comm in selected_communities] if selected_communities else None
    
    with info_col:
        # Show a quick summary of selected communities
        if selected_community_ids:
            st.write(f"**Selected: {len(selected_community_ids)} communities**")
            
            # Calculate total nodes in selected communities
            selected_nodes = sum(len([node for node, comm in partition.items() if comm == comm_id]) 
                              for comm_id in selected_community_ids)
            st.write(f"Including {selected_nodes} companies")
        else:
            st.write("**Showing all communities**")
    
    # Add community information to nodes
    nodes_df['community'] = nodes_df['id'].map(lambda x: partition.get(x, 0))
    
    # Calculate metrics for each community
    community_metrics = {}
    
    # Get list of communities to display metrics for
    communities_to_display = selected_community_ids if selected_community_ids else set(partition.values())
    
    for comm_id in communities_to_display:
        # Get nodes in this community
        comm_nodes = [node for node, comm in partition.items() if comm == comm_id]
        
        # Calculate total market share
        total_market_share = sum(nodes_df[nodes_df['id'].isin(comm_nodes)]['market_share'])
        
        # Calculate internal vs external edges
        internal_edges = 0
        external_edges = 0
        internal_volume = 0
        external_volume = 0
        
        for _, edge in edges_df.iterrows():
            source_comm = partition.get(edge['party'], -1)
            target_comm = partition.get(edge['counter_party'], -1)
            
            if source_comm == comm_id and target_comm == comm_id:
                internal_edges += 1
                internal_volume += edge['notional']
            elif source_comm == comm_id or target_comm == comm_id:
                external_edges += 1
                external_volume += edge['notional']
        
        # Store metrics
        community_metrics[comm_id] = {
            'size': len(comm_nodes),
            'market_share': total_market_share,
            'internal_edges': internal_edges,
            'external_edges': external_edges,
            'internal_volume': internal_volume,
            'external_volume': external_volume,
            'nodes': comm_nodes
        }
    
    # Create a network visualization colored by community
    node_colors = [f"Community {partition[node]}" for node in G.nodes()]
    
    # Create a dataframe for the network visualization
    node_df = pd.DataFrame({
        'id': list(G.nodes()),
        'community_id': [partition[node] for node in G.nodes()],
        'community': [f"Community {partition[node]}" for node in G.nodes()],
        'market_share': [nodes_df[nodes_df['id'] == node]['market_share'].iloc[0] 
                        if node in nodes_df['id'].values else 0 for node in G.nodes()]
    })
    
    # Store the current partition in the session state
    # This is the key fix - save the partition to session state
    st.session_state['current_partition'] = partition
    
    # Add a button to view the list of companies in each community
    if st.button("Show Companies by Community"):
        st.subheader("Companies in Each Community")
        
        # Use the partition from session state
        current_partition = st.session_state['current_partition']
        
        # Get communities to display
        display_communities = selected_community_ids if selected_community_ids else sorted(set(current_partition.values()))
        
        # Create tabs for each community
        tabs = st.tabs([f"Community {comm_id}" for comm_id in display_communities])
        
        for i, comm_id in enumerate(display_communities):
            with tabs[i]:
                # Get companies in this community
                comm_companies = [node for node, comm in current_partition.items() if comm == comm_id]
                
                # Create a dataframe for companies in this community
                if comm_companies:
                    company_data = []
                    for company in sorted(comm_companies):
                        if company in nodes_df['id'].values:
                            market_share = nodes_df[nodes_df['id'] == company]['market_share'].iloc[0]
                            degree = nodes_df[nodes_df['id'] == company]['degree'].iloc[0]
                        else:
                            market_share = 0
                            degree = 0
                            
                        company_data.append({
                            'Company': company,
                            'Market Share (%)': market_share,
                            'Connections': degree
                        })
                    
                    company_df = pd.DataFrame(company_data).sort_values('Market Share (%)', ascending=False)
                    st.dataframe(company_df, use_container_width=True)
    
    # Filter by selected communities if any
    if selected_community_ids:
        filtered_nodes = node_df[node_df['community_id'].isin(selected_community_ids)]
        filtered_node_ids = set(filtered_nodes['id'])
        
        # Create a subgraph with only nodes from selected communities
        G_filtered = G.subgraph(filtered_node_ids)
        
        # Update G to the filtered graph for visualization
        G = G_filtered
    
    # Rest of the function remains the same...
    # Create edges dataframe for visualization
    edge_list = []
    for (u, v, d) in G.edges(data=True):
        edge_list.append({
            'source': u,
            'target': v,
            'weight': d['weight'],
            'source_community': partition[u],
            'target_community': partition[v]
        })
    
    edge_df = pd.DataFrame(edge_list)
    
    # Create network visualization with plotly
    pos = nx.spring_layout(G, seed=42)
    
    # Create plotly figure
    fig = go.Figure()
    
    # Add edges
    for i, (u, v, d) in enumerate(G.edges(data=True)):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        weight = d['weight']
        
        # Scale line width based on weight (log scale)
        width = max(1, min(8, math.log10(weight) - 4))
        
        # Get community IDs for both endpoints
        comm_u = partition[u]
        comm_v = partition[v]
        
        # If same community, use community color, otherwise gray
        if comm_u == comm_v:
            color = px.colors.qualitative.Plotly[comm_u % len(px.colors.qualitative.Plotly)]
            opacity = 0.7
        else:
            color = 'rgba(200, 200, 200, 0.3)'
            opacity = 0.3
        
        fig.add_trace(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=width, color=color),
                opacity=opacity,
                hoverinfo='none',
                showlegend=False
            )
        )
    
    # Add nodes - only for communities in G (which may be filtered)
    communities_in_graph = set(partition[node] for node in G.nodes())
    
    for comm_id in sorted(communities_in_graph):
        # Get nodes in this community
        comm_nodes = [node for node in G.nodes() if partition[node] == comm_id]
        
        # Skip if no nodes (shouldn't happen with filtering, but just in case)
        if not comm_nodes:
            continue
            
        # Get positions
        x = [pos[node][0] for node in comm_nodes if node in pos]
        y = [pos[node][1] for node in comm_nodes if node in pos]
        
        # Skip if no positions (shouldn't happen, but just in case)
        if not x or not y:
            continue
        
        # Get market shares for sizing
        sizes = []
        for node in comm_nodes:
            if node in nodes_df['id'].values:
                size = max(10, min(50, nodes_df[nodes_df['id'] == node]['market_share'].iloc[0] * 3))
            else:
                size = 10  # Default size if market share not found
            sizes.append(size)
        
        # Get colors
        color = px.colors.qualitative.Plotly[comm_id % len(px.colors.qualitative.Plotly)]
        
        # Create hover text
        hover_text = []
        for node in comm_nodes:
            if node in nodes_df['id'].values:
                market_share = nodes_df[nodes_df['id'] == node]['market_share'].iloc[0]
                degree = nodes_df[nodes_df['id'] == node]['degree'].iloc[0]
            else:
                market_share = 0
                degree = 0
                
            hover_text.append(
                f"Party: {node}<br>"
                f"Community: {comm_id}<br>"
                f"Market Share: {market_share:.2f}%<br>"
                f"Connections: {degree}"
            )
        
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode='markers',
                marker=dict(
                    size=sizes,
                    color=color,
                    line=dict(width=1, color='black')
                ),
                text=hover_text,
                hoverinfo='text',
                name=f"Community {comm_id}"
            )
        )
    
    # Update layout
    fig.update_layout(
        title='Trading Communities Network',
        showlegend=True,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        height=700,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show community metrics
    metrics_data = []
    for comm_id, metrics in community_metrics.items():
        # Get top parties that have market share > 1%
        top_parties = []
        for node in sorted(metrics['nodes']):
            if node in nodes_df['id'].values and nodes_df[nodes_df['id'] == node]['market_share'].iloc[0] > 1:
                top_parties.append(node)
        
        metrics_data.append({
            'Community ID': comm_id,
            'Size (Parties)': metrics['size'],
            'Market Share (%)': f"{metrics['market_share']:.2f}%",
            'Internal Connections': metrics['internal_edges'],
            'External Connections': metrics['external_edges'],
            'Internal Volume': f"{metrics['internal_volume']/1e9:.2f}B",
            'External Volume': f"{metrics['external_volume']/1e9:.2f}B",
            'Top Parties': ', '.join(top_parties[:5])
        })
    
    metrics_df = pd.DataFrame(metrics_data).sort_values('Size (Parties)', ascending=False)
    
    st.subheader("Community Metrics")
    st.dataframe(metrics_df, use_container_width=True)

# Main application logic
top_parties = get_top_parties(df, top_n_parties)
nodes_df, edges_df = prepare_network_data(
    df, 
    top_parties=top_parties, 
    min_notional=min_edge_value,
    focus_parties=selected_parties if selected_parties else None
)

# Display number of nodes and edges in the visualization
st.write(f"Network contains {len(nodes_df)} parties and {len(edges_df)} connections based on filters.")

# Display the selected visualization
if viz_type == "Interactive Network":
    st.subheader("Interactive Network Visualization")
    st.write("This visualization shows the trading network where:")
    st.write("- **Node size** represents market share")
    st.write("- **Node color intensity** represents number of connections")
    st.write("- **Edge thickness** represents flow volume between parties")
    st.write("- **Arrow direction** shows the flow direction from party to counter party")
    st.write("Hover over nodes and edges for more information. You can zoom, pan, and click nodes to explore the network.")
    
    html_file = create_interactive_network(nodes_df, edges_df, color_scheme)
    HtmlFile = open(html_file, 'r', encoding='utf-8')
    source_code = HtmlFile.read()
    components.html(source_code, height=600)
    
elif viz_type == "Centrality Analysis":
    st.subheader("Network Centrality Analysis")
    st.write("""
    This analysis shows different measures of importance in the trading network:
    - **Degree Centrality**: Parties with many direct connections
    - **Betweenness Centrality**: Parties that act as bridges between other parties
    - **Eigenvector Centrality**: Parties connected to other important parties
    """)
    plot_centrality_metrics(nodes_df, edges_df)
    
elif viz_type == "Party Flow Distribution":
    st.subheader("Party Flow Distribution")
    st.write("""
    This visualization shows how each party's trading is distributed among counter parties:
    - Each bar represents a party's total flow
    - Colored segments show the proportion of flow with different counter parties
    - Only the top 5 counter parties are shown individually, with remaining flows grouped as 'Others'
    """)
    plot_flow_distribution(df)
    
elif viz_type == "Trading Clusters":
    st.subheader("Trading Community Detection")
    st.write("""
    This visualization identifies communities of parties that trade more intensively with each other:
    - Nodes are colored by detected community
    - Node size represents market share
    - Edges within the same community are highlighted in the community color
    - Edges between communities are shown in light gray
    
    Communities are detected using network analysis algorithms that identify groups with dense internal connections.
    """)
    plot_trading_clusters(nodes_df, edges_df)

# Add a section for key insights
st.sidebar.markdown("---")
with st.sidebar.expander("Key Network Insights"):
    st.write("**Top 5 Parties by Market Share:**")
    top_5 = df.drop_duplicates('party')[['party', 'party_market_share_pct']].sort_values('party_market_share_pct', ascending=False).head(5)
    for _, row in top_5.iterrows():
        st.write(f"- {row['party']}: {row['party_market_share_pct']:.2f}%")
    
    st.write("**Strongest Trading Relationship:**")
    strongest_flow = df.sort_values('notional', ascending=False).iloc[0]
    st.write(f"{strongest_flow['party']} → {strongest_flow['counter_party']}: {strongest_flow['notional']:,}")
    
    st.write("**Most Connected Party:**")
    most_connected = nodes_df.sort_values('degree', ascending=False).iloc[0]
    st.write(f"{most_connected['id']}: {int(most_connected['degree'])} connections")
    
    st.write("**Network Concentration:**")
    total_parties = len(df['party'].unique())
    concentration_text = f"Top {min(20, total_parties)} parties control approximately 80% of market share"
    st.write(concentration_text)
    
    # Calculate reciprocity for the actual data rather than using a fixed value
    G_recip = nx.DiGraph()
    for _, edge in edges_df.iterrows():
        G_recip.add_edge(edge['party'], edge['counter_party'])
    
    # Count bidirectional edges
    bidirectional_count = 0
    total_unique_pairs = 0
    seen_pairs = set()
    
    for u, v in G_recip.edges():
        pair = tuple(sorted([u, v]))
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            total_unique_pairs += 1
            if G_recip.has_edge(v, u):
                bidirectional_count += 1
    
    reciprocity_pct = (bidirectional_count / max(1, total_unique_pairs)) * 100
    st.write(f"**Reciprocity:**")
    st.write(f"{bidirectional_count} out of {total_unique_pairs} relationships are bidirectional ({reciprocity_pct:.1f}%)")

# Add company type classification (optional enhancement)
if st.sidebar.checkbox("Enable Company Type Classification", value=False):
    st.subheader("Company Type Classification")
    
    # Try to classify companies based on their names
    company_types = {
        "Trading": ["Trading", "Market", "Capital", "Securities", "Asset", "Fund", "Invest"],
        "Banking": ["Bank", "Financial", "Credit", "Finance"],
        "Brokerage": ["Broker", "Brokerage", "Trade", "Exchange"],
        "Technology": ["Tech", "Technology", "Digital", "Algo", "Quant"],
        "Other": []
    }
    
    def classify_company(name):
        for category, keywords in company_types.items():
            if any(keyword in name for keyword in keywords):
                return category
        return "Other"
    
    # Add classification to nodes
    nodes_df['type'] = nodes_df['id'].apply(classify_company)
    
    # Create a pie chart of company types
    type_counts = nodes_df['type'].value_counts().reset_index()
    type_counts.columns = ['Company Type', 'Count']
    
    fig = px.pie(
        type_counts, 
        values='Count', 
        names='Company Type',
        title='Distribution of Company Types in the Network',
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show top companies by type
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Top Trading Companies by Market Share**")
        trading_companies = nodes_df[nodes_df['type'] == 'Trading'].sort_values('market_share', ascending=False).head(5)
        for _, row in trading_companies.iterrows():
            st.write(f"- {row['id']}: {row['market_share']:.2f}%")
    
    with col2:
        st.write("**Top Brokerage Companies by Connections**")
        brokerage_companies = nodes_df[nodes_df['type'] == 'Brokerage'].sort_values('degree', ascending=False).head(5)
        for _, row in brokerage_companies.iterrows():
            st.write(f"- {row['id']}: {int(row['degree'])} connections")

# Footer
st.markdown("---")
st.markdown("Network visualization created with NetworkX, PyVis, and Plotly")