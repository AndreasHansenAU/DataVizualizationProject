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
    selection_color = 'rgba(200, 80, 0, 1)' # dark orange
    selection_size = 10
    related_color = 'rgba(200, 130, 0, 0.9)' # lighter orange
    related_size = 10
    highlight_color = 'rgba(65, 105, 225, 0.8)' # blue
    background_color = 'rgba(211, 211, 211, 0.3)' # light grey
    marker_size = 10

    # plot
    plot_bgcolor = 'white'

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