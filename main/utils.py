def standardize_uuid(uuid_string):
    """Remove hyphens from UUID string"""
    return uuid_string.replace('-', '')

def format_uuid_with_hyphens(uuid_string):
    """Add hyphens to UUID string in standard format"""
    uuid_clean = uuid_string.replace('-', '')
    return '-'.join([
        uuid_clean[:8],
        uuid_clean[8:12],
        uuid_clean[12:16],
        uuid_clean[16:20],
        uuid_clean[20:]
    ]) 