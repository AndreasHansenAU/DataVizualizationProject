from utils.Jitter import *
from utils.Utils import *
from constants import default
from dash import Dash, html, dcc, ctx, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from flask_caching import Cache
import pandas as pd
import webbrowser
from threading import Timer
import os
import plotly.graph_objects as go

###############################################################################
# setup app
port=8050
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)


###############################################################################
# setup cache
cache = Cache(app.server, config={
    'DEBUG':True,
    'CACHE_TYPE':'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT':300
})


###############################################################################
# setup data
@cache.memoize()
def read_data_terror():
    df = pd.read_csv("src/data/globalterrorism_2020_cleaned.csv")

    # jitter geospatial coordinates
    df = add_jitter_coordinates(df, "latitude", "longitude", "latitude_jitter", "longitude_jitter")

    # jitter beeswarm
    df = add_jitter_beeswarm(df, jitter_amount=0.2)

    # simplify vehicle name
    df.loc[df['weaptype1_txt'].str.contains('Vehicle'), 'weaptype1_txt'] = 'Vehicle'

    # ensure 0 or None casualties can be plotted in heatmap
    df['total_casualties_visualized'] = df['total_casualties'].replace(0, 1)

    return df


df_terror = read_data_terror()

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
                   'total_casualties', 
                   'scite1',
                   'propextent_txt',
                   'claimmode_txt']


###############################################################################
# filter data
@cache.memoize()
def filter_years(df, year_range):
    year_lower, year_upper = year_range
    df_filtered = df[(df['iyear'] >= year_lower) & (df['iyear'] <= year_upper)]
    return df_filtered

@cache.memoize()
def filter_data(df, year_range, attacktype, weapontype, targettype, group):
    # filter years
    df_filtered = filter_years(df, year_range)

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


###############################################################################
# setup filters
@callback(
    Output('crossfilter-group-container', 'children'),
    State('crossfilter-group-dropdown', 'value'),
    Input('crossfilter-year-slider', 'value'),
)
def update_group_dropdown(group_selections, year_range):
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
        value=group_selections,
        placeholder='Show All Terror Groups',
        multi=True,
        clearable=False,
        maxHeight=200,
        optionHeight=35
    )


###############################################################################
# setup layout
app.layout = html.Div([
    dcc.Store(id='global-clickData'),

    # Top blue box with title and filters in 3 columns
    html.Div([
        html.H3("Exploration of The Global Terrorism Database", style={'color': 'white', 'text-align': 'center'}),
        
        html.Div([
            # Column 1 and 2
            html.Div([
                # Range Slider spans columns 1 and 2
                html.Div([
                    dcc.RangeSlider(
                        id='crossfilter-year-slider',
                        min=df_terror['iyear'].min(),
                        max=df_terror['iyear'].max(),
                        step=None,
                        value=default.year_range.value,
                        marks={str(year): str(year) if year % 10 == 0 else '' for year in df_terror['iyear'].unique()},
                        allowCross=False,
                        dots=False,
                        updatemode='mouseup',
                        tooltip=dict(placement="top", always_visible=True),
                    ),
                ], style={'padding': '0px', 'width': '100%', 'display': 'inline-block', 'vertical-align': 'top'}),

                # Column 1
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
                        clearable=False,
                        style={'margin-top': '10px'}
                    ),
                ], style={'padding': '10px', 'width': '48.2%', 'display': 'inline-block', 'vertical-align': 'top'}),

                # Column 2
                html.Div([
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
                        children=update_group_dropdown(None, default.year_range.value),
                        style={'margin-top': '10px', 'padding': '0px'}
                    )
                ], style={'padding': '10px', 'width': '48.2%', 'display': 'inline-block', 'vertical-align': 'top'}),
            ], style={'width': '66%', 'display': 'inline-block', 'vertical-align': 'top'}),

            # Column 3
            html.Div([
                html.Button('Reset Selection',
                            id='button-reset-selection',
                            n_clicks=0,
                            style={'margin-top': '0px', 'background-color': 'white'}
                            ),
                html.Div(
                    id="info-box",
                    style={'margin-top': '10px', 'clear': 'both'}
                )
            ], style={'padding': '10px', 'width': '33%', 'display': 'inline-block'}),
        ], style={'display': 'flex', 'flex-direction': 'row'})
    ], style={'background-color': default.highlight_color.value, 'padding': '0px', 'color': 'white'}),

    # Main charts
    html.Div([
        # Heatmap
        html.Div([
            dcc.Store(id='map-state', data={'zoom': default.zoom.value, 'center': dict(lat=default.lat.value, lon=default.lon.value)}),
            dcc.RadioItems(
                id='toggle-metric',
                options=[
                    {'label': 'Show Number of Attacks', 'value': 'attacks'},
                    {'label': 'Show Total Casualties', 'value': 'casualties'}
                ],
                value='attacks',
                inline=True,
                style={'margin-top': '10px'},
                labelStyle={'margin-right': '20px'}
            ),
            dcc.Graph(id='map-heatmap', hoverData=None, clickData=None)
        ], style={'grid-area': 'heatmap'}),

        # Parallel sets
        html.Div([
            dcc.Graph(id='chart-parallel-sets', clickData=None)
        ], style={'grid-area': 'parallel-sets'}),

        # Beeswarm
        html.Div([
            dcc.Graph(id='chart-beeswarm', clickData=None, hoverData=None)
        ], style={'grid-area': 'beeswarm', 'margin-top': '-40px'}),

        # Scatterplot
        html.Div([
            dcc.Graph(id='chart-scatter', clickData=None, hoverData=None)
        ], style={'grid-area': 'scatterplot', 'margin-top': '0px'}),

    ], style={
        'display': 'grid',
        'grid-template-areas': '''
            "heatmap parallel-sets"
            "beeswarm scatterplot"
        ''',
        'grid-template-columns': '1fr 1fr',
        'grid-template-rows': 'auto auto',
        'gap': '0px',
        'align-items': 'center',
        'justify-items': 'center',
        'width': '100%',
        'padding': '0px'
    })
])


###############################################################################
# update global clickdata
@callback(
    Output('global-clickData', 'data'),
    Input('map-heatmap', 'clickData'),
    Input('chart-beeswarm', 'clickData'),
    Input('button-reset-selection', 'n_clicks')
)
def update_global_clickdata(map_clickData, beeswarm_clickData, n_clicks):
    global_clickData = None

    # update global click data based on which event triggered a callback
    trigger = list(ctx.triggered_prop_ids.keys())
    if 'map-heatmap.clickData' in trigger:
        trigger = 'map-heatmap.clickData'
        global_clickData = map_clickData['points'][0]['customdata']
    elif 'chart-beeswarm.clickData' in trigger:
        trigger = 'chart-beeswarm.clickData'
        global_clickData = beeswarm_clickData['points'][0]['customdata']
    elif 'button-reset-clickdata.n_clicks' in trigger:
        trigger = 'button-reset-clickdata.n_clicks'
        global_clickData = None
    
    return dict(data=global_clickData, trigger=trigger)


###############################################################################
# update heatmap
@callback(
    Output('map-heatmap', 'figure'),
    State('map-state', 'data'),
    Input('global-clickData', 'data'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-weapontype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'),
    Input('toggle-metric', 'value'),
    running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)],
    prevent_initial_call=True)
def update_map_heatmap(map_state, clickData, year_range, attacktype, weapontype, targettype, group, metric):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, weapontype, targettype, group)
    
    if metric == 'casualties':
        z_value = 'total_casualties_visualized'
        max_density = 50
        colorbar_title = "Casualties"
        title = 'Where do casualties occur?'
    else:
        z_value = None
        max_density = 50
        colorbar_title = "Attacks"
        title = 'Where do attacks occur?'

    # reversed truncated ice scale
    color_scale = [
        [0.0, "rgb(120, 195, 225)"],
        [0.01, "rgb(120, 195, 225)"],
        [0.25, "rgb(90, 160, 195)"],
        [0.5, "rgb(60, 125, 165)"],
        [0.75, "rgb(30, 90, 135)"],
        [1.00, "rgb(10, 50, 100)"]
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
            radius=default.marker_size.value,
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

    fig.update_traces(customdata=dff[customdata_list],
                      # update hover box
                      hovertemplate="<b>%{customdata[3]}-%{customdata[4]}-%{customdata[5]} %{customdata[9]}, %{customdata[6]}</b><br>"
                                    "Group: %{customdata[25]}<br>"
                                    "Attack type: %{customdata[15]}<br>"
                                    "Weapon type: %{customdata[18]}<br>"
                                    "Target type: %{customdata[20]}<br>",
                      hoverlabel=dict(
                          bgcolor=default.highlight_color.value,
                          bordercolor=default.hover_bordercolor.value,
                          font=default.hover_font_dict.value
                      )
    )
    
    fig.update_layout(
        title=dict(
            text=title,
            yref="container",
            yanchor="top",
            y=0.96,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        margin=dict(l=0, r=0, t=40, b=45),
        coloraxis_colorbar=dict(
            title=dict(
                text=colorbar_title,
                font=default.label_dict.value),
            titleside="right",
        ),
        map=dict(
            style="light", # open-street-map
            center=center,
            zoom=zoom,
        ),
        width=900,
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
            related_split = get_related_ids(related)
            # get information from related attacks
            related_gps = dff[dff['eventid'].isin(related_split)][['eventid', 'latitude_jitter', 'longitude_jitter']]
            for idx, (_, row) in  enumerate(related_gps.iterrows()):
                # highlight related attacks and draw lines to them
                fig.add_trace(
                    go.Scattermap(
                        mode='lines+markers',
                        lon=[clicked_lon, row['longitude_jitter']],
                        lat=[clicked_lat, row['latitude_jitter']],
                        line=dict(width=3, 
                                  color=default.related_color.value),
                        marker=dict(size=default.related_size.value, 
                                    color=default.related_color.value),
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
                    marker=dict(size=default.selection_size.value, 
                                color=default.selection_color.value),
                    hoverinfo='skip', # no hover info
                    showlegend=False, # don't show in legend
                ),
            )
    
    return fig


# update heatmap state
@callback(
    Output('map-state', 'data'),
    Input('map-heatmap', 'relayoutData'),
    Input('global-clickData', 'data'),
    prevent_initial_call=True
)
def update_map_state(relayoutData, clickData):
    if relayoutData is not None:
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


###############################################################################
# update infobox
@callback(
    Output('info-box', 'children'),
    Input('global-clickData', 'data'))
def update_info_box(clickData):
    if clickData['data'] is None:
        return html.Div(
            id='info-box', 
            style={
                'width': '100%',
                'height': '100px',
                'overflow-y': 'scroll',
                'background-color': 'white',
                'border-radius': '5px',
                'color': 'black'
            },
            children="Click on an attack to see details."
        )

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
    nkill = 'Unknown' if clickData['data'][29] is None else clickData['data'][29]
    nkillter = clickData['data'][30]
    nwound = 'Unknown' if clickData['data'][31] is None else clickData['data'][31]
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

    # source
    scite1 = clickData['data'][41]

    # extent of damage (class)
    propextent = clickData['data'][42]

    claimmode = clickData['data'][43]

    selection_style = {"width": f"{default.selection_size.value}px", 
                       "height": f"{default.selection_size.value}px",
                       "backgroundColor": default.selection_color.value,
                       "borderRadius": "50%",
                       "display": "inline-block",
                       "marginRight": f"{default.selection_size.value}px"}
    
    related_style = {"width": f"{default.related_size.value}px", 
                       "height": f"{default.related_size.value}px",
                       "backgroundColor": default.related_color.value,
                       "borderRadius": "50%",
                       "display": "inline-block",
                       "marginRight": f"{default.related_size.value}px"}

    criterion_colormap = {0:default.background_color.value, 1:default.selection_color.value}
    criterion_info = {1:dict(value=crit1, symbol='➊', details=html.Div(['Indication that act is aimed at attaining a', html.Br(), 'political, economic, religious or social goal'])),
                      2:dict(value=crit2, symbol='➋', details=html.Div(['Evidence of intention to coerce, intimidate', html.Br(), 'or convey message to larger audience(s)', html.Br(), 'other than the immediate victim(s).'])),
                      3:dict(value=crit3, symbol='➌', details=html.Div(['Act is outside international humanitarian', html.Br(), 'law of legitimate warfare according', html.Br(), 'to the Geneva Convention 1949.']))}
    box_content = []

    # quick attack info
    header = [html.Span(style=selection_style),
              html.Span(f"{day}-{month}-{year} {city}, {country} {flag}")]
    
    for i in [1, 2, 3]:
        crit_value = criterion_info[i]['value']
        crit_symbol = criterion_info[i]['symbol']
        crit_details = criterion_info[i]['details']
        crit_color = criterion_colormap[crit_value]
        spacing = 100 if i==1 else 30
        header.append(html.Span(crit_symbol, id=f'crit{i}-symbol', style={'color':crit_color, 'font-size':'20px', 'cursor':'default', 'margin-left':f'{spacing}px'}))
        header.append(dbc.Tooltip(crit_details, target=f'crit{i}-symbol', placement='bottom', style={'color':default.font_color.value, 'font-size':default.hover_font_size.value, 'font-family':default.font_type.value}))


    box_content.append(html.Div(header))
    
    if related is not None:
        n_related = len(get_related_ids(related)) - 1
        box_content.append(html.Div([html.Span(style=related_style), html.Span(f"{n_related} related attacks")]))
    box_content.append(html.Div([html.Span(f"Lethal injuries: {nkill}")]))
    box_content.append(html.Div([html.Span(f"Non-lethal injuries: {nwound}")]))
    if propextent is not None:
        box_content.append(html.Div([html.Span(f"Property damage: {propextent}")]))

    # group info
    box_content.append(html.Div([html.Br(), html.Strong("Details of group:")]))
    box_content.append(html.Div([html.Span(f"Group: {group}")]))
    if motive is not None:
        box_content.append(html.Div([html.Span(f"Group motive: {motive}")]))
    if claimmode is not None:
        if claimmode != 'Unknown':
            box_content.append(html.Div([html.Span(f"Method of claim: {claimmode}")]))
    
    # attack details
    box_content.append(html.Div([html.Br(), html.Strong("Details of attack:")]))
    box_content.append(html.Div([html.Span(f"Type of attack: {attacktype1}")]))
    box_content.append(html.Div([html.Span(f"Type of weapon: {weaptype1}")]))
    box_content.append(html.Div([html.Span(f"Type of target: {targtype1}")]))
    if target1 is not None:
        box_content.append(html.Div([html.Span(f"Specific target: {target1}")]))
    
    # summary and source
    if summary is not None:
        box_content.append(html.Div([html.Br(), html.Strong('Summary of attack:'), html.Br(), html.Span(summary)]))
    box_content.append(html.Div([html.Br(), html.Strong("Source: "), html.Span(scite1)]))

    # return info box
    info_box = html.Div(
        id='info-box', 
        style={
            'width': '100%',
            'height': '200px',
            'overflow-y': 'scroll',
            'background-color': 'white',
            'border-radius': '5px',
            'color': 'black'
        },
        children=box_content,
    )
    return info_box


###############################################################################
# update parallel sets
@callback(
        Output('chart-parallel-sets', 'figure'),
        Input('crossfilter-year-slider', 'value'),
        Input('crossfilter-attacktype-dropdown', 'value'),
        Input('crossfilter-weapontype-dropdown', 'value'),
        Input('crossfilter-targettype-dropdown', 'value'),
        Input('crossfilter-group-dropdown', 'value'),
        running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_parallel_sets(year_range, attacktype, weapontype, targettype, group):
    #dff = filter_years(df_terror, year_range)
    dff = filter_data(df_terror, year_range, None, None, None, group)

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
            labelfont=default.label_dict.value,
            tickfont=dict(color=default.font_color.value, family=default.font_type.value, size=10, weight=10),
            sortpaths='forward',
            hoveron='category',
            hoverinfo='count'
        )
    )

    # Update layout for improved readability and consistency
    fig.update_layout(
        title=dict(
            text="How are attacks, weapons and targets related?",
            yref="container",
            yanchor="top",
            y=0.95,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        font=default.label_dict.value,
        margin=dict(l=150, r=100, t=70, b=10), # ensure labels can be read
        plot_bgcolor=default.plot_bgcolor.value,
        width=900,
        height=500
    )
     
    return fig


# update filters interactively in parallel sets
@callback(
    Output('crossfilter-attacktype-dropdown', 'value'),
    Output('crossfilter-weapontype-dropdown', 'value'),
    Output('crossfilter-targettype-dropdown', 'value'),
    State('crossfilter-attacktype-dropdown', 'value'),
    State('crossfilter-weapontype-dropdown', 'value'),
    State('crossfilter-targettype-dropdown', 'value'),
    State('crossfilter-year-slider', 'value'),
    State('crossfilter-group-dropdown', 'value'),
    Input('chart-parallel-sets', 'clickData'),
    running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_parallel_categories_filters(attacktype, weapontype, targettype, year_range, group, clickData):
    def update_filter(filter_current, filter_new_list):
        # if the attribute value is the same for all clicked points
        if len(filter_new_list) == 1:
            # get the clicked value
            value_clicked = filter_new_list[0]

            # if no filter is applied, then apply clicked value
            if filter_current is None:
                filter_current = [value_clicked]

            # if filter is applied but not with clicked value, then apply clicked value
            elif value_clicked not in filter_current:
                filter_current.append(value_clicked)

            # if filter is applied with clicked value, then remove clicked value
            elif value_clicked in filter_current:
                filter_current.remove(value_clicked)
        
        return filter_current

    # filter data
    dff = filter_data(df_terror, year_range, None, None, None, group)

    attacktype_current = attacktype
    weapontype_current = weapontype
    targettype_current = targettype

    if clickData:
        # get rows that belong to clicked shape
        points_list = clickData['points']
        indexes = [point['pointNumber'] for point in points_list]
        dff_subset = dff.iloc[indexes]

        # get all unique values
        attacktypes_clicked = dff_subset['attacktype1_txt'].unique()
        weapontypes_clicked = dff_subset['weaptype1_txt'].unique()
        targettypes_clicked = dff_subset['targtype1_txt'].unique()

        # update filters
        attacktype_current = update_filter(attacktype_current, attacktypes_clicked)
        weapontype_current = update_filter(weapontype_current, weapontypes_clicked)
        targettype_current = update_filter(targettype_current, targettypes_clicked)
    
    return (attacktype_current, weapontype_current, targettype_current)


###############################################################################
# update beeswarm
@callback(
        Output('chart-beeswarm', 'figure'),
        Input('global-clickData', 'data'),
        Input('crossfilter-year-slider', 'value'),
        Input('crossfilter-attacktype-dropdown', 'value'),
        Input('crossfilter-weapontype-dropdown', 'value'),
        Input('crossfilter-targettype-dropdown', 'value'),
        Input('crossfilter-group-dropdown', 'value'),
        running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_beeswarm(clickData, year_range, attacktype, weapontype, targettype, group):
    dff = filter_data(df_terror, year_range, None, None, None, group)

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

    # Highlight based on related and clickData 
    if clickData['data'] is not None:
        # get related
        related = clickData['data'][14]
        if related:
            # format ids of related attacks
            related_split = get_related_ids(related)
            dff.loc[dff['eventid'].isin(related_split), 'highlight'] = 2
        
        # get click
        clicked_eventid = clickData['data'][0]
        dff.loc[dff['eventid'] == clicked_eventid, 'highlight'] = 3


    # Set color mapping
    highlight_scale = {0: [default.background_color.value, default.marker_size.value], 
                       1: [default.highlight_color.value, default.marker_size.value], 
                       2: [default.related_color.value, default.related_size.value],
                       3: [default.selection_color.value, default.selection_size.value]}

    # Create figure and add traces
    fig = go.Figure()

    # scatterplot of background, highlight, related and selection
    for i in [0, 1, 2, 3]:
        dff_condition = dff[dff['highlight'] == i]
        scaling_factor = -0.1*dff['total_casualties'].max()
        dff_condition['total_casualties'] = dff_condition['total_casualties'].fillna(scaling_factor)
        fig.add_trace(
            go.Scatter(
                x=dff_condition['total_casualties'],
                y=dff_condition['y_jittered'],
                mode='markers',
                marker=dict(size=highlight_scale[i][1], 
                            color=highlight_scale[i][0]),
                name="",
                customdata=dff_condition[customdata_list].to_numpy(),
                hovertemplate="<b>%{customdata[3]}-%{customdata[4]}-%{customdata[5]} %{customdata[9]}, %{customdata[6]}</b><br>"
                              "Group: %{customdata[25]}<br>"
                              "Attack type: %{customdata[15]}<br>"
                              "Weapon type: %{customdata[18]}<br>"
                              "Target type: %{customdata[20]}<br>",
                hoverlabel=dict(
                    bgcolor=highlight_scale[i][0],
                    bordercolor=default.hover_bordercolor.value,
                    font=default.hover_font_dict.value
                )
            )
        )
    

    # Calculate the range for ticks
    x_min = -0.1*dff['total_casualties'].max()  # Include negative placeholder
    x_max = dff['total_casualties'].max()
    tickvals = dynamic_ticks(0, x_max)  # Exclude the negative placeholder for the range
    tickvals = np.insert(tickvals, 0, x_min)  # Add the negative placeholder
    ticktext = ["Unknown" if val < 0 else f"{int(val)}" for val in tickvals]
    
    # Update layout
    fig.update_layout(
        uirevision=default.redrawid.value,
        title=dict(
            text="Which attacks have the highest number of casualties?",
            yref="container",
            yanchor="top",
            y=0.95,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(
            tickvals=tickvals,
            ticktext=ticktext,
            zeroline=True,
            zerolinecolor=default.gridline_color.value,
            zerolinewidth=default.gridline_width.value,
            title=dict(
                text='Number of casualties',
                font=default.label_dict.value
            ),
            showgrid=True, 
            gridcolor=default.gridline_color.value, 
            gridwidth=default.gridline_width.value),
        yaxis=dict(
            zeroline=True,
            zerolinecolor=default.gridline_color.value,
            zerolinewidth=default.gridline_width.value,
            tickvals=list(category_to_y.values()),
            ticktext=list(category_to_y.keys()),
            title=dict(
                text='Target Type',
                font=default.label_dict.value
            ),
            showgrid=True,
            gridcolor=default.gridline_color.value,
            gridwidth=default.gridline_width.value
        ),
        font=default.label_dict.value,
        showlegend=False,
        plot_bgcolor=default.plot_bgcolor.value,
        width=900,
        height=700,
        shapes=[
            dict(
                type="line",
                x0=scaling_factor/2,
                x1=scaling_factor/2,
                y0=-0.05*dff['y_jittered'].max(),
                y1=1.05*dff['y_jittered'].max(),
                line=dict(color="black", width=2)
            )
        ]
    )

    return fig


# Define a utility to compute "nice" intervals and number of ticks
def dynamic_ticks(data_min, data_max, axis_length=900, target_tick_spacing=100):
    # Estimate the number of ticks based on axis length
    ideal_tick_count = max(5, min(8, axis_length // target_tick_spacing))  # Between 5 and 8 ticks

    # Compute a "nice" interval
    range_span = data_max - data_min
    raw_interval = range_span / (ideal_tick_count - 1)
    magnitude = 10 ** np.floor(np.log10(raw_interval))
    nice_interval = np.ceil(raw_interval / magnitude) * magnitude

    # Generate ticks
    tick_min = np.floor(data_min / nice_interval) * nice_interval
    tick_max = np.ceil(data_max / nice_interval) * nice_interval
    ticks = np.arange(tick_min, tick_max + nice_interval, nice_interval)

    return ticks


###############################################################################
# update scatter
@callback(
    Output('chart-scatter', 'figure'),
    Input('crossfilter-year-slider', 'value'),
    Input('crossfilter-attacktype-dropdown', 'value'),
    Input('crossfilter-weapontype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'),
    running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)],
    prevent_initial_call=True)
def update_chart_scatter(year_range, attacktype, weapontype, targettype, group):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, weapontype, targettype, None)

    # get number of attacks and sum of casualties per group
    dff_grouped = (dff.groupby(['gname'])['total_casualties']
                      .agg(['count', 'sum'])
                      .reset_index(drop=False)
                      .rename(columns={'count':'n_attacks', 'sum':'n_casualties'}))

    # Set default highlight and define filters
    dff_grouped['highlight'] = 1

    # Highlight based on related and clickData 
    if group is not None and len(group) > 0:
        dff_grouped.loc[dff_grouped['gname'].isin(group)==False, 'highlight'] = 0


    # Set color mapping
    highlight_scale = {0: [default.background_color_group.value, default.marker_size.value], 
                       1: [default.highlight_color_group.value, default.marker_size.value]}
    
    fig = go.Figure()

    for i in [0, 1]:
        condition = dff_grouped['highlight'] == i
        fig.add_trace(
            go.Scatter(
                x=dff_grouped.loc[condition, 'n_attacks'],
                y=dff_grouped.loc[condition, 'n_casualties'],
                mode='markers',
                marker=dict(size=highlight_scale[i][1], 
                            color=highlight_scale[i][0]),
                name="",
                customdata=dff_grouped.loc[condition, ['gname', 'n_attacks', 'n_casualties']].to_numpy(),
                hovertemplate="<b>%{customdata[0]}</b><br>"
                              "Attacks: %{customdata[1]}<br>"
                              "Casualties: %{customdata[2]}",
                hoverlabel=dict(
                    bgcolor=highlight_scale[i][0],
                    bordercolor=default.hover_bordercolor.value,
                    font=default.hover_font_dict.value
                )
            )
        )


    # add lines
    mean_casualties_per_attack = dff_grouped['n_casualties'].sum()/dff_grouped['n_attacks'].sum()
    max_casualties = dff_grouped['n_casualties'].max()
    x_stop = max_casualties/mean_casualties_per_attack
    extension = 1.1
    fig.update_layout(
        uirevision=default.redrawid.value,
        shapes=[
            dict(
                type='line',
                x0=0,
                y0=0,
                x1=x_stop*extension,
                y1=x_stop*mean_casualties_per_attack*extension,
                line=dict(
                    color='grey',
                    width=2, 
                    dash='dash'
                )
            )
        ],
        annotations=[
            dict(
                x=x_stop*1.00,
                y=x_stop*mean_casualties_per_attack*1.05,
                text="Above average casualties",
                showarrow=False,
                font=default.hover_font_dict.value,
                xanchor='right',
                yanchor='bottom'
            ),
            dict(
                x=x_stop*extension,
                y=x_stop*mean_casualties_per_attack*1.045,
                text="Below average casualties",
                showarrow=False,
                font=default.hover_font_dict.value,
                xanchor='left',
                yanchor='top'
            )
        ]
    )

    # Update layout
    fig.update_layout(
        title=dict(
            text="Which groups cause most casualties?",
            yref="container",
            yanchor="top",
            y=0.97,
            xref="paper",
            xanchor="center",
            x=0.5,
            font=default.title_dict.value
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(
            zeroline=True,
            zerolinecolor=default.gridline_color.value,
            zerolinewidth=default.gridline_width.value,
            title=dict(
                text='Number of attacks',
                font=default.label_dict.value
            ),
            showgrid=True, 
            gridcolor=default.gridline_color.value, 
            gridwidth=default.gridline_width.value
        ),
        yaxis=dict(
            zeroline=True,
            zerolinecolor=default.gridline_color.value,
            zerolinewidth=default.gridline_width.value,
            title=dict(
                text='Sum of casualties',
                font=default.label_dict.value
            ),
            showgrid=True,
            gridcolor=default.gridline_color.value,
            gridwidth=default.gridline_width.value
        ),
        font=default.label_dict.value,
        showlegend=False,
        plot_bgcolor=default.plot_bgcolor.value,
        width=700,
        height=700
    )

    return fig


# update group filter by click in scatter
@callback(
    Output('crossfilter-group-dropdown', 'value'),
    State('crossfilter-group-dropdown', 'value'),
    Input('chart-scatter', 'clickData'),
    running=[(Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_group_filter(group, clickData):
    # if clicked
    if clickData is not None:
        # get clicked point
        selected_group = clickData['points'][0]['customdata'][0]

        # if no filter is applied
        if group is None:
            group = [selected_group]
        
        # if filter is applied and selection is not in it
        elif selected_group not in group:
            group.append(selected_group)
        
        # if filter is applied and selection is in it
        elif selected_group in group:
            group.remove(selected_group)
        
        # update filter
        return group
    return no_update


###############################################################################
# deploy app
def open_browser():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
	    webbrowser.open_new("http://localhost:{}".format(port))


if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, port=port)