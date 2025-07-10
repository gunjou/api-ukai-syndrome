blacklist = set()

def add_to_blacklist(jti):
    blacklist.add(jti)

def is_blacklisted(jti):
    return jti in blacklist