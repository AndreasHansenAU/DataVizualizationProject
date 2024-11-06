from utils.Jitter import add_jitter
from dash import Dash, html, dcc, ctx, Input, Output, State, callback, no_update
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
df_terror.loc[df_terror['weaptype1_txt'].str.contains('Vehicle'), 'weaptype1_txt'] = 'Vehicle'

all_attacktypes = pd.Series(df_terror['attacktype1_txt'].unique(), name='attacktype1_txt')
all_weapontypes = pd.DataFrame(df_terror['weaptype1_txt'].unique(), columns=['weaptype1_txt'])
all_targettypes = pd.Series(df_terror['targtype1_txt'].unique(), name='targtype1_txt')

all_countries = df_terror[['country_txt', 'region_txt']].drop_duplicates().reset_index(drop=True)


###################
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


###################
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
            children=update_group_dropdown(None, [2015, 2020]),
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
        ])
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
        ], style={'padding': '0 20', 'marginTop': '20px'}),  # Adjust padding and margin to space them out

        html.Div([
            dcc.Graph(
                id='scatterplot-severity'
            )
        ], style={'padding': '0 20', 'marginTop': '20px'})
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
def update_map_heatmap(map_state, clickData, year_range, attacktype, weapontype, targettype, group, metric):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, weapontype, targettype, group)
    
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
    if 'map-heatmap.clickData' in trigger:
        clicked_lat = clickData['points'][0]['lat']
        clicked_lon = clickData['points'][0]['lon']
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
                         center=center, #dict(lat=0, lon=0)
                         zoom=zoom, # 0
                         map_style="open-street-map", # "satellite-streets" #"open-street-map",
                         color_continuous_scale=color_scale,
                         opacity=1,
                         range_color=(0, max_density)
    )

    # update hover box
    fig.update_traces(customdata=dff[['eventid', 'country_txt', 'iday', 'imonth', 'iyear',
                                      'summary', 'crit1', 'crit2', 'crit3', 'related', 'region_txt', 'provstate', 'city', 
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
                      hovertemplate="<b>%{customdata[2]}-%{customdata[3]}-%{customdata[4]} %{customdata[12]}, %{customdata[1]}</b><br>"
                                    "Group: %{customdata[23]}<br>"
                                    "Attack type: %{customdata[13]}<br>"
                                    "Weapon type: %{customdata[16]}<br>"
                                    "Target type: %{customdata[18]}<br>")


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
        clicked_lat = clickData['points'][0]['lat']
        clicked_lon = clickData['points'][0]['lon']
        related = clickData['points'][0]['customdata'][9]
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
        clicked_eventid = clickData['points'][0]['customdata'][0]
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
    Input('map-heatmap', 'clickData'),
    prevent_initial_call=True
)
def update_map_state(relayoutData, clickData):
    trigger = list(ctx.triggered_prop_ids.keys())

    # if triggered by click then update state to clicked points location
    if 'map-heatmap.clickData' in trigger:
        clicked_lat = clickData['points'][0]['lat']
        clicked_lon = clickData['points'][0]['lon']
        return {'zoom': 7,
                'center': {'lat':clicked_lat, 'lon':clicked_lon}}

    # if triggered by relayout then update state
    if 'map-heatmap.relayoutData' in trigger:
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
    eventid = point_data[0]
    country = point_data[1]
    day = point_data[2]
    month = point_data[3]
    year = point_data[4]
    summary = point_data[5]
    crit1 = point_data[6]
    crit2 = point_data[7]
    crit3 = point_data[8]
    related = point_data[9]
    region_txt = point_data[10]
    provstate = point_data[11]
    city = point_data[12]
    
    # Attack types
    attacktype1 = point_data[13]
    #attacktype2 = point_data[13]
    #attacktype3 = point_data[14]
    
    # Success and suicide
    success = point_data[14]
    suicide = point_data[15]
    
    # Weapon types and subtypes
    weaptype1 = point_data[16]
    weapsubtype1 = point_data[17]
    #weaptype2 = point_data[19]
    #weapsubtype2 = point_data[20]
    #weaptype3 = point_data[21]
    #weapsubtype3 = point_data[22]
    
    # Target types and subtypes
    targtype1 = point_data[18]
    targsubtype1 = point_data[19]
    #targtype2 = point_data[25]
    #targsubtype2 = point_data[26]
    #targtype3 = point_data[27]
    #targsubtype3 = point_data[28]
    
    # Corporate 
    corp1 = point_data[20]
    #corp2 = point_data[30]
    #corp3 = point_data[31]
    
    # Target
    target1 = point_data[21]
    #target2 = point_data[33]
    #target3 = point_data[34]
    
    # Target nationaly
    natlty1 = point_data[22]
    #natlty2 = point_data[36]
    #natlty3 = point_data[37]
    
    # Groups
    group = point_data[23]
    guncertain = point_data[24]
    nperps = point_data[25]
    motive = point_data[26]
    
    # Casualties and injuries
    nkill = point_data[27]
    nkillter = point_data[28]
    nwound = point_data[29]
    nwoundte = point_data[30]
    
    # Property damage
    property = point_data[31]
    propvalue = point_data[32]
    
    # Hostage information
    ishostkid = point_data[33]
    nhostkid = point_data[34]
    nhours = point_data[35]
    ndays = point_data[36]
    
    # Flag
    flag = point_data[37]

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
    Input('crossfilter-weapontype-dropdown', 'value'),
    Input('crossfilter-targettype-dropdown', 'value'),
    Input('crossfilter-group-dropdown', 'value'),
    Input('toggle-metric', 'value'),
    running=[(Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_weapon_distribution(year_range, attacktype, weapontype, targettype, group, metric):
    # get cached data
    dff = filter_data(df_terror, year_range, attacktype, weapontype, targettype, group)
    
    # group by weapon type
    dff_grouped = dff.groupby(["weaptype1_txt"])

    # calculate number of death or number of attacks per weapon type
    if metric == "casualties":
        dff_num_weapons = dff_grouped["nkill"].sum().to_frame(name="count").reset_index(drop=False)
        weap_dist_title = 'Which weapons are used to harm or kill most people?'
    else:
        dff_num_weapons = dff_grouped["weaptype1_txt"].count().to_frame(name="count").reset_index(drop=False)
        weap_dist_title = 'Which weapons are most frequently used in attacks?'
    
    # join on all weapon types
    dff_prepared = all_weapontypes.merge(dff_num_weapons, on="weaptype1_txt", how="left")
    dff_prepared["count"] = dff_prepared["count"].fillna(0).astype(int)
    
    # sort by ascending count
    dff_sorted = dff_prepared.sort_values(by=['count'], ascending=True)

    fig = px.bar(dff_sorted, 
                 x='count', 
                 y='weaptype1_txt', 
                 orientation='h',
                 text='count',
                 text_auto=True
    )

    fig.update_layout(
        title=weap_dist_title,
        yaxis_title='',
        xaxis_title='Number of attacks',
        title_x=0.5
    )
    
    return fig


@callback(
    Output('scatterplot-severity', 'figure'),
    Input('crossfilter-year-slider', 'value'),
    running=[(Output('crossfilter-year-slider', 'disabled'), True, False),
             (Output('crossfilter-attacktype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-weapontype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-targettype-dropdown', 'disabled'), True, False),
             (Output('crossfilter-group-dropdown', 'disabled'), True, False),
             (Output('toggle-metric', 'disabled'), True, False)])
def update_chart_scatterplot_severity(year_range):
    # get cached data
    dff = filter_years(df_terror, year_range)

    dff_grouped = dff.groupby(['country_txt', 'region_txt'])
    dff_num_attack = dff_grouped['eventid'].count()
    dff_freq = dff_grouped['nkill'].mean()

    dff_prepared = all_countries.merge(dff_num_attack, left_on=['country_txt', 'region_txt'], right_index=True, how='left')
    dff_prepared = dff_prepared.merge(dff_freq, left_on=['country_txt', 'region_txt'], right_index=True, how='left')
    dff_prepared.columns = ['country_txt', 'region_txt', 'number_of_attacks', 'avg_kill']
    dff_prepared['number_of_attacks'] = dff_prepared['number_of_attacks'].fillna(0).astype(int)
    dff_prepared['avg_kill'] = dff_prepared['avg_kill'].fillna(0).round(4)

    fig = go.Figure(data=go.Scatter(x=dff_prepared['number_of_attacks'],
                                    y=dff_prepared['avg_kill'],
                                    mode='markers',
                                    text=dff_prepared['country_txt'])
    )

    fig.update_layout(title='Average casualties per attack per country', 
                      xaxis_title='Number of attacks', 
                      yaxis_title='Average casualties per attacks')

    return fig


@callback(
        Output('chart-parallel-sets', 'figure'),
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
def update_chart_parallel_sets(year_range, attacktype, weapontype, targettype, group):
    #dff = filter_years(df_terror, year_range)
    dff = filter_data(df_terror, year_range, attacktype=None, weapontype=None, targettype=None, group=group)

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
    
    # define order of dimensions
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


###################
# deploy app
def open_browser():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
	    webbrowser.open_new("http://localhost:{}".format(port))


if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, port=port)