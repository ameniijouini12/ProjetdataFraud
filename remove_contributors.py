def commit_callback(commit):
    if commit.author_name == b"Erven Idjad":
        commit.skip()
    elif commit.author_name == b"Meracqy":
        commit.skip()
