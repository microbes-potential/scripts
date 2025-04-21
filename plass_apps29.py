# PlasmidFlow: Final Version with Real-Time Customization, Zoom/Pan, Style Persistence, and Export Option

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import networkx as nx
import io
import base64
import tempfile
import os
import plotly.io as pio
import json

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = "PlasmidFlow"

app.layout = dbc.Container([
    html.Div([
        html.Img(src="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Plasmid_Replication.svg/512px-Plasmid_Replication.svg.png",
                 style={"height": "80px", "margin-bottom": "10px"}),
        html.H1("PlasmidFlow: Visualizing Plasmid-Driven Traits Across Environments",
                className="text-center", style={"color": "#2c3e50"})
    ], style={"textAlign": "center", "marginTop": 30, "backgroundColor": "white"}),

    html.Div([
        html.H4("📂 Upload Your Plasmid Dataset", style={"color": "#2980b9"}),
        html.A("📥 Download Example CSV", href="/assets/plasmidflow_example_input.csv", download="plasmidflow_example_input.csv", target="_blank", style={"display": "block", "marginBottom": "10px", "color": "#16a085"}),
        dcc.Upload(
            id='upload-data',
            children=html.Div(['Drag and Drop or ', html.A('Select a CSV File')]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px', 'borderStyle': 'dashed',
                'borderRadius': '5px', 'textAlign': 'center', 'margin-bottom': '20px'
            },
            multiple=False
        ),
        html.Div(id='output-preview')
    ], style={"backgroundColor": "white", "padding": "20px", "borderRadius": "10px"}),

    dcc.Store(id='stored-data'),
    dcc.Store(id='custom-style', data={
        "node_color": "dodgerblue",
        "edge_color": "gray",
        "node_size": 12,
        "bg_color": "white",
        "font_size": 14
    }),

    html.Div([
        html.H4("🎯 Data Filters", style={"color": "#16a085"}),
        html.Label("Filter by Environment:"),
        dcc.Input(id='env-filter', type='text', placeholder='Type or paste environment name', debounce=True, style={'width': '100%', 'margin-bottom': '10px'}),

        html.Label("Select Traits to Display:"),
        html.Div([
            html.Label("Gene Transfer Flow:"),
            dcc.Checklist(id='sankey-traits', options=[{'label': t, 'value': t} for t in ['ARGs', 'Virulence', 'T4SS', 'MGEs']], value=[]),

            html.Label("Shared Plasmid Network:"),
            dcc.Checklist(id='network-traits', options=[{'label': t, 'value': t} for t in ['ARGs', 'Virulence', 'T4SS', 'MGEs']], value=[]),

            html.Label("Trait Presence Matrix:"),
            dcc.Checklist(id='heatmap-traits', options=[{'label': t, 'value': t} for t in ['ARGs', 'Virulence', 'T4SS', 'MGEs']], value=[]),
        ])
    ], style={'margin-bottom': '20px', 'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px'}),

    dcc.Tabs(id='tabs', value='sankey', children=[
        dcc.Tab(label='🔗 Gene Transfer Flow', value='sankey'),
        dcc.Tab(label='🌐 Shared Plasmid Network', value='network'),
        dcc.Tab(label='🔥 Trait Presence Matrix', value='heatmap')
    ]),

    html.Div(id='tabs-content', style={"backgroundColor": "white", "padding": "20px", "borderRadius": "10px"}),

    html.Div([
        html.H4("🎨 Graph Customization"),
        html.Label("Node Color (name):"),
        dcc.Input(id='style-node-color', type='text', value="dodgerblue", style={"width": "100%"}),

        html.Label("Edge Color (name):"),
        dcc.Input(id='style-edge-color', type='text', value="gray", style={"width": "100%"}),

        html.Label("Node Size:"),
        dcc.Slider(id='style-node-size', min=5, max=30, value=12, step=1),

        html.Label("Background Color (name):"),
        dcc.Input(id='style-bg-color', type='text', value="white", style={"width": "100%"}),

        html.Label("Font Size:"),
        dcc.Slider(id='style-font-size', min=10, max=24, value=14, step=1),

        html.Br(),
        html.Label("Trait Presence Matrix Color Scale:"),
        dcc.Dropdown(
            id='heatmap-colorscale',
            options=[{"label": scale, "value": scale} for scale in ["Blues", "Viridis", "Plasma", "Cividis", "Inferno"]],
            value="Blues"
        ),

        html.Br(),
        html.Button("💾 Save Style", id="save-style-btn", className="btn btn-secondary"),
        html.Button("📂 Load Style", id="load-style-btn", className="btn btn-info", style={"marginLeft": "10px"}),
        dcc.Download(id="download-style"),
        dcc.Upload(id='upload-style', children=html.Div(['Drop or Select Style JSON']), multiple=False, style={
            'width': '100%', 'padding': '10px', 'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '5px', 'textAlign': 'center', 'marginTop': '10px'
        })
    ], style={"backgroundColor": "#f9f9f9", "padding": "20px", "marginTop": "10px", "border": "1px solid #ccc", "borderRadius": "10px"}),

    html.Div([
        html.Label("Download Format:"),
        dcc.RadioItems(id="download-format", options=[
            {"label": "SVG", "value": "svg"},
            {"label": "PNG", "value": "png"},
            {"label": "PDF", "value": "pdf"},
        ], value="png", inline=True),
        dcc.Loading(
            html.Button("Download Current Plot", id="download-btn", className="btn btn-primary mt-2"),
            type="circle",
            color="#2980b9"
        ),
        dcc.Download(id="download-image")
    ], style={"backgroundColor": "white", "padding": "20px", "borderRadius": "10px", "marginTop": "20px"})
], fluid=True)

# === Helper Functions and Callbacks ===

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return pd.read_csv(io.StringIO(decoded.decode('utf-8')))

def filter_by_traits(df, traits):
    for t in traits:
        df = df[df[t].str.lower() != 'no']
    return df

def create_sankey(df, style):
    if df.empty:
        return go.Figure()
    labels = list(pd.unique(df['Host_Genome'].tolist() + df['Plasmid_ID'].tolist() + df['Environment'].tolist()))
    label_map = {label: i for i, label in enumerate(labels)}
    source = df['Host_Genome'].map(label_map)
    target = df['Plasmid_ID'].map(label_map)
    env_source = df['Plasmid_ID'].map(label_map)
    env_target = df['Environment'].map(label_map)
    link_source = pd.concat([source, env_source])
    link_target = pd.concat([target, env_target])
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=style['node_size'],
            line=dict(color="black", width=0.5),
            label=labels,
            color=style['node_color']
        ),
        link=dict(
            source=link_source,
            target=link_target,
            value=[1]*len(link_source),
            color=style['edge_color']
        )
    )])
    fig.update_layout(title_text="Flow of Genetic Material via Plasmids",
                      font_size=style['font_size'], paper_bgcolor=style['bg_color'], margin=dict(l=50, r=50, t=80, b=40))
    return fig

def create_network(df, style):
    if df.empty:
        return go.Figure()
    G = nx.Graph()
    for _, row in df.iterrows():
        G.add_node(row['Plasmid_ID'], type='plasmid')
        G.add_node(row['Environment'], type='environment')
        G.add_edge(row['Plasmid_ID'], row['Environment'])
    pos = nx.spring_layout(G, seed=42, k=0.3/len(G.nodes()) if len(G.nodes()) > 0 else 0.3)
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    node_x, node_y, node_text = [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                             line=dict(width=1, color=style['edge_color']), hoverinfo='none'))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text', text=node_text,
                             textposition="top center",
                             marker=dict(size=style['node_size'], color=style['node_color'])))
    fig.update_layout(title="Network of Shared Plasmids Across Environments",
                      showlegend=False, paper_bgcolor=style['bg_color'],
                      font_size=style['font_size'], margin=dict(l=10, r=10, t=60, b=40),
                      xaxis=dict(showgrid=False, zeroline=False),
                      yaxis=dict(showgrid=False, zeroline=False))
    fig.update_layout(dragmode='pan')
    return fig

def create_heatmap(df, scale, style):
    if df.empty:
        return go.Figure()
    df_melted = df.melt(id_vars=['Plasmid_ID'], value_vars=['ARGs', 'Virulence', 'T4SS', 'MGEs'],
                        var_name='Trait', value_name='Presence')
    df_melted['Binary'] = df_melted['Presence'].apply(lambda x: 1 if str(x).lower() != 'no' else 0)
    heat_df = df_melted.pivot(index='Plasmid_ID', columns='Trait', values='Binary').fillna(0)
    fig = px.imshow(heat_df, text_auto=True, color_continuous_scale=scale, aspect='auto')
    fig.update_layout(title="Presence of Plasmid-Associated Traits",
                      font=dict(size=style['font_size']), paper_bgcolor=style['bg_color'],
                      margin=dict(l=40, r=40, t=60, b=30))
    return fig

@app.callback(
    Output('output-preview', 'children'),
    Output('stored-data', 'data'),
    Input('upload-data', 'contents')
)
def update_output(contents):
    if contents:
        try:
            df = parse_contents(contents)
            if df.empty or 'Plasmid_ID' not in df.columns:
                return html.Div("⚠️ Uploaded file is invalid or missing required columns."), None
            preview = dash_table.DataTable(
                columns=[{"name": i, "id": i} for i in df.columns],
                data=df.to_dict('records'),
                page_size=5,
                style_table={"overflowX": "auto"}
            )
            return preview, df.to_dict('records')
        except Exception as e:
            return html.Div(f"❌ Error reading file: {str(e)}"), None
    return html.Div("📁 Please upload a CSV file to begin."), None

@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs', 'value'),
    Input('custom-style', 'data'),
    State('stored-data', 'data'),
    Input('env-filter', 'value'),
    Input('sankey-traits', 'value'),
    Input('network-traits', 'value'),
    Input('heatmap-traits', 'value'),
    Input('heatmap-colorscale', 'value')
)
def render_content(tab, style, data, selected_env, sankey_traits, network_traits, heatmap_traits, scale):
    if not data:
        return html.Div("Please upload a dataset.")
    df = pd.DataFrame(data)
    if selected_env:
        df = df[df['Environment'].str.contains(selected_env.strip(), case=False, na=False)]
    if tab == 'sankey':
        return dcc.Graph(id='graph', figure=create_sankey(filter_by_traits(df.copy(), sankey_traits), style))
    elif tab == 'network':
        return dcc.Graph(id='graph', figure=create_network(filter_by_traits(df.copy(), network_traits), style))
    elif tab == 'heatmap':
        return dcc.Graph(id='graph', figure=create_heatmap(filter_by_traits(df.copy(), heatmap_traits), scale, style))

@app.callback(
    Output('custom-style', 'data'),
    Input('style-node-color', 'value'),
    Input('style-edge-color', 'value'),
    Input('style-node-size', 'value'),
    Input('style-bg-color', 'value'),
    Input('style-font-size', 'value')
)
def update_style(node_color, edge_color, node_size, bg_color, font_size):
    return {
        "node_color": node_color,
        "edge_color": edge_color,
        "node_size": node_size,
        "bg_color": bg_color,
        "font_size": font_size
    }

@app.callback(
    Output("download-image", "data"),
    Input("download-btn", "n_clicks"),
    State("tabs", "value"),
    State("download-format", "value"),
    State("stored-data", "data"),
    State("heatmap-colorscale", "value"),
    State("custom-style", "data"),
    prevent_initial_call=True
)
def download_plot(n, tab, fmt, data, scale, style):
    df = pd.DataFrame(data)
    if tab == 'sankey':
        fig = create_sankey(df, style)
    elif tab == 'network':
        fig = create_network(df, style)
    elif tab == 'heatmap':
        fig = create_heatmap(df, scale, style)
    try:
        import kaleido  # Ensure kaleido is available
        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
            pio.write_image(fig, tmp.name, format=fmt, width=1200, height=800, scale=2)
            return dcc.send_file(tmp.name)
    except Exception as e:
        return dcc.send_string(f"Error: {str(e)}", filename="error.txt")

@app.callback(
    Output("download-style", "data"),
    Input("save-style-btn", "n_clicks"),
    State("custom-style", "data"),
    prevent_initial_call=True
)
def save_style(n, style):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as tmp:
        json.dump(style, tmp)
        tmp.flush()
        return dcc.send_file(tmp.name)

@app.callback(
    Output("custom-style", "data", allow_duplicate=True),
    Input("upload-style", "contents"),
    State("custom-style", "data"),
    prevent_initial_call=True
)
def load_style(contents, current):
    if contents:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            return json.loads(decoded.decode('utf-8'))
        except Exception:
            return current
    return current

if __name__ == '__main__':
    print("PlasmidFlow is running at http://127.0.0.1:8050")
    app.run(debug=True, port=8050)

