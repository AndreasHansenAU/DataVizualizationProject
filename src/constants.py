from enum import Enum

class default(Enum):
    # font
    font_type = 'Arial'
    font_color = 'rgba(0, 0, 0, 1)'

    # title
    title_font_size = 20
    title_font_weight = 20

    # label
    label_font_size = 12
    label_font_weight = 10

    # hover
    hover_bordercolor = 'rgba(0, 0, 0, 1)'
    hover_font_size = 12
    hover_font_weight = 5

    # selection
    selection_opacity = 1
    selection_color = f'rgba(191, 38, 0, {selection_opacity})' # dark red
    selection_size = 10
    related_opacity = 0.9
    related_color = f'rgba(250, 137, 129, {related_opacity})' # light red
    related_size = 10
    highlight_opacity = 0.8
    highlight_color = f'rgba(61, 134, 215, {highlight_opacity})' # blue
    highlight_color_group = f'rgba(80, 163, 21, {highlight_opacity})'
    background_opacity = 0.5
    background_color = f'rgba(214, 227, 254, {background_opacity})' # light blue
    background_color_group = f'rgba(186, 204, 181, {background_opacity})'
    marker_size = 10

    # plot
    plot_bgcolor = 'white'
    gridline_color = 'lightgray'
    gridline_width = 0.5
    redrawid = 'redraw'

    # default states
    year_range = [2015, 2020]
    zoom = 0.1
    lat = 16.5
    lon = 10.4

    # predefined dictionaries
    title_dict = dict(
        color=font_color,
        family=font_type,
        size=title_font_size,
        weight=title_font_weight
    )
    
    label_dict = dict(
        color=font_color, 
        family=font_type, 
        size=label_font_size, 
        weight=label_font_weight
    )
    
    hover_font_dict = dict(
        color=font_color,
        family=font_type,
        size=hover_font_size,
        weight=hover_font_weight
    )