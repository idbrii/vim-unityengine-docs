# Download Unity3D docs
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
# from __future__ import unicode_literals

try:
    from html.parser import HTMLParser
except ImportError:
    # python 2
    from HTMLParser import HTMLParser

try:
    import urllib.request, urllib.parse, urllib.error
except ImportError:
    import urllib as urllib_py2
    class urllib:
        request = urllib_py2
        parse = urllib_py2
        error = urllib_py2

import re
import os
import os.path

# TODO: The unity ScriptReference page no longer contains a list of all types.
# Instead, the types are loaded into the tree dynamically via javascript. So
# this script no longer works.
#
# May have to do something in C# from inside Unity instead:
#   using System.Linq;
#   string nspace = "Unity";
#   var assemblies = System.AppDomain.CurrentDomain.GetAssemblies().ToList();
#   assemblies.Add(System.Reflection.Assembly.GetExecutingAssembly());
#   var types = new System.Collections.Generic.List<string>();
#   foreach (var assembly in assemblies)
#   {
#       var q = from t in assembly.GetTypes()
#           where t.IsClass && !string.IsNullOrEmpty(t.Namespace) && t.Namespace.StartsWith(nspace)
#           select t;
#       q.ToList().ForEach(t => types.Add(t.Namespace +"."+ t.Name));
#   }
#   Debug.Log("LIST OF TYPES:\n"+ string.Join("\n", types.ToArray()) +"\nLIST OF TYPES\n", this);
#
# This above solution is incomplete. It doesn't load enough assemblies to get
# the right types (Mathf is missing). It loaded 3500 types for me but
# unity-type-index has 10000.
#
BASE_URL = r"http://docs.unity3d.com/Documentation/ScriptReference/"
OUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "unity-type-index.txt"
    )
TEMP = OUT + "~"

# Stack functions ==============================================================
def stack_is_empty(stack):
    return len(stack) == 0

def stack_show_last_element(stack):
    return stack[-1] if len(stack) else None

def stack_print_action(stack, tag, action, indent=1):
    print (" " * indent * len(stack) \
           + action + " " + tag + ". New depth: " +  str(len(stack)) \
           )

# HTMLParser functions =========================================================
def has_attribute_with_value(attrs, name, value):
    return len([a for a in attrs if a[0]==name and a[1]==value]) > 0

def get_attribute(attrs, name):
    xs = [a for a in attrs if a[0]==name]
    return xs[0] if len(xs) > 0 else None

# Unity types parser ===========================================================
class TypesParser (HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.types = []
        self.stack = []
        self.inside_left_menu = False
        self.relevant_tags = ["a", "li", "ul"]
        self.verbose = False

    @staticmethod
    def is_left_menu(stack, tag, attrs):
        return tag == "ul" \
            and stack_is_empty(stack) \
            and has_attribute_with_value(attrs, "class", "left-menu")

    def handle_starttag(self, tag, attrs):
        if not tag in self.relevant_tags: return
        if TypesParser.is_left_menu(self.stack, tag, attrs):
            self.stack.append(tag)
            self.inside_left_menu = True
            return
        if not self.inside_left_menu: return

        self.stack.append(tag)

        if self.verbose: stack_print_action(self.stack, tag, "Pushed", 1)

    def handle_data(self, data):
        if stack_show_last_element(self.stack) == "a":
            # print data
            self.types.append(data)

    def handle_endtag(self, tag):
        if not self.inside_left_menu: return
        if not tag in self.relevant_tags: return

        self.stack.pop()
        if self.verbose: stack_print_action(self.stack, "Popped", tag, 1)

        if stack_is_empty(self.stack):
            self.inside_left_menu = False

# Unity type info parser =======================================================
class TypeInfoParser (HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.base = None
        self.field_names = []
        self.stack = []
        self.relevant_tags = ["th", "a"]
        self.inside_th = False
        self.verbose = False

    def handle_starttag(self, tag, attrs):
        if not tag in self.relevant_tags: return
        if tag == "a" and not self.inside_th: return
        if tag == "th": self.inside_th = True

        self.stack.append(tag)
        if self.verbose: stack_print_action(self.stack, tag, "Pushed", 1)

        if tag == "a":
            attr, value = get_attribute(attrs, "href")
            # Fill in the href for the method name
            self.field_names.append([None, value])

    def handle_data(self, data):
        if stack_show_last_element(self.stack) == "a":
            # Fill in the name for the href
            self.field_names[-1][0] = data

    def handle_endtag(self, tag):
        if not tag in self.relevant_tags: return
        if tag == "a" and not self.inside_th: return
        if tag == "th": self.inside_th = False
        self.stack.pop()
        if self.verbose: stack_print_action(self.stack, tag, "Popped", 1)

# File formatting functions ====================================================
def get_type_name_from_line(line):
    type_name = re.match(r"^[^\t\.]*", line)
    return type_name.group() if type_name is not None else None

def get_last_downloaded_type(lines):
    if len(lines) == 0: return []
    last_line = lines[-1]
    return get_type_name_from_line(last_line)

def get_line_for_type_name(type_name):
    return "%s\t[%s.html]" % (type_name, type_name)

# Main functions ===============================================================
def download_type_list(url):
    response = urllib.request.urlopen(url)
    html = response.read()
    # This part probably doesn't work! It most likely no longer
    # includes the whole index.
    #print(html)
    parser = TypesParser()
    parser.feed(html)
    return parser.types

def download_type_info(base_url, type_name):
    url = base_url + "/" + type_name + ".html"
    response = urllib.request.urlopen(url)
    html = response.read()
    parser = TypeInfoParser()
    parser.feed(html)
    return parser.field_names

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

def make():
    # Download type list from server
    remote_type_list = download_type_list(BASE_URL)

    # Read existing types
    touch(TEMP)
    handle = open(TEMP, "r")
    lines = handle.readlines()
    handle.close()

    # Parse the exisitng type names
    existing_type_names = [get_type_name_from_line(l) for l in lines]

    # Find the last type
    last_type_name = existing_type_names[-1] if existing_type_names else None

    # Make sure we don't have types that do no exist on the remote
    old_type_names = []
    old_lines = []
    for (existing_type_name, line) in zip(existing_type_names, lines):
        if existing_type_name in remote_type_list\
           and existing_type_name != last_type_name:
            old_type_names.append(existing_type_name)
            old_lines.append(line)

    # Find all types remaining_type_names for download
    remaining_type_names = []
    for remote_type_name in remote_type_list:
        if not remote_type_name in old_type_names:
            remaining_type_names.append(remote_type_name)

    # Write all old ones back to TEMP
    handle = open(TEMP, "w")
    handle.write("".join(old_lines)) # No need for \n
    handle.close()

    # Process the remaining type names
    lines = []
    n = 0
    limit_n = None # dev only
    try:
        for type_name in remaining_type_names:
            print (
                "Processing (%i/%i): " % (n+1, len(remaining_type_names))\
                + type_name
                )
            line = get_line_for_type_name(type_name)
            lines.append(line)
            field_names = download_type_info(BASE_URL, type_name)
            for field_name, url in field_names:
                line = "%s.%s\t[%s]" % (type_name, field_name, url)
                lines.append(line)
            n += 1
            if limit_n and n >= limit_n: break
    except KeyboardInterrupt:
        # commit to file
        handle = open(TEMP, "a")
        handle.write("\n".join(lines))
        handle.close()
        pass

    # commit to main file
    handle = open(OUT, "w")
    handle.write("\n".join(lines))
    handle.close()

make()
