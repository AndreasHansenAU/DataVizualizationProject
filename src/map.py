from utils.Jitter import *
from dash import Dash, html, dcc, ctx, Input, Output, State, callback, no_update
import dash_core_components as dcc
from flask_caching import Cache
import pandas as pd
import plotly.express as px
import webbrowser
from threading import Timer
import os
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
import numpy as np
np.random.seed(42)


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
    df_jittered = add_jitter_coordinates(df, "latitude", "longitude", "latitude_jitter", "longitude_jitter")
    df_jittered = add_jitter_beeswarm(df_jittered, jitter_amount=0.2)
    return df_jittered


df_terror = read_data_terror()
df_terror.loc[df_terror['weaptype1_txt'].str.contains('Vehicle'), 'weaptype1_txt'] = 'Vehicle'

all_attacktypes = pd.Series(df_terror['attacktype1_txt'].unique(), name='attacktype1_txt')
all_weapontypes = pd.DataFrame(df_terror['weaptype1_txt'].unique(), columns=['weaptype1_txt'])
all_targettypes = pd.Series(df_terror['targtype1_txt'].unique(), name='targtype1_txt')

all_countries = df_terror[['country_txt', 'region_txt']].drop_duplicates().reset_index(drop=True)

customdata_list = ['eventid', 'latitude_jitter', 'longitude_jitter', 
                   'iday', 'imonth', 'iyear',
                   'country_txt', 'region_txt', 'provstate', 'city', 
                   'summary', 'crit1', 'crit2', 'crit3', 'related',
                   'attacktype1_txt', #'attacktype2_txt', 'attacktype3_txt',
                   'success', 'suicide',
                   'weaptype1_txt', 'weapsubtype1_txt', #'weaptype2_txt', 'weapsubtype2_txt', 'weaptype3_txt', 'weapsubtype3_txt',
                   'targtype1_txt', 'targsubtype1_txt', #'targtype2_txt', 'targsubtype2_txt', 'targtype3_txt', 'targsubtype3_txt',
                   'corp1', #'corp2', 'corp3',
                   'target1', #'target2', 'target3',
                   'natlty1_txt', #'natlty2_txt', 'natlty3_txt',
                   'gname', 'guncertain1', 'nperps', 'motive',
                   'nkill', 'nkillter', 'nwound', 'nwoundte', 'property', 'propvalue', 'ishostkid', 'nhostkid', 'nhours', 'ndays',
                   'flag']


###################
# filter data
@cache.memoize()
def filter_years(df, year_range):
    year_lower, year_upper = year_range
    df_filtered = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]
    return df_filtered

@cache.memoize()
def filter_casualties(df, casualty_lower, casualty_upper):
    if casualty_lower == None or casualty_upper == None:
        return df
    df_filtered = df[(df['total_casualties'] >= casualty_lower) & (df['total_casualties'] <= casualty_upper)]
    return df_filtered

@cache.memoize()
def filter_data(df, year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group):
    # filter years
    df_filtered = filter_years(df, year_range)
    df_filtered = filter_casualties(df_filtered, casualty_lower, casualty_upper)

    # filter attack
    if attacktype is not None:
        if len(attacktype) > 0:
            df_filtered = df_filtered[df_filtered['attacktype1_txt'].isin(attacktype)]
    
    if weapontype is not None:
        if len(weapontype) > 0:
            df_filtered = df_filtered[df_filtered['weaptype1_txt'].isin(weapontype)]
    
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
    Output('crossfilter-summary-container', 'children'),
    State('crossfilter-summary-dropdown', 'value'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-casualty-lower', 'value'),
    Input('crossfilter-casualty-upper', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-weapontype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'),
)
def update_summary_dropdown(summary_selections, year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group):
    # filter
    df_notna = df_terror[df_terror['summary'].notna()]
    df_filtered = filter_data(df_notna, year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group)

    if len(df_filtered) > 10000:
        options = [{'label': 'Please apply more filters to narrow down your search...', 'value': 'none', 'disabled': True}]
    else:
        # Find total casualties for each summary
        summary_casualties = df_filtered.groupby(['summary'])['total_casualties'].sum()
        # sort ascending
        summaries_sorted = summary_casualties.sort_values(ascending=False)
        # Format required by dcc.Dropdown (label-value pairs)
        options = [{'label': summary, 'value': summary} for summary in summaries_sorted.index]
    
    # Return the dcc.Dropdown component with the computed options
    return dcc.Dropdown(
        id='crossfilter-summary-dropdown',
        options=options,
        value=summary_selections,
        placeholder='Find an attack using keywords',
        multi=False,
        clearable=True,
        maxHeight=200,
        optionHeight=35,
        style={
        'whiteSpace': 'nowrap',   # Allow text to wrap naturally
        'display': 'block'        # Each selected item on its own line
        }
    )


@callback(
    Output('crossfilter-group-container', 'children'),
    State('crossfilter-group-dropdown', 'value'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-casualty-lower', 'value'),
    Input('crossfilter-casualty-upper', 'value'),
)
def update_group_dropdown(group_selections, year_range, casualty_lower, casualty_upper):
    # filter years
    df_filtered = filter_years(df_terror, year_range)
    df_filtered = filter_casualties(df_filtered, casualty_lower, casualty_upper)

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
        value=group_selections,
        placeholder='Show All Terror Groups',
        multi=True,
        clearable=False,
        maxHeight=200,
        optionHeight=35
    )

@callback(
    Output('crossfilter-casualty-upper', 'value'),
    Input('crossfilter-casualty-lower', 'value'),
    State('crossfilter-casualty-upper', 'value')
)
def adjust_upper_casualty_input(casualty_lower, casualty_upper):
    # If casualty_lower is higher than casualty_upper, set casualty_upper to max_casualties
    if casualty_lower is not None and casualty_upper is not None and casualty_lower > casualty_upper:
        return df_terror['total_casualties'].max()
    # No update if conditions aren't met
    raise PreventUpdate


###################
# setup layout
app.layout = html.Div([
    dcc.Store(
        id='global-clickData'
    ),

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

        html.Div([
            html.Label("Specify Casualty Range:"),
            dcc.Input(
                id='crossfilter-casualty-lower',
                type='number',
                placeholder='Lower bound',
                min=0,
                max=df_terror['total_casualties'].max(),
                value=0,
                style={'width': '40%', 'margin-right': '10px'}
            ),
            dcc.Input(
                id='crossfilter-casualty-upper',
                type='number',
                placeholder='Upper bound',
                min=0,
                value=df_terror['total_casualties'].max(),
                style={'width': '40%'}
            )
        ], style={'width': '86%', 'padding': '20px', 'margin-left': '-25px'}),

        html.Div(
            id='crossfilter-summary-container',
            children=update_summary_dropdown(None, [2015, 2020], 0, df_terror['total_casualties'].max(), None, None, None, None),
            style={'width': '80%', 'padding': '5px', 'whiteSpace': 'nowrap'}
        ),

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
            style={'width': '80%', 'padding': '5px'}
        ),

        html.Div(
            dcc.Dropdown(
                id='crossfilter-weapontype-dropdown',
                options=list(df_terror['weaptype1_txt'].unique()),
                value=None,
                placeholder='Show All Weapon Types',
                multi=True,
                clearable=False,
                maxHeight=200,
                optionHeight=35
            ),
            style={'width': '80%', 'padding': '5px'}
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
            style={'width': '80%', 'padding': '5px'}
        ),

        # set dropdown to choose group
        # can choose multiple types and can't clear value to being empty
        html.Div(
            id='crossfilter-group-container',
            children=update_group_dropdown(None, [2015, 2020], 0, df_terror['total_casualties'].max()),
            style={'width': '80%', 'padding': '5px'}
        ),

        html.Div([
            dcc.RadioItems(
                id='toggle-metric',
                options=[
                    {'label': 'Show Number of Attacks', 'value': 'attacks'},
                    {'label': 'Show Total Casualties', 'value': 'casualties'}
                ],
                value='attacks', # default
                inline=False
            )
        ], style={'padding': '10px', 'display': 'inline-block'}),

        # Heatmap below the Slider and Dropdown
        html.Div([
            dcc.Store(id='map-state', data={'zoom':0, 'center':dict(lat=0, lon=0)}),
            dcc.Graph(
                id='map-heatmap',
                hoverData=None,
                clickData=None
            )
        ], style={'padding': '0', 'width': '100%', 'position': 'relative', 'left': '-50px'}),  # Keep the heatmap shifted to the left

        html.Div([
            dcc.Graph(
                id='chart-parallel-sets'
            )
        ], style={'padding': '0', 'width': '100%', 'position': 'relative'})
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

        html.Div([
            dcc.Graph(
                id='chart-beeswarm',
                clickData=None,
                hoverData=None
            )
        ], style={'padding': '0', 'width': '100%', 'position': 'relative'})
    ], style={'width': '49%', 'display': 'inline-block', 'vertical-align': 'top'})  # Right side remains the same width
], style={'display': 'flex', 'flex-direction': 'row', 'margin': '0', 'padding': '0'})  # Set margin and padding to 0 for the entire layout


###################
# update graphs
@callback(
    Output('global-clickData', 'data'),
    Input('map-heatmap', 'clickData'),
    Input('chart-beeswarm', 'clickData')
)
def update_global_clickdata(map_clickData, beeswarm_clickData):
    global_clickData = None

    # update global click data based on which event triggered a callback
    trigger = list(ctx.triggered_prop_ids.keys())
    if 'map-heatmap.clickData' in trigger:
        global_clickData = map_clickData['points'][0]['customdata']
    elif 'chart-beeswarm.clickData' in trigger:
        global_clickData = beeswarm_clickData['points'][0]['customdata']
    
    return global_clickData

@callback(
    Output('map-heatmap', 'figure'),
    State('map-state', 'data'), # can read state but can't be triggered by state change
    Input('global-clickData', 'data'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-casualty-lower', 'value'),
    Input('crossfilter-casualty-upper', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-weapontype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'),
    Input('toggle-metric', 'value'),
    running=[(Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)],
    prevent_initial_call=True)
def update_map_heatmap(map_state, clickData, year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group, metric):
    # get cached data
    dff = filter_data(df_terror, year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group)
    
    if metric == 'casualties':
        z_value = 'total_casualties'
        max_density = 200
        colorbar_title = "Total Casualties"
    else:
        z_value = None
        max_density = 200
        colorbar_title = "Number of Attacks"

    # Plotly3 color scale
    color_scale = [
        [0.0,  "rgba(0, 0, 0, 0)"],
        [0.01, "#0508b8"],
        [0.3,  "#6b1cfb"],
        [0.6,  "#dd2bfd"],
        [1.0,  "#fec3fe"]
    ]
    
    # ensure that map is drawn in same state prior to update
    trigger = list(ctx.triggered_prop_ids.keys())
    if 'global-clickData.data' in trigger and clickData is not None:
        clicked_lat = clickData[1]
        clicked_lon = clickData[2]
        zoom = 7
        center = {'lat':clicked_lat, 'lon':clicked_lon}
    else:
        zoom = map_state['zoom']
        center = map_state['center']

    # Create a scatter_geo plot, simulating a heatmap by coloring points based on density
    fig = px.density_map(dff,
                         lat="latitude_jitter",
                         lon="longitude_jitter",
                         z=z_value,
                         radius=10,
                         center=center,
                         zoom=zoom,
                         map_style="open-street-map", # "satellite-streets" #"open-street-map",
                         color_continuous_scale=color_scale,
                         opacity=1,
                         range_color=(0, max_density)
    )

    # update hover box
    fig.update_traces(customdata=dff[customdata_list],
                      # update hover box
                      hovertemplate="<b>%{customdata[3]}-%{customdata[4]}-%{customdata[5]} %{customdata[9]}, %{customdata[6]}</b><br>"
                                    "Group: %{customdata[25]}<br>"
                                    "Attack type: %{customdata[15]}<br>"
                                    "Weapon type: %{customdata[18]}<br>"
                                    "Target type: %{customdata[20]}<br>")


    # Update layout to add a title to the legend
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=colorbar_title,  # Set the title for the colorbar (legend)
            titleside="right",  # Position the title on the right side
        )
    )

    # draw lines to related attacks and draw clicked point
    if clickData:
        # get current point
        clicked_lat = clickData[1]
        clicked_lon = clickData[2]
        related = clickData[14]
        if related:
            # format ids of related attacks
            related_split = related.split(', ')
            related_split = [int(r) for r in related_split]
            # get information from related attacks
            related_gps = dff[dff['eventid'].isin(related_split)][['eventid', 'latitude_jitter', 'longitude_jitter']]
            for idx, (_, row) in  enumerate(related_gps.iterrows()):
                # highlight related attacks and draw lines to them
                fig.add_trace(
                    go.Scattermap(
                        mode='lines+markers',
                        lon=[clicked_lon, row['longitude_jitter']],
                        lat=[clicked_lat, row['latitude_jitter']],
                        line=dict(width=3, color='black'),
                        marker=dict(size=10, color='black'),
                        opacity=0.8,
                        name=f'Related {idx+1}',
                        hoverinfo='skip', # no hover info
                        showlegend=False # don't show in legend
                    ),
                )
        # plot clicked point if it's still in the filtered data
        clicked_eventid = clickData[0]
        is_eventid_present = dff['eventid'].isin([clicked_eventid]).any()
        if is_eventid_present:
            fig.add_trace(
                go.Scattermap(
                    mode='markers',
                    lon=[clicked_lon],
                    lat=[clicked_lat],
                    marker=dict(size=10, color='red'),
                    opacity=0.8,
                    hoverinfo='skip', # no hover info
                    showlegend=False # don't show in legend
                ),
            )
    return fig


@callback(
    Output('map-state', 'data'),
    Input('map-heatmap', 'relayoutData'),
    Input('global-clickData', 'data'),
    prevent_initial_call=True
)
def update_map_state(relayoutData, clickData):
    trigger = list(ctx.triggered_prop_ids.keys())

    # if triggered by click then update state to clicked points location
    if 'global-clickData.data' in trigger and clickData is not None:
        clicked_lat = clickData[1]
        clicked_lon = clickData[2]
        return {'zoom': 7,
                'center': {'lat':clicked_lat, 'lon':clicked_lon}}

    # if triggered by relayout then update state
    if 'map-heatmap.relayoutData' in trigger:
        return {'zoom': relayoutData.get('map.zoom'), 
                'center': relayoutData.get('map.center')}
    
    return no_update


@callback(
    Output('info-box', 'children'),
    Input('global-clickData', 'data'))
def update_info_box(clickData):
    if clickData is None:
        return "Click on an attack to see details."

    # Overall details
    eventid = clickData[0]
    latitude_jitter = clickData[1]
    longitude_jitter = clickData[2]
    day = clickData[3]
    month = clickData[4]
    year = clickData[5]
    country = clickData[6]
    region = clickData[7]
    provstate = clickData[8]
    city = clickData[9]
    summary = clickData[10]
    crit1 = clickData[11]
    crit2 = clickData[12]
    crit3 = clickData[13]
    related = clickData[14]
    
    # Attack types
    attacktype1 = clickData[15]
    #attacktype2 = point_data[13]
    #attacktype3 = point_data[14]
    
    # Success and suicide
    success = clickData[16]
    suicide = clickData[17]
    
    # Weapon types and subtypes
    weaptype1 = clickData[18]
    weapsubtype1 = clickData[19]
    #weaptype2 = point_data[19]
    #weapsubtype2 = point_data[20]
    #weaptype3 = point_data[21]
    #weapsubtype3 = point_data[22]
    
    # Target types and subtypes
    targtype1 = clickData[20]
    targsubtype1 = clickData[21]
    #targtype2 = point_data[25]
    #targsubtype2 = point_data[26]
    #targtype3 = point_data[27]
    #targsubtype3 = point_data[28]
    
    # Corporate 
    corp1 = clickData[22]
    #corp2 = point_data[30]
    #corp3 = point_data[31]
    
    # Target
    target1 = clickData[23]
    #target2 = point_data[33]
    #target3 = point_data[34]
    
    # Target nationaly
    natlty1 = clickData[24]
    #natlty2 = point_data[36]
    #natlty3 = point_data[37]
    
    # Groups
    group = clickData[25]
    guncertain = clickData[26]
    nperps = clickData[27]
    motive = clickData[28]
    
    # Casualties and injuries
    nkill = clickData[29]
    nkillter = clickData[30]
    nwound = clickData[31]
    nwoundte = clickData[32]
    
    # Property damage
    property = clickData[33]
    propvalue = clickData[34]
    
    # Hostage information
    ishostkid = clickData[35]
    nhostkid = clickData[36]
    nhours = clickData[37]
    ndays = clickData[38]
    
    # Flag
    flag = clickData[39]

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
        Output('chart-parallel-sets', 'figure'),
        Input('crossfilter-year-slider', 'value'),
        Input('crossfilter-casualty-lower', 'value'),
        Input('crossfilter-casualty-upper', 'value'),
        Input('crossfilter-attacktype-dropdown', 'value'),
        Input('crossfilter-weapontype-dropdown', 'value'),
        Input('crossfilter-targettype-dropdown', 'value'),
        Input('crossfilter-group-dropdown', 'value'),
        running=[(Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_parallel_sets(year_range, casualty_lower, casualty_upper, attacktype, weapontype, targettype, group):
    #dff = filter_years(df_terror, year_range)
    dff = filter_data(df_terror, year_range, casualty_lower, casualty_upper, None, None, None, group)

    # set value for color based on filters
    dff['highlight'] = 1
    if (weapontype or attacktype or targettype):
        # define condition by boolean vector or True
        weapon_condition = dff['weaptype1_txt'].isin(weapontype) if weapontype else True
        attack_condition = dff['attacktype1_txt'].isin(attacktype) if attacktype else True
        target_condition = dff['targtype1_txt'].isin(targettype) if targettype else True
        condition = weapon_condition & attack_condition & target_condition

        # set opacity based on condition
        dff.loc[condition == True, 'highlight'] = 1
        dff.loc[condition == False, 'highlight'] = 0
    
    # define order of dimensions based on number of attacks consistent with beeswarm
    attack_order = dff.groupby(['attacktype1_txt'])['attacktype1_txt'].count().sort_values(ascending=False).index
    weapon_order = dff.groupby(['weaptype1_txt'])['weaptype1_txt'].count().sort_values(ascending=False).index
    target_order = dff.groupby(['targtype1_txt'])['targtype1_txt'].count().sort_values(ascending=False).index

    # set dimensions with labels
    dimensions=[
        dict(values=dff['attacktype1_txt'], label="Attacks", categoryarray=attack_order),
        dict(values=dff['weaptype1_txt'], label="Weapons", categoryarray=weapon_order),
        dict(values=dff['targtype1_txt'], label="Targets", categoryarray=target_order)
    ]

    # set color scale for highlights
    hightlight_scale = [[0, 'rgba(211, 211, 211, 0.3)'], # light grey not highlighted
                        [1, 'rgba(65, 105, 225, 1)']] # blue when filters

    # parallel categories
    fig = go.Figure(
        go.Parcats(
            dimensions=dimensions,
            line=dict(
                color=dff['highlight'], # color based on level of highlight
                colorscale=hightlight_scale,
                shape='hspline' # smooth curves rather than linear lines
            ),
            hoveron='category',  # show hover info for one category only
            hoverinfo=None, # enable hover
            labelfont=dict(color='rgba(0, 0, 0, 1)'),
            tickfont=dict(color='rgba(0, 0, 0, 1)'),
            sortpaths='forward'
        )
    )

    # Update layout for improved readability and consistency
    fig.update_layout(
        title='How are weapons, targets, and attacks related?',
        font=dict(size=12),
        plot_bgcolor='white'
    )
    
    return fig


@callback(
        Output('chart-beeswarm', 'figure'),
        Input('global-clickData', 'data'),
        Input('crossfilter-year-slider', 'value'),
        Input('crossfilter-attacktype-dropdown', 'value'),
        Input('crossfilter-weapontype-dropdown', 'value'),
        Input('crossfilter-targettype-dropdown', 'value'),
        Input('crossfilter-group-dropdown', 'value'),
        running=[(Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_beeswarm(clickData, year_range, attacktype, weapontype, targettype, group):
    dff = filter_data(df_terror, year_range, None, None, None, None, None, group)

    # Sort and map categories
    category_order = (
        dff.groupby('targtype1_txt')['total_casualties']
        .count()
        .sort_values(ascending=True)
        .index
        .tolist()
    )
    category_to_y = {cat: i for i, cat in enumerate(category_order)}

    # apply jitter
    dff['y_jittered'] = dff['targtype1_txt'].map(category_to_y) + dff['beeswarm_jitter']
    
    
    # Set default highlight and define filters
    dff['highlight'] = 1
    if weapontype or attacktype or targettype:
        weapon_condition = dff['weaptype1_txt'].isin(weapontype) if weapontype else True
        attack_condition = dff['attacktype1_txt'].isin(attacktype) if attacktype else True
        target_condition = dff['targtype1_txt'].isin(targettype) if targettype else True
        condition = weapon_condition & attack_condition & target_condition
        dff.loc[~condition, 'highlight'] = 0

    # Highlight based on clickData
    selected_point = None
    if clickData is not None:
        clicked_eventid = clickData[0]  # Adjust as needed
        dff.loc[dff['eventid'] == clicked_eventid, 'highlight'] = 2
        selected_point = dff[dff['highlight'] == 2]
        dff = dff[dff['highlight'] != 2]  # Exclude selected point(s) for separate trace

    # Set color mapping
    highlight_scale = {0: 'rgba(211, 211, 211, 0.3)', 1: 'rgba(65, 105, 225, 0.5)', 2: 'rgba(225, 0, 0, 0.5)'}

    # Create figure and add traces
    fig = go.Figure()

    # Non-selected points trace
    fig.add_trace(
        go.Scatter(
            x=dff['total_casualties'],
            y=dff['y_jittered'],
            mode='markers',
            marker=dict(color=dff['highlight'].map(highlight_scale), size=8),
            customdata=dff[customdata_list].to_numpy(),
            hovertemplate="<b>%{customdata[3]}-%{customdata[4]}-%{customdata[5]} %{customdata[9]}, %{customdata[6]}</b><br>"
                          "Group: %{customdata[25]}<br>"
                          "Attack type: %{customdata[15]}<br>"
                          "Weapon type: %{customdata[18]}<br>"
                          "Target type: %{customdata[20]}<br>"
        )
    )

    # Selected point(s) trace, if any
    if selected_point is not None:
        fig.add_trace(
            go.Scatter(
                x=selected_point['total_casualties'],
                y=selected_point['y_jittered'],
                mode='markers',
                marker=dict(color='rgba(225, 0, 0, 0.5)', size=8),
                customdata=selected_point[customdata_list].to_numpy(),
                hovertemplate="<b>%{customdata[3]}-%{customdata[4]}-%{customdata[5]} %{customdata[9]}, %{customdata[6]}</b><br>"
                              "Group: %{customdata[25]}<br>"
                              "Attack type: %{customdata[15]}<br>"
                              "Weapon type: %{customdata[18]}<br>"
                              "Target type: %{customdata[20]}<br>"
            )
        )

    # Update layout
    fig.update_layout(
        title='Which attacks have the highest number of casualties?',
        xaxis=dict(
            showgrid=True, 
            gridcolor='lightgray', 
            gridwidth=0.5),
        yaxis=dict(
            tickvals=list(category_to_y.values()),
            ticktext=list(category_to_y.keys()),
            title='Target Type',
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=0.5
        ),
        showlegend=False,
        plot_bgcolor='white',
        width=600,
        height=900
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