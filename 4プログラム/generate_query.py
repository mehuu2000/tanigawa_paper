# 自作関数
def escape_solr_query(text):
    # Solrの特殊文字リスト (長い順、または '\' を最初にエスケープ) + 半角スペース
    # '\\' は必ず最初にエスケープしないと、他の文字をエスケープした後に発生する '\\' もエスケープされてしまう
    solr_special_chars_map = {
        '\\': r'\\', # バックスラッシュ自体をエスケープ
        '+': r'\+',
        '-': r'\-',
        '&': r'\&',
        '|': r'\|',
        '!': r'\!',
        '(': r'\(',
        ')': r'\)',
        '{': r'\{',
        '}': r'\}',
        '[': r'\[',
        ']': r'\]',
        '^': r'\^',
        '"': r'\"',
        '~': r'\~',
        '*': r'\*',
        '?': r'\?',
        ':': r'\:',
        '/': r'\/'
    }

    escaped_text = text
    # キーの順序が重要になるため、明示的に指定するか、一度に置き換える
    for char, escaped_char in solr_special_chars_map.items():
        escaped_text = escaped_text.replace(char, escaped_char)
    return escaped_text