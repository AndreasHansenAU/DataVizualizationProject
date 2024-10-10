from dash import Dash, html, dcc, Input, Output, callback
import pandas as pd
import plotly.express as px
import webbrowser
from threading import Timer
import os

port=8050
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)

terror_encoding = 'ISO-8859-1'
df = pd.read_csv("src/data/globalterrorism_2020.csv", encoding=terror_encoding, low_memory=False)

app.layout = html.Div([
    html.Div([
        dcc.Graph(
            id='crossfilter-indicator-scatter',
            hoverData={'points': [{'customdata': 'Denmark'}]}
        )
    ], style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}),

    html.Div([
        dcc.Graph(
            id='crossfilter-indicator-heatmap',
        )
    ], style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}),

    # Use dcc.RangeSlider for selecting an interval of years
    html.Div(dcc.RangeSlider(
        id='crossfilter-year--slider',
        min=df['iyear'].min(),
        max=df['iyear'].max(),
        step=None,
        value=[2000, 2020], # default range
        marks={str(year): str(year) for year in df['iyear'].unique()},
        allowCross=False,  # Prevents crossing of the two handles
    ), style={'width': '49%', 'padding': '0px 20px 20px 20px'})
])

@callback(
    Output('crossfilter-indicator-scatter', 'figure'),
    Input('crossfilter-year--slider', 'value'))
def update_graph(year_range):
    # subset dataframe by year range
    year_lower = year_range[0]
    year_upper = year_range[1]
    dff = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]

    # plot scatter world map
    fig = px.scatter_geo(dff,
                         lon="longitude",
                         lat="latitude",
                         #text="country_txt",
                         hover_name="country_txt",
                         hover_data={"imonth": True, "iday": True, "gname": True}
    )
    
    fig.update_traces(customdata=dff[['imonth', 'iday', 'gname']],
                      hovertemplate="<b>%{hovertext}</b><br>"
                                    "Month: %{customdata[0]}<br>"
                                    "Day: %{customdata[1]}<br>"
                                    "Group: %{customdata[2]}")
    
    fig.update_layout(
        geo=dict(
            showland=True,  # Show land
            landcolor="lightgray",  # Set land color
            showcountries=True,  # Show country borders
            countrycolor="black",  # Set country border color
            showocean=True,  # Show ocean
            oceancolor="lightblue",  # Set ocean color
            showframe=False,  # Hide the frame around the map
            coastlinecolor="black",  # Set coastline color
        ),
    )

    return fig

@callback(
    Output('crossfilter-indicator-heatmap', 'figure'),
    Input('crossfilter-year--slider', 'value'))
def update_heatmap(year_range):
    # subset dataframe by year range
    year_lower = year_range[0]
    year_upper = year_range[1]
    dff = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]

    # Plotly3 color scale
    color_scale = [
        [0.0,  "rgba(0, 0, 0, 0)"],
        [0.01, "#0508b8"],
        [0.3,  "#6b1cfb"],
        [0.6,  "#dd2bfd"],
        [1.0,  "#fec3fe"]
    ]

    # maximum scale value
    max_density = 50

    # Create a scatter_geo plot, simulating a heatmap by coloring points based on density
    fig = px.density_map(dff,
                         lon="longitude",
                         lat="latitude",
                         radius=10,
                         center=dict(lat=0, lon=0), 
                         zoom=0,
                         map_style="open-street-map", # "satellite-streets" #"open-street-map",
                         color_continuous_scale=color_scale,
                         opacity=1,
                         range_color=(0, max_density)
    )

    # Update layout to add a title to the legend
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Number of attacks",  # Set the title for the colorbar (legend)
            titleside="right",  # Position the title on the right side
        )
    )
    
    return fig


def open_browser():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
	    webbrowser.open_new("http://localhost:{}".format(port))


if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, port=port)