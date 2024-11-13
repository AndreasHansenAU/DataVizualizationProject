from utils.Jitter import *
from constants import default
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
                   'flag',
                   'total_casualties',]


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
    dcc.Store(id='global-clickData'),

    # Top blue box with title and filters in 3 columns
    html.Div([
        html.H3("Terrorism Data Visualization", style={'color': 'white', 'text-align': 'center'}),
        html.Div([
            # Column 1
            html.Div([
                dcc.RangeSlider(
                    id='crossfilter-year-slider',
                    min=df_terror['iyear'].min(),
                    max=df_terror['iyear'].max(),
                    step=None,
                    value=default.year_range.value,
                    marks={str(year): str(year) if year % 5 == 0 else '' for year in df_terror['iyear'].unique()},
                    allowCross=False
                ),

                html.Label("Specify Casualty Range:"),
                dcc.Input(
                    id='crossfilter-casualty-lower',
                    type='number',
                    placeholder='Lower bound',
                    min=0,
                    max=df_terror['total_casualties'].max(),
                    value=0,
                    style={'width': '45%', 'margin-right': '5px'}
                ),
                dcc.Input(
                    id='crossfilter-casualty-upper',
                    type='number',
                    placeholder='Upper bound',
                    min=0,
                    value=df_terror['total_casualties'].max(),
                    style={'width': '45%'}
                )
            ], style={'padding': '10px', 'width': '33%', 'display': 'inline-block'}),

            # Column 2
            html.Div([
                html.Div(
                    id='crossfilter-summary-container',
                    children=update_summary_dropdown(None, default.year_range.value, 0, df_terror['total_casualties'].max(), None, None, None, None),
                    style={'padding': '10px'}
                ),

                dcc.RadioItems(
                    id='toggle-metric',
                    options=[
                        {'label': 'Show Number of Attacks', 'value': 'attacks'},
                        {'label': 'Show Total Casualties', 'value': 'casualties'}
                    ],
                    value='attacks'
                )
            ], style={'padding': '10px', 'width': '33%', 'display': 'inline-block'}),

            # Column 3
            html.Div([
                dcc.Dropdown(
                    id='crossfilter-attacktype-dropdown',
                    options=[{'label': i, 'value': i} for i in df_terror['attacktype1_txt'].unique()],
                    value=None,
                    placeholder='Show All Attack Types',
                    multi=True,
                    clearable=False
                ),
                dcc.Dropdown(
                    id='crossfilter-weapontype-dropdown',
                    options=[{'label': i, 'value': i} for i in df_terror['weaptype1_txt'].unique()],
                    value=None,
                    placeholder='Show All Weapon Types',
                    multi=True,
                    clearable=False
                ),
                dcc.Dropdown(
                    id='crossfilter-targettype-dropdown',
                    options=[{'label': i, 'value': i} for i in df_terror['targtype1_txt'].unique()],
                    value=None,
                    placeholder='Show All Target Types',
                    multi=True,
                    clearable=False
                ),
                html.Div(
                    id='crossfilter-group-container',
                    children=update_group_dropdown(None, default.year_range.value, 0, df_terror['total_casualties'].max()),
                    style={'padding': '10px'}
                )
            ], style={'padding': '10px', 'width': '33%', 'display': 'inline-block'})
        ], style={'display': 'flex', 'flex-direction': 'row'})
    ], style={'background-color': default.highlight_color.value, 'padding': '20px', 'color': 'white'}),

    # Main charts
    html.Div([
        # Column 1
        html.Div([
            # heatmap
            html.Div([
                dcc.Store(id='map-state', data={'zoom': default.zoom.value, 'center': dict(lat=default.lat.value, lon=default.lon.value)}),
                dcc.Graph(id='map-heatmap', hoverData=None, clickData=None)
            ], style={'padding': '0px', 'display': 'inline-block', 'vertical-align': 'top'}),

            # parallel sets
            html.Div([
                dcc.Graph(id='chart-parallel-sets')
            ], style={'padding': '0px', 'display': 'inline-block', 'vertical-align': 'top', 'margin-top': '-50px', 'margin-left': '0px'}),
        ], style={'display': 'flex', 'flex-direction': 'column', 'margin-bottom': '0px', 'width':'50%', 'min-width':'50%'}),
        # end of column 1

        # Column 2
        html.Div([
            # info box
            html.Div([
                html.H4("Selected Attack Information", id="info-title"),
                html.Div(id='info-box', style={
                    'padding': '10px',
                    'border': '1px solid black',
                    'width': '90%',
                    'height': '200px',
                    'overflow-y': 'scroll'
                })
            ], style={'padding': '0px', 'display': 'inline-block', 'vertical-align': 'top'}),

            # beeswarm
            html.Div([
                dcc.Graph(id='chart-beeswarm', clickData=None, hoverData=None)
            ], style={'padding': '0px', 'display': 'inline-block', 'vertical-align': 'top', 'margin-top': '0px'})
        ], style={'display': 'flex', 'flex-direction': 'column', 
                  'margin-top': '0px', 'width':'50%', 'min-width':'50%', 
                  'background_color': default.plot_bgcolor.value})
        # end of column 2

    ], style={'display': 'flex', 'align-items': 'flex-start', 'margin-top': '5px'})
])


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
        trigger = 'map-heatmap.clickData'
        global_clickData = map_clickData['points'][0]['customdata']
    elif 'chart-beeswarm.clickData' in trigger:
        trigger = 'chart-beeswarm.clickData'
        global_clickData = beeswarm_clickData['points'][0]['customdata']
    
    return dict(data=global_clickData, trigger=trigger)


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
        max_density = 50
        colorbar_title = "Casualties"
    else:
        z_value = None
        max_density = 50
        colorbar_title = "Attacks"

    # Viridis
    color_scale = [
        [0.0, "rgba(0, 0, 0, 0)"],
        [0.01, "#440154"],  # Dark purple
        [0.25, "#3b528b"],  # Medium blue
        [0.5, "#21918c"],  # Green
        [0.75, "#5ec962"],  # Yellow-green
        [1.0, "#fde725"]   # Yellow
    ]

    # ensure that map is drawn in same state prior to update
    zoom = map_state['zoom']
    center = map_state['center']

    trigger = list(ctx.triggered_prop_ids.keys())
    if 'global-clickData.data' in trigger and clickData['data'] is not None:
        if clickData['trigger'] != 'map-heatmap.clickData':
            clicked_lat = clickData['data'][1]
            clicked_lon = clickData['data'][2]
            center = {'lat':clicked_lat, 'lon':clicked_lon}
    

    fig = go.Figure()
    fig.add_trace(
        go.Densitymap(
            lat=dff['latitude_jitter'],
            lon=dff['longitude_jitter'],
            z=dff[z_value] if z_value else None,
            radius=10,
            opacity=1,
            zmin=0,
            zmax=max_density,
            colorscale=color_scale,
                        colorbar=dict(
                title=colorbar_title,
                tickvals=[0, 10, 20, 30, 40, 50],   # Define tick values
                ticktext=["0", "10", "20", "30", "40", "50+"],  # Custom tick labels
            ),
            showscale=True,
            name="",
        )
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
        title=dict(
            text="Where do attacks occur?",
            yref="container",
            yanchor="top",
            y=0.85,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        coloraxis_colorbar=dict(
            title=dict(
                text=colorbar_title,
                font=default.label_dict.value),
            titleside="right",
        ),
        map=dict(
            style="open-street-map",  # "carto-positron" or "satellite-streets"
            center=center,
            zoom=zoom
        ),
        width=700,
        height=500
    )


    # draw lines to related attacks and draw clicked point
    if clickData['data']:
        # get current point
        clicked_lat = clickData['data'][1]
        clicked_lon = clickData['data'][2]
        related = clickData['data'][14]
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
                        showlegend=False, # don't show in legend
                    ),
                )
        # plot clicked point if it's still in the filtered data
        clicked_eventid = clickData['data'][0]
        is_eventid_present = dff['eventid'].isin([clicked_eventid]).any()
        if is_eventid_present:
            fig.add_trace(
                go.Scattermap(
                    mode='markers',
                    lon=[clicked_lon],
                    lat=[clicked_lat],
                    marker=dict(size=10, color=default.selection_color.value),
                    opacity=0.8,
                    hoverinfo='skip', # no hover info
                    showlegend=False, # don't show in legend
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
    current_zoom = relayoutData.get('map.zoom')
    current_center = relayoutData.get('map.center')

    trigger = list(ctx.triggered_prop_ids.keys())

    # if triggered by click then update state to clicked points location
    if 'global-clickData.data' in trigger and clickData['data'] is not None:
        clicked_lat = clickData['data'][1]
        clicked_lon = clickData['data'][2]
        return {'zoom': current_zoom,
                'center': {'lat':clicked_lat, 'lon':clicked_lon}}

    # if triggered by relayout then update state
    if 'map-heatmap.relayoutData' in trigger:
        return {'zoom': current_zoom, 
                'center': current_center}
    
    return no_update


@callback(
    Output('info-box', 'children'),
    Input('global-clickData', 'data'))
def update_info_box(clickData):
    if clickData['data'] is None:
        return "Click on an attack to see details."

    # Overall details
    eventid = clickData['data'][0]
    latitude_jitter = clickData['data'][1]
    longitude_jitter = clickData['data'][2]
    day = clickData['data'][3]
    month = clickData['data'][4]
    year = clickData['data'][5]
    country = clickData['data'][6]
    region = clickData['data'][7]
    provstate = clickData['data'][8]
    city = clickData['data'][9]
    summary = clickData['data'][10]
    crit1 = clickData['data'][11]
    crit2 = clickData['data'][12]
    crit3 = clickData['data'][13]
    related = clickData['data'][14]
    
    # Attack types
    attacktype1 = clickData['data'][15]
    #attacktype2 = point_data['data'][13]
    #attacktype3 = point_data['data'][14]
    
    # Success and suicide
    success = clickData['data'][16]
    suicide = clickData['data'][17]
    
    # Weapon types and subtypes
    weaptype1 = clickData['data'][18]
    weapsubtype1 = clickData['data'][19]
    #weaptype2 = point_data['data'][19]
    #weapsubtype2 = point_data['data'][20]
    #weaptype3 = point_data['data'][21]
    #weapsubtype3 = point_data['data'][22]
    
    # Target types and subtypes
    targtype1 = clickData['data'][20]
    targsubtype1 = clickData['data'][21]
    #targtype2 = point_data['data'][25]
    #targsubtype2 = point_data['data'][26]
    #targtype3 = point_data['data'][27]
    #targsubtype3 = point_data['data'][28]
    
    # Corporate 
    corp1 = clickData['data'][22]
    #corp2 = point_data['data'][30]
    #corp3 = point_data['data'][31]
    
    # Target
    target1 = clickData['data'][23]
    #target2 = point_data['data'][33]
    #target3 = point_data['data'][34]
    
    # Target nationaly
    natlty1 = clickData['data'][24]
    #natlty2 = point_data['data'][36]
    #natlty3 = point_data['data'][37]
    
    # Groups
    group = clickData['data'][25]
    guncertain = clickData['data'][26]
    nperps = clickData['data'][27]
    motive = clickData['data'][28]
    
    # Casualties and injuries
    nkill = clickData['data'][29]
    nkillter = clickData['data'][30]
    nwound = clickData['data'][31]
    nwoundte = clickData['data'][32]
    
    # Property damage
    property = clickData['data'][33]
    propvalue = clickData['data'][34]
    
    # Hostage information
    ishostkid = clickData['data'][35]
    nhostkid = clickData['data'][36]
    nhours = clickData['data'][37]
    ndays = clickData['data'][38]
    
    # Flag
    flag = clickData['data'][39]

    # our column
    total_casualties = clickData['data'][40]


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
    hightlight_scale = [[0, default.background_color.value], # light grey not highlighted
                        [1, default.highlight_color.value]] # blue when filters

    # parallel categories
    fig = go.Figure(
        go.Parcats(
            dimensions=dimensions,
            line=dict(
                color=dff['highlight'], # color based on level of highlight
                colorscale=hightlight_scale,
                shape='hspline', # smooth curves rather than linear lines
            ),
            hoveron='category',  # show hover info for one category only
            hoverinfo=None, # enable hover
            labelfont=default.label_dict.value,
            tickfont=dict(color=default.font_color.value, family=default.font_type.value, size=10, weight=10),
            sortpaths='forward',
        )
    )

    # Update layout for improved readability and consistency
    fig.update_layout(
        title=dict(
            text="How are attacks, weapons and targets related?",
            yref="container",
            yanchor="top",
            y=0.9,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        font=default.label_dict.value,
        margin=dict(l=150, r=100), # ensure labels can be read
        plot_bgcolor=default.plot_bgcolor.value,
        width=700,
        height=500
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
    if clickData['data'] is not None:
        clicked_eventid = clickData['data'][0]  # Adjust as needed
        dff.loc[dff['eventid'] == clicked_eventid, 'highlight'] = 2
        selected_point = dff[dff['highlight'] == 2]
        dff = dff[dff['highlight'] != 2]  # Exclude selected point(s) for separate trace

    # Set color mapping
    highlight_scale = {0: default.background_color.value, 
                       1: default.highlight_color.value, 
                       2: default.selection_color.value}

    # Create figure and add traces
    fig = go.Figure()

    # Non-selected points trace
    fig.add_trace(
        go.Scatter(
            x=dff['total_casualties'],
            y=dff['y_jittered'],
            mode='markers',
            marker=dict(color=dff['highlight'].map(highlight_scale), size=8),
            name="",
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
                marker=dict(color=default.selection_color.value, size=8),
                name="",
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
        title=dict(
            text="Which attacks have the highest number of casualties?",
            yref="container",
            yanchor="top",
            y=0.9,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        xaxis=dict(
            title=dict(
                text='Number of casualties',
                font=default.label_dict.value
            ),
            showgrid=True, 
            gridcolor='lightgray', 
            gridwidth=0.5),
        yaxis=dict(
            tickvals=list(category_to_y.values()),
            ticktext=list(category_to_y.keys()),
            title=dict(
                text='Target Type',
                font=default.label_dict.value
            ),
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=0.5
        ),
        font=default.label_dict.value,
        showlegend=False,
        plot_bgcolor=default.plot_bgcolor.value,
        width=700,
        height=700
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