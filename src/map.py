from utils.Jitter import add_jitter
from dash import Dash, html, dcc, Input, Output, callback
from flask_caching import Cache
import pandas as pd
import plotly.express as px
import webbrowser
from threading import Timer
import os


# setup app
port=8050
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)


# setup cache
cache = Cache(app.server, config={
    'DEBUG':True,
    'CACHE_TYPE':'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT':300
})
#cache = Cache(app.server, config={
#    'DEBUG':True,
#    'CACHE_TYPE':'FileSystemCache',
#    'CACHE_DIR':'cache-directory',
#    'CACHE_DEFAULT_TIMEOUT':300
#})


# setup data
@cache.memoize()
def read_data_terror():
    terror_encoding = 'ISO-8859-1'
    df = pd.read_csv("src/data/globalterrorism_2020.csv", encoding=terror_encoding, low_memory=False)
    df_jittered = add_jitter(df, "latitude", "longitude", "latitude_jitter", "longitude_jitter")
    return df_jittered

df_terror = read_data_terror()


# setup layout
app.layout = html.Div([
    html.Div([
        dcc.Graph(
            id='map-scatter',
            hoverData={'points': [{'customdata': 'Denmark'}]}
        )], 
        style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}
    ),

    html.Div([
        dcc.Graph(
            id='map-heatmap',
            hoverData={'points': [{'customdata': 'Denmark'}]}
        )], 
        style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}
    ),

    # use dcc.RangeSlider for selecting an interval of years
    html.Div(
        dcc.RangeSlider(
            id='crossfilter-year-slider',
            min=df_terror['iyear'].min(),
            max=df_terror['iyear'].max(),
            step=None,
            value=[2015, 2020], # default range
            marks={str(year): str(year) for year in df_terror['iyear'].unique()},
            allowCross=False,  # Prevents crossing of the two handles
        ), 
        style={'width': '49%', 'padding': '0px 20px 20px 20px'}
    ),

    # set dropdown to choose attacktype
    # can choose multiple types and can't clear value to being empty
    html.Div(
        dcc.Dropdown(
            id='crossfilter-attacktype-dropdown',
            options=list(df_terror['attacktype1_txt'].unique()),
            value=None,
            placeholder='Show All Attack Types',
            multi=True,
            clearable=False,
            maxHeight=200,
            optionHeight=35
        ),
        style={'width': '30%', 'padding': '0px 20px 20px 20px'}
    )
])


# filter data but memoize with cache for rapid access
@cache.memoize()
def filter_map_data(df, year_range, attacktype):
    year_lower, year_upper = year_range

    df_filtered = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]

    if attacktype is not None:
        if len(attacktype) > 0:
            df_filtered = df_filtered[df_filtered['attacktype1_txt'].isin(attacktype)]

    return df_filtered


@callback(
    Output('map-scatter', 'figure'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'))
def update_graph(year_range, attacktype):
    # get cached data
    dff = filter_map_data(df_terror, year_range, attacktype)

    # plot scatter world map
    fig = px.scatter_geo(dff,
                         lat="latitude_jitter",
                         lon="longitude_jitter",
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
    Output('map-heatmap', 'figure'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'))
def update_heatmap(year_range, attacktype):
    # get cached data
    dff = filter_map_data(df_terror, year_range, attacktype)

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
                         lat="latitude_jitter",
                         lon="longitude_jitter",
                         radius=10,
                         center=dict(lat=0, lon=0), 
                         zoom=0,
                         map_style="open-street-map", # "satellite-streets" #"open-street-map",
                         color_continuous_scale=color_scale,
                         opacity=1,
                         range_color=(0, max_density)
    )

    # update hover box
    fig.update_traces(customdata=dff[['country_txt', 'iday', 'imonth', 'iyear', 'gname', 
                                      'attacktype1_txt', 'weaptype1_txt', 'targtype1_txt']],
                      hovertemplate="<b>%{customdata[0]} %{customdata[1]}-%{customdata[2]}-%{customdata[3]}</b><br>"
                                    "Group: %{customdata[4]}<br>"
                                    "Primary attack type: %{customdata[5]}<br>"
                                    "Primary weapon type used: %{customdata[6]}<br>"
                                    "Primary target type: %{customdata[7]}<br>")

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