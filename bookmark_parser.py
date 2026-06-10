import hashlib
from datetime import datetime
from bs4 import BeautifulSoup

from html.parser import HTMLParser

class NetscapeBookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bookmarks = []
        self.folders = set()
        self.current_path = []
        self.last_folder_name = ""
        self.in_h3 = False
        self.in_a = False
        self.temp_bookmark = None
        self.temp_text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_dict = dict(attrs)
        
        if tag == 'dl':
            if self.last_folder_name:
                self.current_path.append(self.last_folder_name)
                self.folders.add(self.last_folder_name)
                self.last_folder_name = ""
        elif tag == 'h3':
            self.in_h3 = True
            self.temp_text = []
        elif tag == 'a':
            self.in_a = True
            self.temp_text = []
            self.temp_bookmark = {
                'url': attr_dict.get('href', '').strip(),
                'add_date_raw': attr_dict.get('add_date', '')
            }

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'dl':
            if self.current_path:
                self.current_path.pop()
        elif tag == 'h3':
            self.in_h3 = False
            self.last_folder_name = "".join(self.temp_text).strip()
        elif tag == 'a':
            self.in_a = False
            if self.temp_bookmark:
                title = "".join(self.temp_text).strip()
                url = self.temp_bookmark['url']
                
                if url and not url.startswith('javascript:'):
                    add_date_raw = self.temp_bookmark['add_date_raw']
                    
                    add_date = ""
                    if add_date_raw:
                        try:
                            t = int(add_date_raw)
                            if t > 10000000000:
                                t = int(t / 1000000 - 11644473600)
                            add_date = datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')
                        except Exception:
                            add_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        add_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                    folder_str = " / ".join(self.current_path) if self.current_path else "Bookmarks Bar"
                    url_hash = hashlib.md5(url.encode('utf-8', errors='ignore')).hexdigest()
                    
                    self.bookmarks.append({
                        'url': url,
                        'title': title or url,
                        'folder': folder_str,
                        'add_date': add_date,
                        'hash': url_hash
                    })
                self.temp_bookmark = None

    def handle_data(self, data):
        if self.in_h3 or self.in_a:
            self.temp_text.append(data)

def parse_bookmarks_html(file_path):
    """
    Parses a Netscape Bookmark HTML file.
    Returns:
        bookmarks (list of dicts): list of parsed bookmarks.
        folders (list of str): list of folder names found.
    """
    parser = NetscapeBookmarkParser()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            parser.feed(content)
    except Exception as e:
        raise ValueError(f"无法读取或解析书签HTML文件: {str(e)}")
        
    return parser.bookmarks, sorted(list(parser.folders))

def export_bookmarks_to_html(bookmarks, output_file_path):
    """
    Exports a list of bookmarks to Netscape HTML format.
    bookmarks list of dict: [{'url', 'title', 'folder', 'add_date'}]
    """
    tree = {'folders': {}, 'bookmarks': []}
    
    for bm in bookmarks:
        # Use category as folder. If category is not set, fallback to folder. If both empty, fallback to '📦 其他'.
        folder_str = bm.get('category', '').strip() or bm.get('folder', '').strip() or '📦 其他'
        parts = [p.strip() for p in folder_str.split('/') if p.strip()]
        
        curr = tree
        for part in parts:
            if part not in curr['folders']:
                curr['folders'][part] = {'folders': {}, 'bookmarks': []}
            curr = curr['folders'][part]
        curr['bookmarks'].append(bm)
        
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write("<!DOCTYPE NETSCAPE-Bookmark-file-1>\n")
        f.write("<!-- This is an automatically generated file.\n")
        f.write("     It will be read and written.\n")
        f.write("     DO NOT EDIT! -->\n")
        f.write('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n')
        f.write("<TITLE>Bookmarks</TITLE>\n")
        f.write("<H1>Bookmarks</H1>\n")
        f.write("<DL><p>\n")
        
        def write_node(node, indent=4):
            indent_str = " " * indent
            
            # 1. Write current level bookmarks
            for bm in node['bookmarks']:
                url = bm.get('url', '')
                title = bm.get('title', '')
                add_date_str = bm.get('add_date', '')
                add_date_ts = ""
                if add_date_str:
                    try:
                        dt = datetime.strptime(add_date_str, '%Y-%m-%d %H:%M:%S')
                        add_date_ts = str(int(dt.timestamp()))
                    except Exception:
                        pass
                
                # Secure Output Encoding for HTML attributes
                # Standard replacement for URL/title escaping in bookmark HTML
                url_esc = url.replace('"', '&quot;')
                title_esc = title.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                
                f.write(f'{indent_str}<DT><A HREF="{url_esc}" ADD_DATE="{add_date_ts}">{title_esc}</A>\n')
                
            # 2. Write subfolders
            for folder_name, sub_node in node['folders'].items():
                folder_name_esc = folder_name.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                f.write(f'{indent_str}<DT><H3>{folder_name_esc}</H3>\n')
                f.write(f'{indent_str}<DL><p>\n')
                write_node(sub_node, indent + 4)
                f.write(f'{indent_str}</DL><p>\n')
                
        write_node(tree, 4)
        f.write("</DL><p>\n")
