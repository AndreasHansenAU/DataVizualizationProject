
def get_related_ids(related_id_string):
    related_id_split = related_id_string.split(', ')
    related_id_list = [int(r) for r in related_id_split]
    return related_id_list