from utils.Jitter import add_jitter
from dash import Dash, html, dcc, Input, Output, State, callback, no_update
import dash_core_components as dcc
from flask_caching import Cache
import pandas as pd
import plotly.express as px
import webbrowser
from threading import Timer
import os

import plotly.graph_objects as go


###################
#  setup app
port=8050
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)


###################
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


###################
# setup data
@cache.memoize()
def read_data_terror():
    df = pd.read_csv("src/data/globalterrorism_2020_cleaned.csv")
    df_jittered = add_jitter(df, "latitude", "longitude", "latitude_jitter", "longitude_jitter")
    return df_jittered

df_terror = read_data_terror()


###################
# filter data
@cache.memoize()
def filter_years(df, year_range):
    year_lower, year_upper = year_range
    df_filtered = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]
    return df_filtered


@cache.memoize()
def filter_data(df, year_range, attacktype, targettype, group):
    # filter years
    df_filtered = filter_years(df, year_range)

    # filter attack
    if attacktype is not None:
        if len(attacktype) > 0:
            df_filtered = df_filtered[df_filtered['attacktype1_txt'].isin(attacktype)]
    
    # filter target
    if targettype is not None:
        if len(targettype) > 0:
            df_filtered = df_filtered[df_filtered['targtype1_txt'].isin(targettype)]

    # filter group
    if group is not None:
        if len(group) > 0:
            df_filtered = df_filtered[df_filtered['gname'].isin(group)]
    
    return df_filtered


###################
# setup filters
@callback(
    Output('crossfilter-group-container', 'children'),
    Input('crossfilter-year-slider', 'value')
)
def update_group_dropdown(year_range):
    # filter years
    df_filtered = filter_years(df_terror, year_range)

    # count number of attacks for groups
    groups_counts = df_filtered.groupby(['gname'])['gname'].count()

    # sort ascending
    groups_sorted = groups_counts.sort_values(ascending=False)

    # Format required by dcc.Dropdown (label-value pairs)
    options = [{'label': group, 'value': group} for group in groups_sorted.index]
    
    # Return the dcc.Dropdown component with the computed options
    return dcc.Dropdown(
        id='crossfilter-group-dropdown',
        options=options,
        value=None,
        placeholder='Show All Terror Groups',
        multi=True,
        clearable=False,
        maxHeight=200,
        optionHeight=35
    )


###################
# setup layout
app.layout = html.Div([
    # Slider and Dropdown on the left side, above the heatmap
    html.Div([
        html.Div([
            dcc.RangeSlider(
                id='crossfilter-year-slider',
                min=df_terror['iyear'].min(),
                max=df_terror['iyear'].max(),
                step=None,
                value=[2015, 2020],  # default range
                marks={str(year): str(year) if year % 5 == 0 else '' for year in df_terror['iyear'].unique()},
                allowCross=False  # Prevents crossing of the two handles
            )
        ], style={'width': '86%', 'padding': '20px', 'margin-left': '-25px'}),

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
            style={'width': '80%', 'padding': '20px'}
        ),

        # set dropdown to choose target type
        # can choose multiple types and can't clear value to being empty
        html.Div(
            dcc.Dropdown(
                id='crossfilter-targettype-dropdown',
                options=list(df_terror['targtype1_txt'].unique()),
                value=None,
                placeholder='Show All Target Types',
                multi=True,
                clearable=False,
                maxHeight=200,
                optionHeight=35
            ),
            style={'width': '80%', 'padding': '20px'}
        ),

        # set dropdown to choose group
        # can choose multiple types and can't clear value to being empty
        html.Div(
            id='crossfilter-group-container',
            children=update_group_dropdown(year_range=[2015, 2020]),
            style={'width': '80%', 'padding': '20px'}
        ),

        # Heatmap below the Slider and Dropdown
        html.Div([
            dcc.Store(id='map-state', data={'zoom':0, 'center':dict(lat=0, lon=0)}),
            dcc.Graph(
                id='map-heatmap',
                hoverData=None,
                clickData=None
            )
        ], style={'padding': '0', 'width': '100%', 'position': 'relative', 'left': '-50px'})  # Keep the heatmap shifted to the left
    ], style={'width': '49%', 'display': 'inline-block', 'vertical-align': 'top', 'padding': '0 10px'}),  # Reverted the padding for left container

    # Right side - infobox and bar chart stacked vertically
    html.Div([
        # Infobox at the top with scrolling enabled
        html.Div([
            html.H4("Selected Attack Information", id="info-title"),
            html.Div(id='info-box', style={
                'padding': '10px',
                'border': '1px solid black',
                'height': '200px',
                'max-height': '200px',  # Ensure the height is fixed
                'overflow-y': 'scroll'  # Enable scrolling
            })
        ], style={'padding': '0 20'}),

        # Bar chart below the infobox
        html.Div([
            dcc.Graph(
                id='chart-weapon-distribution'
            )
        ], style={'padding': '0 20', 'marginTop': '20px'})  # Adjust padding and margin to space them out
    ], style={'width': '49%', 'display': 'inline-block', 'vertical-align': 'top'})  # Right side remains the same width
], style={'display': 'flex', 'flex-direction': 'row', 'margin': '0', 'padding': '0'})  # Set margin and padding to 0 for the entire layout


###################
# update graphs
@callback(
    Output('map-heatmap', 'figure'),
    State('map-state', 'data'), # can read state but can't be triggered by state change
    Input('map-heatmap', 'clickData'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'))
def update_map_heatmap(map_state, clickData, year_range, attacktype, targettype, group):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, targettype, group)
    
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
    
    # ensure that map is drawn in same state prior to update

    zoom = map_state['zoom']
    center = map_state['center']

    # Create a scatter_geo plot, simulating a heatmap by coloring points based on density
    fig = px.density_map(dff,
                         lat="latitude_jitter",
                         lon="longitude_jitter",
                         radius=10,
                         center=center, #dict(lat=0, lon=0)
                         zoom=zoom, # 0
                         map_style="open-street-map", # "satellite-streets" #"open-street-map",
                         color_continuous_scale=color_scale,
                         opacity=1,
                         range_color=(0, max_density)
    )

    # update hover box
    fig.update_traces(customdata=dff[['country_txt', 'iday', 'imonth', 'iyear',
                                      'summary', 'crit1', 'crit2', 'crit3', 'related', 'region_txt',# 'provstate', 'city', 
                                      'attacktype1_txt', #'attacktype2_txt', 'attacktype3_txt',
                                      'success', 'suicide',
                                      'weaptype1_txt', 'weapsubtype1_txt', #'weaptype2_txt', 'weapsubtype2_txt', 'weaptype3_txt', 'weapsubtype3_txt',
                                      'targtype1_txt', 'targsubtype1_txt', #'targtype2_txt', 'targsubtype2_txt', 'targtype3_txt', 'targsubtype3_txt',
                                      'corp1', #'corp2', 'corp3',
                                      'target1', #'target2', 'target3',
                                      'natlty1_txt', #'natlty2_txt', 'natlty3_txt',
                                      'gname', 'guncertain1', 'nperps', 'motive',
                                      'nkill', 'nkillter', 'nwound', 'nwoundte', 'property', 'propvalue', 'ishostkid', 'nhostkid', 'nhours', 'ndays',
                                      'flag']],
                      # update hover box
                      hovertemplate="<b>%{customdata[0]} %{customdata[1]}-%{customdata[2]}-%{customdata[3]}</b><br>"
                                    "Group: %{customdata[20]}<br>"
                                    "Attack type: %{customdata[10]}<br>"
                                    "Weapon type: %{customdata[13]}<br>"
                                    "Target type: %{customdata[15]}<br>")


    # Update layout to add a title to the legend
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Number of attacks",  # Set the title for the colorbar (legend)
            titleside="right",  # Position the title on the right side
        )
    )

    # draw lines to related attacks
    if clickData:
        # get current point
        clicked_lat = clickData['points'][0]['lat']
        clicked_lon = clickData['points'][0]['lon']
        related = clickData['points'][0]['customdata'][8]
        if related:
            # format ids of related attacks
            related_split = related.split(', ')
            related_split = [int(r) for r in related_split]
            # get information from related attacks
            related_gps = dff[dff['eventid'].isin(related_split)][['eventid', 'latitude_jitter', 'longitude_jitter']]
            # highlight all related attacks
            fig.add_trace(
                go.Scattermap(
                    mode='markers',
                    lon=related_gps['longitude_jitter'],
                    lat=related_gps['latitude_jitter'],
                    hoverinfo='skip',
                    marker=dict(color='black', opacity=0.7, size=10)
                )
            )
            for idx, (_, row) in  enumerate(related_gps.iterrows()):
                # draw lines to all related attacks
                fig.add_trace(
                    go.Scattermap(
                        mode='lines',
                        lon=[clicked_lon, row['longitude_jitter']],
                        lat=[clicked_lat, row['latitude_jitter']],
                        line=dict(width=2, color='black'),
                        opacity=0.7,
                        name=f'Related {idx+1}',
                        hoverinfo='skip', # no hover info
                        showlegend=False # don't show in legend
                    ),
                )

    return fig


@callback(
    Output('map-state', 'data'),
    Input('map-heatmap', 'relayoutData'),
    prevent_initial_call=True
)
def update_map_state(relayoutData):
    if relayoutData:
        return {'zoom': relayoutData.get('map.zoom'), 
                'center': relayoutData.get('map.center')}
    return no_update


@callback(
    Output('info-box', 'children'),
    Input('map-heatmap', 'clickData'))
def update_info_box(clickData):
    if clickData is None:
        return "Click on an attack to see details."

    # Extract custom data from clickData
    point_data = clickData['points'][0]['customdata']

    # Overall details
    country = point_data[0]
    day = point_data[1]
    month = point_data[2]
    year = point_data[3]
    summary = point_data[4]
    crit1 = point_data[5]
    crit2 = point_data[6]
    crit3 = point_data[7]
    related = point_data[8]
    region_txt = point_data[9]
    #provstate = point_data[10]
    #city = point_data[11]
    
    # Attack types
    attacktype1 = point_data[10]
    #attacktype2 = point_data[13]
    #attacktype3 = point_data[14]
    
    # Success and suicide
    success = point_data[11]
    suicide = point_data[12]
    
    # Weapon types and subtypes
    weaptype1 = point_data[13]
    weapsubtype1 = point_data[14]
    #weaptype2 = point_data[19]
    #weapsubtype2 = point_data[20]
    #weaptype3 = point_data[21]
    #weapsubtype3 = point_data[22]
    
    # Target types and subtypes
    targtype1 = point_data[15]
    targsubtype1 = point_data[16]
    #targtype2 = point_data[25]
    #targsubtype2 = point_data[26]
    #targtype3 = point_data[27]
    #targsubtype3 = point_data[28]
    
    # Corporate 
    corp1 = point_data[17]
    #corp2 = point_data[30]
    #corp3 = point_data[31]
    
    # Target
    target1 = point_data[18]
    #target2 = point_data[33]
    #target3 = point_data[34]
    
    # Target nationaly
    natlty1 = point_data[19]
    #natlty2 = point_data[36]
    #natlty3 = point_data[37]
    
    # Groups
    group = point_data[20]
    guncertain = point_data[21]
    nperps = point_data[22]
    motive = point_data[23]
    
    # Casualties and injuries
    nkill = point_data[24]
    nkillter = point_data[25]
    nwound = point_data[26]
    nwoundte = point_data[27]
    
    # Property damage
    property = point_data[28]
    propvalue = point_data[29]
    
    # Hostage information
    ishostkid = point_data[30]
    nhostkid = point_data[31]
    nhours = point_data[32]
    ndays = point_data[33]
    
    # Flag
    flag = point_data[34]

    # Return a formatted string to display in the info box
    info_content = html.Div([
        html.P(f"Country: {country} {flag}"),
        html.P(f"Date: {day}-{month}-{year}"),
        html.P(f"Group: {group}"),
        html.P(f"Attack Type: {attacktype1}"),
        html.P(f"Weapon Type: {weaptype1}"),
        html.P(f"Target Type: {targtype1}"),
        html.P(summary)
    ])

    return info_content


@callback(
    Output('chart-weapon-distribution', 'figure'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'))
def update_chart_weapon_distribution(year_range, attacktype, targettype, group):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, targettype, group)
    # count number of attacks per primary weapon type
    dff_grouped = dff.groupby(['weaptype1_txt'])['weaptype1_txt'].count()
    dff_grouped = dff_grouped.to_frame(name='count').reset_index()
    # calculate percentage and round to 2 decimals
    dff_grouped['percentage'] = dff_grouped['count']/dff_grouped['count'].sum()
    dff_grouped['percentage'] = (100*dff_grouped['percentage']).round(1)
    # change long Vehicle string to Vehicle
    dff_grouped.loc[dff_grouped['weaptype1_txt'].str.contains('Vehicle'), 'weaptype1_txt'] = 'Vehicle'
    # add year range ex. 2015-2020 or just 2020 for use in info box
    if year_range[1]-year_range[0]==0:
        dff_grouped['year_range'] = str(year_range[0])
    else:
        dff_grouped['year_range'] = str(year_range[0])+'-'+str(year_range[1])

    # sort by ascending count
    dff_sorted = dff_grouped.sort_values(by=['count'], ascending=True)

    fig = px.bar(dff_sorted, 
                 x='count', 
                 y='weaptype1_txt', 
                 orientation='h',
                 text='count',
                 text_auto=True
    )

    fig.update_traces(customdata=dff_sorted[['weaptype1_txt', 'count', 'percentage', 'year_range']],
                      hovertemplate=(
                          "%{customdata[0]} was the primary weapon type<br>"
                          "in %{customdata[2]}% of filtered attacks in %{customdata[3]}.")
    )

    fig.update_layout(
        title='Which weapons are used most frequently?',
        yaxis_title='',
        xaxis_title='Number of attacks',
        title_x=0.5
    )
    
    return fig


###################
# deploy app
def open_browser():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
	    webbrowser.open_new("http://localhost:{}".format(port))


if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, port=port)